#!/usr/bin/env python3

from __future__ import annotations

import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from experiment_registry import (
    EXPERIMENTS_DIR,
    ROOT,
    JsonLoadError,
    load_json,
    load_registry,
    validate_manifest,
    validate_run_record,
)


class ExperimentRegistryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.path = EXPERIMENTS_DIR / "examples" / "agent-run-reported.example.json"
        self.record = load_json(self.path)

    def test_repository_registry_and_examples_are_valid(self) -> None:
        registry, issues = load_registry()
        self.assertEqual([], issues)
        self.assertIsNotNone(registry)

        known_ids = {
            entry["experiment_id"]
            for entry in registry["experiments"]
        }
        for path in sorted((EXPERIMENTS_DIR / "examples").glob("*.json")):
            record = load_json(path)
            self.assertEqual([], validate_run_record(record, path, known_ids))

    def test_negative_usage_is_rejected(self) -> None:
        path = EXPERIMENTS_DIR / "examples" / "agent-run-reported.example.json"
        record = copy.deepcopy(load_json(path))
        record["usage"]["total_tokens"] = -1
        issues = validate_run_record(record, path, {"doom-rv32imc", "aes-256-gcm"})
        self.assertTrue(any("total_tokens" in issue and "negative" in issue for issue in issues))

    def test_invalid_numeric_measurements_are_rejected(self) -> None:
        for section, key in (("usage", "total_tokens"), ("time", "build_seconds"), ("cost", "amount")):
            for value in (True, False, -1, "12", [], {}, float("inf"), float("nan")):
                with self.subTest(section=section, key=key, value=value):
                    record = copy.deepcopy(self.record)
                    record[section].update(source="measured", **{key: value})
                    self.assertTrue(validate_run_record(record, self.path))
        self.record["usage"]["total_tokens"] = 1.5
        self.assertTrue(validate_run_record(self.record, self.path))

    def test_partial_telemetry_keeps_unknown_values_null(self) -> None:
        self.record["usage"].update(source="measured", total_tokens=12)
        self.assertEqual([], validate_run_record(self.record, self.path))

    def test_fully_unavailable_telemetry_is_valid(self) -> None:
        for section in ("usage", "time", "cost"):
            values = self.record[section]
            for key in values:
                if key.endswith(("_tokens", "_seconds", "_hours")) or key == "amount":
                    values[key] = None
            values.update(source="unavailable", notes="The harness did not expose telemetry.")
        self.record["agent"]["model"].update(identity_status="unknown", display_name=None)
        self.assertEqual([], validate_run_record(self.record, self.path))

    def test_nonfinite_numbers_are_not_accepted_by_json_loader(self) -> None:
        for value in ("NaN", "Infinity", "-Infinity", "1e999", "-1e999"):
            with self.subTest(value=value), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "record.json"
                path.write_text('{"extra": {"value": ' + value + '}}', encoding="utf-8")
                with self.assertRaises(JsonLoadError):
                    load_json(path)

    def test_duplicate_keys_are_rejected_including_nested_objects(self) -> None:
        for raw in ('{"status": "fail", "status": "pass"}',
                    '{"usage": {"source": "reported", "source": "measured"}}'):
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as directory:
                path = Path(directory) / "record.json"
                path.write_text(raw, encoding="utf-8")
                with self.assertRaisesRegex(JsonLoadError, "duplicate"):
                    load_json(path)

    def test_run_enum_fields_reject_json_values_without_crashing(self) -> None:
        fields = (
            ("status",), ("measurement_status",),
            ("agent", "model", "identity_status"),
            ("usage", "source"), ("time", "source"), ("cost", "source"),
        )
        for field in fields:
            for value in ([], {}, True, 1, None, "invalid"):
                with self.subTest(field=field, value=value):
                    record = copy.deepcopy(self.record)
                    section = record
                    for key in field[:-1]:
                        section = section[key]
                    section[field[-1]] = value
                    issues = validate_run_record(record, self.path)
                    self.assertTrue(any(".".join(field) in issue for issue in issues), issues)

    def test_manifest_status_rejects_containers_without_crashing(self) -> None:
        path = EXPERIMENTS_DIR / "doom-rv32imc" / "experiment.json"
        for value in ([], {}):
            with self.subTest(value=value):
                manifest = load_json(path)
                manifest["status"] = value
                self.assertTrue(validate_manifest(manifest, path))

    def test_boolean_schema_version_is_not_version_one(self) -> None:
        self.record["schema_version"] = True
        self.assertTrue(validate_run_record(self.record, self.path))
        path = EXPERIMENTS_DIR / "doom-rv32imc" / "experiment.json"
        manifest = load_json(path)
        manifest["schema_version"] = True
        self.assertTrue(validate_manifest(manifest, path))
        registry = load_json(EXPERIMENTS_DIR / "registry.json")
        registry["schema_version"] = True
        with patch("experiment_registry.load_json", side_effect=[registry, manifest,
                   load_json(EXPERIMENTS_DIR / "aes-256-gcm" / "experiment.json")]):
            _, issues = load_registry()
        self.assertTrue(any("registry.json: schema_version" in issue for issue in issues))

    def test_empty_known_experiment_set_rejects_every_experiment(self) -> None:
        self.assertTrue(validate_run_record(self.record, self.path, set()))
        self.assertEqual([], validate_run_record(self.record, self.path, None))

    def test_blank_experiment_revision_is_rejected(self) -> None:
        self.record["experiment_revision"] = "  "
        self.assertTrue(validate_run_record(self.record, self.path))

    def test_model_identity_must_support_its_claim(self) -> None:
        cases = (
            {"identity_status": "exact", "canonical_id": None},
            {"identity_status": "exact", "canonical_id": " "},
            {"identity_status": "alias-only", "display_name": None},
            {"identity_status": "alias-only", "canonical_id": "model-v1"},
            {"identity_status": "unknown", "canonical_id": "model-v1"},
        )
        for model in cases:
            with self.subTest(model=model):
                record = copy.deepcopy(self.record)
                record["agent"]["model"].update(model)
                self.assertTrue(validate_run_record(record, self.path))
        for identity, canonical_id, alias in (
            ("exact", "model-v1", "Readable alias"),
            ("alias-only", None, "Readable alias"),
            ("unknown", None, None),
        ):
            with self.subTest(identity=identity):
                self.record["agent"]["model"].update(
                    identity_status=identity, canonical_id=canonical_id, display_name=alias)
                self.assertEqual([], validate_run_record(self.record, self.path))

    def test_unavailable_telemetry_requires_null_and_a_source_note(self) -> None:
        for section, field in (("usage", "total_tokens"), ("time", "agent_wall_seconds"),
                               ("time", "reported_wall_hours"), ("cost", "amount")):
            for value in (0, 12):
                with self.subTest(section=section, field=field, value=value):
                    record = copy.deepcopy(self.record)
                    record[section].update(source="unavailable", **{field: value})
                    issues = validate_run_record(record, self.path)
                    self.assertTrue(any(field in issue and "unavailable" in issue for issue in issues), issues)
        for notes in (None, "", "   ", []):
            with self.subTest(notes=notes):
                self.record["cost"]["notes"] = notes
                self.assertTrue(validate_run_record(self.record, self.path))

    def test_missing_token_fields_are_not_silently_treated_as_null(self) -> None:
        del self.record["usage"]["reasoning_tokens"]
        self.assertTrue(validate_run_record(self.record, self.path))

    def test_zero_is_valid_when_measured(self) -> None:
        self.record["cost"].update(amount=0, source="measured")
        self.assertEqual([], validate_run_record(self.record, self.path))

    def test_cli_returns_json_failure_for_malformed_record(self) -> None:
        self.record["status"] = {}
        with tempfile.TemporaryDirectory(prefix="experiment records ") as directory:
            path = Path(directory) / "invalid record.json"
            path.write_text(json.dumps(self.record), encoding="utf-8")
            completed = subprocess.run(
                [str(ROOT / "tools" / "experiment"), "--json", "validate-run", str(path)],
                cwd=directory, capture_output=True, text=True, check=False,
            )
        self.assertEqual(1, completed.returncode)
        self.assertEqual("", completed.stderr)
        result = json.loads(completed.stdout)
        self.assertFalse(result["ok"])
        self.assertTrue(any("status" in issue for issue in result["issues"]))


if __name__ == "__main__":
    unittest.main()
