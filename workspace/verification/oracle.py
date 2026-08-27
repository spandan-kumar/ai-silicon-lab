#!/usr/bin/env python3
"""Generate deterministic supplemental oracles and compare candidate frames."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import time
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
WORKLOADS_PATH = ROOT / "workspace" / "verification" / "workloads.json"
EXPECTED_PATH = ROOT / "workspace" / "verification" / "expected-oracles.json"
REFERENCE = ROOT / "ground_truth" / "reference" / "bin" / "doomgeneric-headless"
SOURCE_METADATA = ROOT / "ground_truth" / "reference" / "SOURCE.json"
WAD = ROOT / "ground_truth" / "assets" / "freedoom1.wad"
ORACLE_ROOT = ROOT / ".aisl" / "verification" / "oracles"
FRAME_BYTES = 320 * 200 * 3


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def load_workloads() -> dict[str, dict[str, Any]]:
    value = json.loads(WORKLOADS_PATH.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or not isinstance(value.get("workloads"), list):
        raise ValueError("invalid workload manifest")
    workloads: dict[str, dict[str, Any]] = {}
    for workload in value["workloads"]:
        workload_id = workload.get("id")
        if not isinstance(workload_id, str) or not workload_id:
            raise ValueError("workload id must be a non-empty string")
        if workload_id in workloads:
            raise ValueError(f"duplicate workload id: {workload_id}")
        workloads[workload_id] = workload
    return workloads


def load_expected() -> dict[str, Any]:
    value = json.loads(EXPECTED_PATH.read_text(encoding="utf-8"))
    if value.get("schema_version") != 1 or not isinstance(value.get("oracles"), dict):
        raise ValueError("invalid expected-oracle manifest")
    return value


def validate_metadata(metadata: dict[str, Any]) -> None:
    expected = load_expected()
    workload_id = metadata["workload"]["id"]
    wanted = expected["oracles"].get(workload_id)
    if wanted is None:
        raise RuntimeError(f"no pinned oracle expectation for {workload_id}")
    actual = {
        "archive_bytes": metadata["archive_bytes"],
        "archive_sha256": metadata["archive_sha256"],
        "input_sha256": metadata["input_sha256"],
        "simulation_frames": metadata["reports"][0]["simulation_frames"],
        "tics": metadata["reports"][0]["tics"],
    }
    if actual != wanted:
        raise RuntimeError(f"pinned oracle mismatch for {workload_id}: {actual} != {wanted}")
    for field in ("wad_sha256", "reference_binary_sha256", "reference_revision"):
        if metadata[field] != expected[field]:
            raise RuntimeError(f"pinned {field} mismatch: {metadata[field]} != {expected[field]}")


def expected_names(count: int) -> list[str]:
    return [f"frame-{index:06d}.rgb" for index in range(count)]


def archive_frames(frame_dir: Path, count: int, output: Path) -> list[str]:
    names = expected_names(count)
    actual = sorted(path.name for path in frame_dir.glob("*.rgb"))
    if actual != names:
        raise RuntimeError(f"frame set mismatch: expected {len(names)}, received {len(actual)}")
    hashes: list[str] = []
    with output.open("wb") as archive:
        for name in names:
            path = frame_dir / name
            data = path.read_bytes()
            if len(data) != FRAME_BYTES:
                raise RuntimeError(f"{name}: expected {FRAME_BYTES} bytes, received {len(data)}")
            hashes.append(hashlib.sha256(data).hexdigest())
            archive.write(data)
    return hashes


def run_reference(workload: dict[str, Any], run_root: Path) -> dict[str, Any]:
    frames = run_root / "frames"
    frames.mkdir(parents=True)
    result_path = run_root / "result.json"
    input_path = ROOT / workload["input"]
    home = run_root / "home"
    tmp = run_root / "tmp"
    home.mkdir()
    tmp.mkdir()
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin"),
        "HOME": str(home),
        "TMPDIR": str(tmp),
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
        "AISL_INPUT_FILE": str(input_path),
        "AISL_FRAME_DIR": str(frames),
        "AISL_RESULT_FILE": str(result_path),
        "AISL_FRAME_WIDTH": "320",
        "AISL_FRAME_HEIGHT": "200",
        "AISL_FRAME_FORMAT": "rgb888",
        "AISL_FRAME_COUNT": str(workload["capture_frames"]),
        "AISL_FRAME_WARMUP": str(workload["warmup_frames"]),
    }
    command = [
        str(REFERENCE),
        "-iwad",
        str(WAD),
        "-skill",
        str(workload["skill"]),
        "-warp",
        str(workload["episode"]),
        str(workload["map"]),
    ]
    started = time.monotonic()
    completed = subprocess.run(command, cwd=run_root, env=env, capture_output=True, check=False)
    elapsed = time.monotonic() - started
    (run_root / "stdout.log").write_bytes(completed.stdout)
    (run_root / "stderr.log").write_bytes(completed.stderr)
    if completed.returncode != 0:
        raise RuntimeError(f"reference failed with exit {completed.returncode}: {run_root}")
    if not result_path.is_file():
        raise RuntimeError("reference result JSON is missing")
    report = json.loads(result_path.read_text(encoding="utf-8"))
    if report.get("booted") is not True or report.get("doom_started") is not True:
        raise RuntimeError(f"reference did not satisfy boot protocol: {report}")
    return {
        "command": command,
        "elapsed_seconds": elapsed,
        "frames": frames,
        "report": report,
        "stdout": run_root / "stdout.log",
        "stderr": run_root / "stderr.log",
    }


def generate(workload: dict[str, Any]) -> dict[str, Any]:
    workload_id = workload["id"]
    destination = ORACLE_ROOT / workload_id
    destination.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"aisl-oracle-{workload_id}-") as temp:
        temp_root = Path(temp)
        runs = []
        archives = []
        per_frame_hashes = []
        for repeat in range(2):
            run = run_reference(workload, temp_root / f"repeat-{repeat}")
            archive = temp_root / f"repeat-{repeat}.bin"
            frame_hashes = archive_frames(run["frames"], int(workload["capture_frames"]), archive)
            runs.append(run)
            archives.append(archive)
            per_frame_hashes.append(frame_hashes)
        archive_hashes = [sha256_file(path) for path in archives]
        if archive_hashes[0] != archive_hashes[1] or per_frame_hashes[0] != per_frame_hashes[1]:
            raise RuntimeError(f"reference is not deterministic for {workload_id}: {archive_hashes}")
        shutil.copyfile(archives[0], destination / "oracle.bin")
        shutil.copyfile(runs[0]["stdout"], destination / "reference.stdout.log")
        shutil.copyfile(runs[0]["stderr"], destination / "reference.stderr.log")
        source = json.loads(SOURCE_METADATA.read_text(encoding="utf-8"))
        metadata = {
            "schema_version": 1,
            "workload": workload,
            "deterministic_repeats": 2,
            "archive_sha256": archive_hashes[0],
            "archive_bytes": archives[0].stat().st_size,
            "per_frame_sha256": per_frame_hashes[0],
            "input_sha256": sha256_file(ROOT / workload["input"]),
            "wad_sha256": sha256_file(WAD),
            "reference_binary_sha256": sha256_file(REFERENCE),
            "reference_revision": source["reference_engine"]["revision"],
            "reports": [run["report"] for run in runs],
            "commands": [run["command"] for run in runs],
            "elapsed_seconds": [run["elapsed_seconds"] for run in runs],
        }
        validate_metadata(metadata)
        write_json(destination / "metadata.json", metadata)
        return metadata


def compare(workload: dict[str, Any], frame_dir: Path) -> dict[str, Any]:
    count = int(workload["capture_frames"])
    oracle_path = ORACLE_ROOT / workload["id"] / "oracle.bin"
    if not oracle_path.is_file():
        raise FileNotFoundError(f"oracle missing for {workload['id']}; run generate first")
    expected_oracle = load_expected()["oracles"][workload["id"]]
    if oracle_path.stat().st_size != expected_oracle["archive_bytes"]:
        raise RuntimeError(f"oracle has wrong size for {workload['id']}")
    if sha256_file(oracle_path) != expected_oracle["archive_sha256"]:
        raise RuntimeError(f"oracle hash mismatch for {workload['id']}")
    expected = expected_names(count)
    actual = sorted(path.name for path in frame_dir.glob("*.rgb"))
    missing = sorted(set(expected) - set(actual))
    extra = sorted(set(actual) - set(expected))
    mismatches: list[dict[str, Any]] = []
    with oracle_path.open("rb") as oracle:
        for index, name in enumerate(expected):
            wanted = oracle.read(FRAME_BYTES)
            path = frame_dir / name
            if not path.is_file():
                continue
            got = path.read_bytes()
            if len(got) != FRAME_BYTES:
                mismatches.append({"frame": index, "reason": "wrong_size", "bytes": len(got)})
            elif got != wanted:
                mismatch_bytes = sum(left != right for left, right in zip(got, wanted))
                mismatches.append(
                    {
                        "frame": index,
                        "reason": "byte_mismatch",
                        "mismatch_bytes": mismatch_bytes,
                        "sha256": hashlib.sha256(got).hexdigest(),
                    }
                )
    return {
        "workload": workload["id"],
        "correct": not missing and not extra and not mismatches,
        "frames_expected": count,
        "frames_received": len(actual),
        "missing": missing,
        "extra": extra,
        "mismatches": mismatches[:20],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="action", required=True)
    generate_parser = subparsers.add_parser("generate")
    generate_parser.add_argument("workload_ids", nargs="*")
    compare_parser = subparsers.add_parser("compare")
    compare_parser.add_argument("workload_id")
    compare_parser.add_argument("frame_dir", type=Path)
    args = parser.parse_args()
    workloads = load_workloads()
    if args.action == "generate":
        selected = args.workload_ids or list(workloads)
        unknown = sorted(set(selected) - set(workloads))
        if unknown:
            parser.error(f"unknown workload(s): {', '.join(unknown)}")
        generated = {workload_id: generate(workloads[workload_id]) for workload_id in selected}
        summary = {
            workload_id: {
                "archive_sha256": metadata["archive_sha256"],
                "archive_bytes": metadata["archive_bytes"],
                "deterministic_repeats": metadata["deterministic_repeats"],
            }
            for workload_id, metadata in generated.items()
        }
        print(json.dumps(summary, sort_keys=True))
        return 0
    result = compare(workloads[args.workload_id], args.frame_dir.resolve())
    print(json.dumps(result, sort_keys=True))
    return 0 if result["correct"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
