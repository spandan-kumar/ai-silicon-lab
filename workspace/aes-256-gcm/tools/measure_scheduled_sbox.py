#!/usr/bin/env python3
"""Measure validated scheduled S-box RTL with the pinned Nangate45 flow."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import time
from types import SimpleNamespace

import benchmark_masked_sbox_circuits as bench
from hpc2_schedule import load_schedule, validate_rtl


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", type=Path, required=True, help="schedule.json with adjacent scheduled.sv")
    parser.add_argument("--source", type=Path, help="relocated SLP source; must match the recorded hash")
    parser.add_argument("--output-dir", type=Path, required=True, help="new measurement directory under the workspace")
    parser.add_argument("--liberty", type=Path, default=bench.DEFAULT_LIBERTY)
    args = parser.parse_args()
    schedule = load_schedule(args.schedule, args.source)
    source_rtl = args.schedule.resolve().parent / "scheduled.sv"
    validate_rtl(schedule, source_rtl)
    liberty = args.liberty.resolve()
    if not liberty.exists() or bench.sha256_file(liberty) != bench.NANGATE45_SHA256:
        parser.error("pinned Nangate45 Liberty file missing or corrupt")
    output = args.output_dir.resolve()
    bench.relative(output)
    output.mkdir(parents=True, exist_ok=False)
    rtl = output / "scheduled.sv"
    shutil.copy2(source_rtl, rtl)
    shutil.copy2(args.schedule, output / "schedule.json")
    journal = []

    def retained_run(argv: list, **kwargs) -> subprocess.CompletedProcess:
        must_succeed = kwargs.pop("check", False)
        kwargs["capture_output"] = True
        began = time.monotonic()
        result = subprocess.run(argv, check=False, **kwargs)
        stem = output / f"command-{len(journal):02d}"
        stdout = result.stdout.encode() if isinstance(result.stdout, str) else result.stdout
        stderr = result.stderr.encode() if isinstance(result.stderr, str) else result.stderr
        stem.with_suffix(".stdout.log").write_bytes(stdout or b"")
        stem.with_suffix(".stderr.log").write_bytes(stderr or b"")
        journal.append({
            "argv": [str(argument) for argument in argv], "exit_code": result.returncode,
            "elapsed_seconds": time.monotonic() - began,
            "stdout": stem.name + ".stdout.log", "stderr": stem.name + ".stderr.log",
            "stdout_sha256": hashlib.sha256(stdout or b"").hexdigest(),
            "stderr_sha256": hashlib.sha256(stderr or b"").hexdigest(),
        })
        (output / "commands.json").write_text(json.dumps(journal, indent=2) + "\n")
        if must_succeed:
            result.check_returncode()
        return result

    # Inject only this module's command runner; never replace subprocess.run
    # process-wide. The benchmark functions and their hardware checks are reused.
    original_subprocess = bench.subprocess
    bench.subprocess = SimpleNamespace(run=retained_run)
    try:
        functional = bench.verify_rtl("scheduled", rtl, schedule["latency"], output)
        formal = bench.verify_gadget_formally("scheduled", rtl, output)
        mapped = bench.map_rtl("scheduled", rtl, liberty, output)
        cells = bench.create_functional_cell_model(liberty, output)
        gate = bench.verify_mapped_netlist(
            "scheduled", output / "scheduled-netlist.v", cells, schedule["latency"], output
        )
    finally:
        bench.subprocess = original_subprocess
    summary = {
        "schedule": schedule, "functional_output": functional, **formal, **mapped, **gate,
        "rtl_sha256": bench.sha256_file(rtl), "liberty_sha256": bench.sha256_file(liberty),
        "schedule_sha256": bench.sha256_file(args.schedule),
        "claim": "Functional and mapping measurements only; composition verification is separate. No physical leakage or novelty claim.",
    }
    (output / "measurement.json").write_text(json.dumps(summary, indent=2) + "\n")
    print(json.dumps({key: value for key, value in summary.items() if key not in {"schedule", "mapped_cell_types"}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
