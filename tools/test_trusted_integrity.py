#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path
import subprocess
import tempfile
import unittest

from experiment_registry import sha256_file
from verify_trusted import verify_trusted


class TrustedIntegrityTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="trusted files ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "lab").mkdir()
        (self.root / "ground_truth").mkdir()
        self.file = self.root / "lab/evaluate"
        self.file.write_text("trusted fixture\n")
        self.manifest = {"schema_version": 1, "protected_roots": ["lab", "ground_truth"],
                         "files": {"lab/evaluate": sha256_file(self.file)}}
        self.save()
        subprocess.run(["git", "init", "-q", str(self.root)], check=True)
        subprocess.run(["git", "add", "lab", "ground_truth"], cwd=self.root, check=True)

    def save(self) -> None:
        (self.root / "ground_truth/trusted-manifest.json").write_text(json.dumps(self.manifest))

    def test_valid_manifest_passes(self) -> None:
        self.assertEqual({"ok": True, "checked": 1, "issues": []}, verify_trusted(self.root))

    def test_changed_and_deleted_files_fail(self) -> None:
        self.file.write_text("tampered\n")
        result = verify_trusted(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("hash mismatch" in issue for issue in result["issues"]))
        self.file.unlink()
        self.assertFalse(verify_trusted(self.root)["ok"])

    def test_omitted_tracked_file_is_detected(self) -> None:
        (self.root / "lab/new-tool").write_text("new tool\n")
        subprocess.run(["git", "add", "lab/new-tool"], cwd=self.root, check=True)
        result = verify_trusted(self.root)
        self.assertFalse(result["ok"])
        self.assertTrue(any("absent from manifest" in issue for issue in result["issues"]))

    def test_invalid_hash_or_external_entry_is_rejected(self) -> None:
        for value in ([], True, "not-a-hash"):
            with self.subTest(value=value):
                self.manifest["files"]["lab/evaluate"] = value
                self.save()
                self.assertFalse(verify_trusted(self.root)["ok"])
        self.manifest["files"] = {"../outside": "0" * 64}
        self.save()
        self.assertFalse(verify_trusted(self.root)["ok"])

    def test_malformed_manifest_is_a_structured_failure(self) -> None:
        path = self.root / "ground_truth/trusted-manifest.json"
        for raw in ("{", "null", "[]", '{"files": {}}'):
            with self.subTest(raw=raw):
                path.write_text(raw)
                self.assertFalse(verify_trusted(self.root)["ok"])


if __name__ == "__main__":
    unittest.main()
