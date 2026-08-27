#!/usr/bin/env python3
"""Run the supplemental deterministic workloads on the RTL simulator."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
import hashlib
import json
from pathlib import Path
import subprocess
import time
from typing import Any

import oracle


ROOT = Path(__file__).resolve().parents[2]
DEFAULT_SIMULATOR = ROOT / "workspace" / "sim_cv" / "build" / "aisl_sim_cv"
DEFAULT_FIRMWARE = ROOT / "workspace" / "firmware" / "doom" / "build-candidate" / "doom.bin"
DEFAULT_WAD = ROOT / "workspace" / "assets" / "freedoom1.wad"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def run_workload(
    workload: dict[str, Any],
    output_root: Path,
    simulator: Path,
    firmware: Path,
    wad: Path,
) -> dict[str, Any]:
    run_root = output_root / workload["id"]
    frames = run_root / "frames"
    frames.mkdir(parents=True)
    result_path = run_root / "result.json"
    command = [
        str(simulator),
        "--firmware",
        str(firmware),
        "--wad",
        str(wad),
        "--inputs",
        str(ROOT / workload["input"]),
        "--frames-dir",
        str(frames),
        "--result",
        str(result_path),
        "--width",
        "320",
        "--height",
        "200",
        "--frame-count",
        str(workload["capture_frames"]),
        "--warmup",
        str(workload["warmup_frames"]),
        "--skill",
        str(workload["skill"]),
        "--episode",
        str(workload["episode"]),
        "--map",
        str(workload["map"]),
        "--max-cycles",
        "4000000000",
        "--trace-samples",
        "128",
        "--cycle-trace-stride",
        "1024",
        "--execution-trace-stride",
        "4096",
    ]
    started = time.monotonic()
    with (run_root / "stdout.log").open("wb") as stdout, (run_root / "stderr.log").open(
        "wb"
    ) as stderr:
        completed = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr, check=False)
    elapsed = time.monotonic() - started
    evidence: dict[str, Any] = {
        "workload": workload["id"],
        "command": command,
        "returncode": completed.returncode,
        "elapsed_seconds": elapsed,
    }
    if completed.returncode != 0:
        evidence["error"] = "simulator returned non-zero"
        write_json(run_root / "suite-result.json", evidence)
        return evidence
    if not result_path.is_file():
        evidence["error"] = "simulator result is missing"
        write_json(run_root / "suite-result.json", evidence)
        return evidence
    report = json.loads(result_path.read_text(encoding="utf-8"))
    comparison = oracle.compare(workload, frames)
    write_json(run_root / "comparison.json", comparison)
    evidence.update(
        {
            "correct": comparison["correct"] and report.get("success") is True,
            "cycles": report.get("cycles"),
            "retired_instructions": report.get("retired_instructions"),
            "frames": report.get("frames"),
            "tics": report.get("tics"),
            "result_sha256": sha256_file(result_path),
            "frame_stream_sha256": report.get("hashes", {}).get("frames_sha256"),
            "cycle_trace_sha256": report.get("hashes", {}).get("cycle_trace_sha256"),
            "native_trace_sha256": report.get("hashes", {}).get("native_trace_sha256"),
            "retire_trace_sha256": report.get("hashes", {}).get("retire_trace_sha256"),
            "comparison": comparison,
        }
    )
    write_json(run_root / "suite-result.json", evidence)
    return evidence


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("output_root", type=Path)
    parser.add_argument("--simulator", type=Path, default=DEFAULT_SIMULATOR)
    parser.add_argument("--firmware", type=Path, default=DEFAULT_FIRMWARE)
    parser.add_argument("--wad", type=Path, default=DEFAULT_WAD)
    parser.add_argument("--jobs", type=int, default=1)
    parser.add_argument("--workload", action="append", dest="workload_ids")
    args = parser.parse_args()

    output_root = args.output_root.resolve()
    if output_root.exists() and any(output_root.iterdir()):
        parser.error(f"output root must be absent or empty: {output_root}")
    output_root.mkdir(parents=True, exist_ok=True)
    if args.jobs < 1:
        parser.error("--jobs must be at least one")
    for path, label in (
        (args.simulator, "simulator"),
        (args.firmware, "firmware"),
        (args.wad, "WAD"),
    ):
        if not path.is_file():
            parser.error(f"{label} is missing: {path}")

    workloads = oracle.load_workloads()
    selected = args.workload_ids or list(workloads)
    unknown = sorted(set(selected) - set(workloads))
    if unknown:
        parser.error(f"unknown workload(s): {', '.join(unknown)}")

    results: dict[str, dict[str, Any]] = {}
    with ThreadPoolExecutor(max_workers=min(args.jobs, len(selected))) as executor:
        futures = {
            executor.submit(
                run_workload,
                workloads[workload_id],
                output_root,
                args.simulator.resolve(),
                args.firmware.resolve(),
                args.wad.resolve(),
            ): workload_id
            for workload_id in selected
        }
        for future in as_completed(futures):
            workload_id = futures[future]
            try:
                result = future.result()
            except Exception as exc:  # Preserve a suite summary even on infrastructure errors.
                result = {"workload": workload_id, "correct": False, "error": str(exc)}
            results[workload_id] = result
            print(json.dumps(result, sort_keys=True), flush=True)

    summary = {
        "schema_version": 1,
        "correct": all(result.get("correct") is True for result in results.values()),
        "parallel_jobs": min(args.jobs, len(selected)),
        "simulator_sha256": sha256_file(args.simulator),
        "firmware_sha256": sha256_file(args.firmware),
        "wad_sha256": sha256_file(args.wad),
        "results": {workload_id: results[workload_id] for workload_id in selected},
    }
    write_json(output_root / "suite-result.json", summary)
    return 0 if summary["correct"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
