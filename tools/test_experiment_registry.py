#!/usr/bin/env python3

from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from experiment_registry import (
    EXPERIMENTS_DIR,
    load_json,
    load_registry,
    validate_run_record,
)


class ExperimentRegistryTests(unittest.TestCase):
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

    def test_nonfinite_numbers_are_not_accepted_by_json_loader(self) -> None:
        path = EXPERIMENTS_DIR / "examples" / "agent-run-reported.example.json"
        raw = Path(path).read_text(encoding="utf-8").replace("2600000", "NaN", 1)
        temporary_path = path.with_name(".nonfinite-test.json")
        try:
            temporary_path.write_text(raw, encoding="utf-8")
            with self.assertRaises(Exception):
                load_json(temporary_path)
        finally:
            temporary_path.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
