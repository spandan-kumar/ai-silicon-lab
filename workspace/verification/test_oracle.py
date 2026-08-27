#!/usr/bin/env python3
"""Negative and positive tests for the exact-frame comparator."""

from __future__ import annotations

from pathlib import Path
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent))
import oracle


class ComparatorTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory(prefix="aisl-comparator-test-")
        self.root = Path(self.temp.name)
        self.frames = self.root / "frames"
        self.frames.mkdir()
        self.oracle_root = self.root / "oracles"
        self.workload = {"id": "synthetic", "capture_frames": 2}
        oracle_dir = self.oracle_root / "synthetic"
        oracle_dir.mkdir(parents=True)
        self.first = bytes([0x12]) * oracle.FRAME_BYTES
        self.second = bytes([0x34]) * oracle.FRAME_BYTES
        (oracle_dir / "oracle.bin").write_bytes(self.first + self.second)
        (self.frames / "frame-000000.rgb").write_bytes(self.first)
        (self.frames / "frame-000001.rgb").write_bytes(self.second)

    def tearDown(self) -> None:
        self.temp.cleanup()

    def compare(self) -> dict[str, object]:
        expected = {
            "oracles": {
                "synthetic": {
                    "archive_bytes": 2 * oracle.FRAME_BYTES,
                    "archive_sha256": oracle.sha256_file(self.oracle_root / "synthetic" / "oracle.bin"),
                }
            }
        }
        with (
            mock.patch.object(oracle, "ORACLE_ROOT", self.oracle_root),
            mock.patch.object(oracle, "load_expected", return_value=expected),
        ):
            return oracle.compare(self.workload, self.frames)

    def test_exact_match_passes(self) -> None:
        self.assertTrue(self.compare()["correct"])

    def test_one_byte_flip_fails(self) -> None:
        changed = bytearray(self.first)
        changed[123] ^= 1
        (self.frames / "frame-000000.rgb").write_bytes(changed)
        result = self.compare()
        self.assertFalse(result["correct"])
        self.assertEqual(result["mismatches"][0]["mismatch_bytes"], 1)

    def test_missing_frame_fails(self) -> None:
        (self.frames / "frame-000001.rgb").unlink()
        result = self.compare()
        self.assertFalse(result["correct"])
        self.assertEqual(result["missing"], ["frame-000001.rgb"])

    def test_extra_frame_fails(self) -> None:
        (self.frames / "frame-000002.rgb").write_bytes(self.first)
        result = self.compare()
        self.assertFalse(result["correct"])
        self.assertEqual(result["extra"], ["frame-000002.rgb"])

    def test_wrong_size_fails(self) -> None:
        (self.frames / "frame-000000.rgb").write_bytes(b"short")
        result = self.compare()
        self.assertFalse(result["correct"])
        self.assertEqual(result["mismatches"][0]["reason"], "wrong_size")


if __name__ == "__main__":
    unittest.main()
