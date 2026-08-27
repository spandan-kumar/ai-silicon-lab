#!/usr/bin/env python3
"""Verify functional and deterministic evidence from two RTL bring-up runs."""

import hashlib
import json
import pathlib
import sys


def load(path: str) -> dict:
    with pathlib.Path(path).open(encoding="utf-8") as handle:
        return json.load(handle)


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(f"usage: {sys.argv[0]} RESULT_A RESULT_B")
    first = load(sys.argv[1])
    second = load(sys.argv[2])
    for result in (first, second):
        assert result["success"] is True, result
        assert result["booted"] is True
        assert result["doom_started"] is True
        assert result["finished"] is True
        assert result["trap"] is False
        assert result["frames"] == 1
        assert result["input_count"] == 2
        assert result["firmware_stats"] == {
            "simulation_frames": 1,
            "game_tics": 123,
            "captured_frames": 1,
            "exit_code": 0,
        }
        assert result["retired_instructions"] > 20
        assert result["native_trace_events"] > 20
        for digest in result["hashes"].values():
            assert len(digest) == 64
            int(digest, 16)
        frame = pathlib.Path(result["artifacts"]["frames"][0]["path"])
        assert frame.read_bytes() == bytes.fromhex("112233a0b0c0")
        assert hashlib.sha256(frame.read_bytes()).hexdigest() == result["artifacts"]["frames"][0]["sha256"]
        uart = pathlib.Path(result["artifacts"]["uart_log"])
        assert uart.read_bytes() == b"OK\n"
        assert hashlib.sha256(uart.read_bytes()).hexdigest() == result["hashes"]["uart_sha256"]

    deterministic_fields = (
        "simulator_sha256",
        "rtl_sources_sha256",
        "firmware_sha256",
        "wad_sha256",
        "input_text_sha256",
        "input_records_sha256",
        "cycle_trace_sha256",
        "native_trace_sha256",
        "retire_trace_sha256",
        "frames_sha256",
        "uart_sha256",
    )
    for field in deterministic_fields:
        assert first["hashes"][field] == second["hashes"][field], field
    assert first["cycles"] == second["cycles"]
    assert first["retired_instructions"] == second["retired_instructions"]
    assert first["retire_trace_samples"] == second["retire_trace_samples"]
    print("bringup verification passed: RV32IM, MMIO, RGB capture, hashes, and repeatability")


if __name__ == "__main__":
    main()
