#!/usr/bin/env python3
from __future__ import annotations

import copy
import hashlib
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch

from experiment_registry import ROOT, load_json, validate_run_record, validate_saved_runs, verify_evidence


class EvidenceFileTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="evidence artifacts ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.artifact = self.root / "run output.bin"
        self.artifact.write_bytes(b"measured output\x00\xff")
        self.record = load_json(ROOT / "experiments/examples/agent-run-reported.example.json")
        self.record["evidence"] = [{"kind": "test-output", "description": "Measured test output",
                                   "path": self.artifact.name,
                                   "sha256": hashlib.sha256(self.artifact.read_bytes()).hexdigest()}]

    def verify(self):
        self.assertEqual([], validate_run_record(self.record, Path("record.json")))
        return verify_evidence(self.record, Path("record.json"), self.root)

    def test_file_matches_including_uppercase_hash(self) -> None:
        self.assertEqual((1, []), self.verify())
        self.record["evidence"][0]["sha256"] = self.record["evidence"][0]["sha256"].upper()
        self.assertEqual((1, []), self.verify())

    def test_tampered_and_missing_artifacts_fail(self) -> None:
        self.artifact.write_bytes(b"changed")
        checked, issues = self.verify()
        self.assertEqual(1, checked)
        self.assertTrue(any("mismatch" in issue for issue in issues))
        self.artifact.unlink()
        checked, issues = self.verify()
        self.assertEqual(0, checked)
        self.assertTrue(issues)

    def test_missing_hash_is_allowed_structurally_but_not_for_verification(self) -> None:
        del self.record["evidence"][0]["sha256"]
        checked, issues = self.verify()
        self.assertEqual(0, checked)
        self.assertTrue(any("requires a SHA-256" in issue for issue in issues))

    def test_no_file_evidence_cannot_claim_verified_files(self) -> None:
        self.record["evidence"] = [{"kind": "owner-report", "path": None, "description": "Reported history"}]
        checked, issues = self.verify()
        self.assertEqual(0, checked)
        self.assertTrue(any("no file-backed evidence" in issue for issue in issues))

    def test_report_without_file_can_accompany_verified_file(self) -> None:
        self.record["evidence"].append({"kind": "owner-report", "path": None, "description": "Reported history"})
        self.assertEqual((1, []), self.verify())

    def test_malformed_hashes_and_hash_without_path_fail_structural_validation(self) -> None:
        for value in ("x" * 64, "abc", 17, [], {}, True):
            with self.subTest(value=value):
                record = copy.deepcopy(self.record)
                record["evidence"][0]["sha256"] = value
                self.assertTrue(validate_run_record(record, Path("record.json")))
        self.record["evidence"][0]["path"] = None
        self.assertTrue(validate_run_record(self.record, Path("record.json")))

    def test_external_and_non_regular_paths_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as outside:
            external = Path(outside) / "private.bin"
            external.write_bytes(self.artifact.read_bytes())
            (self.root / "external-link").symlink_to(external)
            (self.root / "loop").symlink_to("loop")
            os.mkfifo(self.root / "pipe")
            for value in (str(external), "../escape", "external-link", ".", "pipe", "loop", "bad\0name"):
                with self.subTest(value=value):
                    self.record["evidence"][0]["path"] = value
                    checked, issues = self.verify()
                    self.assertEqual(0, checked)
                    self.assertTrue(issues)

    def test_cli_verifies_relative_to_checkout_from_other_cwd(self) -> None:
        with tempfile.TemporaryDirectory(prefix="evidence-cli-", dir=ROOT / "runs") as directory:
            artifact = Path(directory) / "output with spaces.bin"
            artifact.write_bytes(self.artifact.read_bytes())
            self.record["evidence"][0]["path"] = str(artifact.relative_to(ROOT))
            path = self.root / "record.json"
            path.write_text(json.dumps(self.record))
            command = [str(ROOT / "tools/experiment"), "--json", "validate-run", str(path), "--verify-evidence"]
            result = subprocess.run(command, cwd=self.root, capture_output=True, text=True, check=False)
            self.assertEqual(0, result.returncode, result.stderr)
            self.assertEqual({"ok": True, "issues": [], "artifacts_checked": 1}, json.loads(result.stdout))
            artifact.unlink()
            result = subprocess.run(command, cwd=self.root, capture_output=True, text=True, check=False)
            self.assertEqual(1, result.returncode)
            self.assertFalse(json.loads(result.stdout)["ok"])

    def test_saved_records_are_included_in_registry_check(self) -> None:
        records = self.root / "doom-rv32imc/records"
        records.mkdir(parents=True)
        (records / "invalid.json").write_text('{"schema_version": false}')
        with patch("experiment_registry.EXPERIMENTS_DIR", self.root):
            issues = validate_saved_runs({"experiments": [{"experiment_id": "doom-rv32imc"}]})
        self.assertTrue(any("invalid.json" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
