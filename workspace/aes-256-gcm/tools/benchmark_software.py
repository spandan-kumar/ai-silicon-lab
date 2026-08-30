#!/usr/bin/env python3
"""Measure both software baselines and emit provenance-rich JSON."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import platform
import statistics
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))

from aes_gcm import encrypt


LENGTHS = (0, 1, 15, 16, 17, 31, 32, 64)


def command_output(command: list[str]) -> str:
    result = subprocess.run(command, text=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, check=True)
    return result.stdout.strip()


def file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def measure_openssl(binary: Path, repeats: int) -> list[dict[str, object]]:
    samples: dict[tuple[int, int], list[float]] = {}
    iterations: dict[tuple[int, int], int] = {}
    for _ in range(repeats):
        output = command_output([str(binary), "--benchmark"])
        for row in csv.DictReader(io.StringIO(output)):
            key = int(row["payload_bytes"]), int(row["aad_bytes"])
            samples.setdefault(key, []).append(float(row["ns_per_transaction"]))
            iterations[key] = int(row["iterations"])
    return [{
        "payload_bytes": key[0],
        "aad_bytes": key[1],
        "iterations_per_repeat": iterations[key],
        "repeats": repeats,
        "median_ns_per_transaction": statistics.median(values),
        "min_ns_per_transaction": min(values),
        "max_ns_per_transaction": max(values),
        "median_ns_per_payload_byte": None if key[0] == 0 else statistics.median(values) / key[0],
    } for key, values in sorted(samples.items())]


def measure_reference(repeats: int) -> list[dict[str, object]]:
    key = bytes((3 * i + 1) & 0xFF for i in range(32))
    iv = bytes((5 * i + 2) & 0xFF for i in range(12))
    aad = bytes((7 * i + 3) & 0xFF for i in range(64))
    data = bytes((11 * i + 4) & 0xFF for i in range(64))
    results = []
    for index, payload_length in enumerate(LENGTHS):
        aad_length = LENGTHS[-1 - index]
        iterations = 100 if payload_length < 32 else 50
        samples = []
        for repeat in range(repeats):
            start = time.perf_counter_ns()
            for run in range(iterations):
                varying_iv = iv[:-1] + bytes([(iv[-1] + run + repeat) & 0xFF])
                encrypt(key, varying_iv, data[:payload_length], aad[:aad_length])
            samples.append((time.perf_counter_ns() - start) / iterations)
        median = statistics.median(samples)
        results.append({
            "payload_bytes": payload_length,
            "aad_bytes": aad_length,
            "iterations_per_repeat": iterations,
            "repeats": repeats,
            "median_ns_per_transaction": median,
            "min_ns_per_transaction": min(samples),
            "max_ns_per_transaction": max(samples),
            "median_ns_per_payload_byte": None if payload_length == 0 else median / payload_length,
        })
    return results


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--binary", type=Path, default=ROOT / "build" / "openssl_baseline")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--repeats", type=int, default=5)
    args = parser.parse_args()
    if args.repeats < 3:
        raise ValueError("at least three repeats are required")

    try:
        cpu = command_output(["sysctl", "-n", "machdep.cpu.brand_string"])
    except (subprocess.CalledProcessError, FileNotFoundError):
        cpu = platform.processor() or None
    document = {
        "schema_version": 1,
        "experiment_id": "aes-256-gcm",
        "profile_id": "aes-256-gcm-64-v1",
        "measured_at": datetime.now(timezone.utc).isoformat(),
        "measurement": "CLOCK_MONOTONIC/perf_counter wall time; median of repeated fixed-iteration runs",
        "host": {
            "platform": platform.platform(),
            "machine": platform.machine(),
            "cpu": cpu,
        },
        "tools": {
            "compiler": command_output(["cc", "--version"]).splitlines()[0],
            "linked_openssl": command_output([str(args.binary), "--version"]),
            "python": platform.python_version(),
        },
        "build": {
            "openssl_flags": "-std=c11 -O3 -Wall -Wextra -Werror $(pkg-config --cflags --libs openssl)",
            "binary_sha256": file_sha256(args.binary),
            "candidate_commit": command_output(["git", "rev-parse", "HEAD"]),
        },
        "limitations": [
            "Wall-time measurements are host-specific and are not CPU cycle counts.",
            "The OpenSSL implementation may use platform acceleration; the dependency-free Python model prioritizes auditability, not speed.",
            "Each transaction includes key/context setup, so these are cold-key end-to-end measurements.",
        ],
        "baselines": {
            "openssl_evp_aes_256_gcm": measure_openssl(args.binary, args.repeats),
            "dependency_free_python_reference": measure_reference(args.repeats),
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"software benchmark: wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
