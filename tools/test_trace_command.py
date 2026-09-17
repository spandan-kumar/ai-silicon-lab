#!/usr/bin/env python3
"""Exercise the public trace wrapper in an isolated, space-bearing checkout."""

from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TraceCommandTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="lab trace tests ")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / "lab").mkdir()
        for name in ("trace", "trace_command.py"):
            shutil.copy2(ROOT / "lab" / name, self.root / "lab" / name)
        self.wrapper = str(self.root / "lab/trace")

    def command(self, code: str, label: str = "test") -> list[str]:
        return [self.wrapper, "--run-id", "test-run", "--label", label,
                "--", sys.executable, "-c", code]

    def run_trace(self, code: str, label: str = "test") -> subprocess.CompletedProcess:
        return subprocess.run(self.command(code, label), cwd=self.root.parent,
                              capture_output=True, text=True, check=False, timeout=20)

    def records(self) -> list:
        return json.loads((self.root / "runs/test-run/commands.json").read_text())

    def test_child_failure_and_both_logs_are_retained(self) -> None:
        result = self.run_trace("import sys; print('output'); print('error', file=sys.stderr); sys.exit(7)")
        self.assertEqual(7, result.returncode, result.stderr)
        record, = self.records()
        self.assertEqual(7, record["returncode"])
        self.assertEqual("output\n", (self.root / record["stdout"]).read_text())
        self.assertEqual("error\n", (self.root / record["stderr"]).read_text())

    def test_timestamps_enclose_real_child_execution(self) -> None:
        result = self.run_trace("import datetime as d; print(d.datetime.now(d.timezone.utc).isoformat())")
        self.assertEqual(0, result.returncode, result.stderr)
        record, = self.records()
        child_time = dt.datetime.fromisoformat((self.root / record["stdout"]).read_text().strip())
        started = dt.datetime.fromisoformat(record["started_at"].replace("Z", "+00:00"))
        finished = dt.datetime.fromisoformat(record["finished_at"].replace("Z", "+00:00"))
        self.assertLessEqual(started, child_time)
        self.assertLessEqual(child_time, finished)
        self.assertGreater(record["elapsed_seconds"], 0)

    def test_repeated_and_concurrent_labels_preserve_every_attempt(self) -> None:
        self.assertEqual(0, self.run_trace("print('first')").returncode)
        children = [subprocess.Popen(self.command("print(%r)" % value),
                                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
                    for value in ("second", "third")]
        for child in children:
            _, stderr = child.communicate(timeout=20)
            self.assertEqual(0, child.returncode, stderr)
        records = self.records()
        self.assertEqual(3, len(records))
        self.assertEqual(3, len({record["stdout"] for record in records}))
        self.assertEqual({"first", "second", "third"},
                         {(self.root / record["stdout"]).read_text().strip() for record in records})
        attempts = list((self.root / "runs/test-run/traces").glob("*/command.json"))
        self.assertEqual(3, len(attempts))
        self.assertCountEqual(records, [json.loads(path.read_text()) for path in attempts])

    def test_missing_executable_is_recorded_as_failure(self) -> None:
        result = subprocess.run([self.wrapper, "--run-id", "test-run", "--", "/missing/aisl-command"],
                                capture_output=True, text=True, check=False)
        self.assertEqual(127, result.returncode, result.stderr)
        record, = self.records()
        self.assertEqual(127, record["returncode"])
        self.assertIn("launch_error", record)
        self.assertTrue((self.root / record["stderr"]).read_text())

    def test_signal_exit_is_failure_and_original_status_is_recorded(self) -> None:
        result = self.run_trace("import os, signal; os.kill(os.getpid(), signal.SIGTERM)")
        self.assertEqual(143, result.returncode, result.stderr)
        record, = self.records()
        self.assertEqual(-15, record["returncode"])

    def test_invalid_names_and_empty_commands_are_rejected(self) -> None:
        for args in (["--run-id", "test-run"],
                     ["--run-id", "../escape", "--", sys.executable, "-c", "pass"],
                     ["--run-id", "test-run", "--label", "../escape", "--", sys.executable, "-c", "pass"]):
            with self.subTest(args=args):
                result = subprocess.run([self.wrapper, *args], capture_output=True, check=False)
                self.assertEqual(2, result.returncode)
        self.assertFalse((self.root / "runs").exists())

    def test_corrupt_existing_index_is_not_overwritten(self) -> None:
        run = self.root / "runs/test-run"
        run.mkdir(parents=True)
        (run / "commands.json").write_text("not-json")
        result = self.run_trace("print('retained')")
        self.assertNotEqual(0, result.returncode)
        self.assertEqual("not-json", (run / "commands.json").read_text())


if __name__ == "__main__":
    unittest.main()
