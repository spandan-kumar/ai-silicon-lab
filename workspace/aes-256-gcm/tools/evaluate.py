#!/usr/bin/env python3
"""Run and retain the AES experiment's simulation-complete evidence."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import re
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parents[1]
BINARIES = [
    "build/openssl_baseline",
    "build/aes256_key_schedule_sim",
    "build/aes256_iterative_sim",
    "build/aes256_parallel_sim",
    "build/aes_gcm_iterative_sim",
    "build/aes_gcm_parallel_sim",
]


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=REPOSITORY, check=True, capture_output=True, text=True
    ).stdout.strip()


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", args.run_id):
        raise SystemExit("run ID must use lowercase letters, digits, dot, underscore, or dash")
    dirty_before = bool(git("status", "--porcelain", "--untracked-files=normal"))
    if dirty_before and not args.allow_dirty:
        raise SystemExit("refusing simulation-complete evaluation from a dirty worktree")

    run_directory = REPOSITORY / "runs" / args.run_id
    if run_directory.exists():
        raise SystemExit(f"run directory already exists: {run_directory}")
    run_directory.mkdir(parents=True)
    started_at = dt.datetime.now(dt.timezone.utc)
    commands: list[dict[str, object]] = []
    phases = [
        ("precheck", ["make", "reference", "vectors", "software", "rtl-functions", "lint", "verify-nist"]),
        ("build", ["make", *BINARIES]),
        ("simulation", ["make", "rtl-primitives", "rtl-gcm", "repeatability"]),
        ("synthesis", ["make", "synthesis"]),
    ]
    status = "pass"
    times: dict[str, float | None] = {
        "precheck_seconds": None,
        "build_seconds": None,
        "simulation_seconds": None,
        "synthesis_seconds": None,
    }
    for phase, command in phases:
        stdout_path = run_directory / f"{phase}.stdout.log"
        stderr_path = run_directory / f"{phase}.stderr.log"
        began = time.monotonic()
        with stdout_path.open("w") as stdout_file, stderr_path.open("w") as stderr_file:
            completed = subprocess.run(
                command, cwd=ROOT, stdout=stdout_file, stderr=stderr_file, text=True
            )
        elapsed = time.monotonic() - began
        times[f"{phase}_seconds"] = round(elapsed, 6)
        commands.append({
            "phase": phase,
            "argv": command,
            "exit_code": completed.returncode,
            "elapsed_seconds": round(elapsed, 6),
            "stdout": str(stdout_path.relative_to(REPOSITORY)),
            "stderr": str(stderr_path.relative_to(REPOSITORY)),
            "stdout_sha256": sha256(stdout_path),
            "stderr_sha256": sha256(stderr_path),
        })
        print(f"{phase}: {'PASS' if completed.returncode == 0 else 'FAIL'} elapsed_seconds={elapsed:.3f}")
        if completed.returncode != 0:
            status = "fail"
            break

    finished_at = dt.datetime.now(dt.timezone.utc)
    (run_directory / "commands.json").write_text(
        json.dumps(commands, indent=2, sort_keys=True) + "\n"
    )
    candidate_commit = git("rev-parse", "HEAD")
    instructions = REPOSITORY / "AGENTS.md"
    instruction_hashes = []
    if instructions.exists():
        instruction_hashes.append({"path": "AGENTS.md", "sha256": sha256(instructions)})
    artifacts = [str((run_directory / "commands.json").relative_to(REPOSITORY))]
    synthesis_summary = ROOT / "build" / "synth" / "summary.json"
    if synthesis_summary.exists():
        artifacts.append(str(synthesis_summary.relative_to(REPOSITORY)))
    run_record = {
        "schema_version": 1,
        "record_type": "experiment-run",
        "run_id": args.run_id,
        "experiment_id": "aes-256-gcm",
        "experiment_revision": 1,
        "status": status,
        "measurement_status": "mixed",
        "agent": {
            "model": {
                "provider": "OpenAI",
                "display_name": "Codex",
                "canonical_id": None,
                "identity_status": "unavailable",
            },
            "harness": {"name": "Codex desktop", "version": None, "environment": "local"},
            "reasoning": {"effort": None, "mode": None, "context": None},
            "goal_sha256": None,
            "instruction_hashes": instruction_hashes,
            "subagents": [],
            "notes": "Model identity, goal hash, and token telemetry were not exposed to the local evaluator.",
        },
        "usage": {
            "input_tokens": None,
            "cached_input_tokens": None,
            "cache_write_tokens": None,
            "output_tokens": None,
            "reasoning_tokens": None,
            "total_tokens": None,
            "source": "unavailable",
        },
        "time": {
            "started_at": started_at.isoformat(),
            "finished_at": finished_at.isoformat(),
            "agent_wall_seconds": None,
            "human_seconds": None,
            "build_seconds": times["build_seconds"],
            "simulation_seconds": times["simulation_seconds"],
            "synthesis_seconds": times["synthesis_seconds"],
            "hardware_seconds": None,
            "precheck_seconds": times["precheck_seconds"],
            "source": "measured for evaluator phases; unavailable for agent/human/physical time",
        },
        "cost": {
            "amount": None,
            "currency": "USD",
            "source": "unavailable",
            "rate_date": None,
        },
        "execution": {
            "candidate_commit": candidate_commit,
            "candidate_profile": "experiments/aes-256-gcm/profile.json",
            "harness_run_ids": [args.run_id],
            "lab_run_ids": [],
            "benchmark_id": "aes-256-gcm-64-v1",
            "tool_versions": {},
            "artifact_paths": artifacts,
            "commands": commands,
            "clean_before": not dirty_before,
            "clean_after": not bool(git("status", "--porcelain", "--untracked-files=normal")),
        },
        "result": {
            "status": "simulation-complete" if status == "pass" else "failed",
            "claim_level": "measured-local-evaluator",
            "reproducible": status == "pass" and not dirty_before,
            "physical_target": None,
            "timing": None,
            "power": None,
            "notes": "Physical implementation metrics remain unavailable because no target flow or board is configured.",
        },
        "evidence": [
            {
                "kind": "aes-local-evaluator",
                "path": str((run_directory / "commands.json").relative_to(REPOSITORY)),
                "description": "Command, exit-code, duration, and output-hash record for each gate phase.",
            }
        ],
    }
    run_path = run_directory / "run.json"
    run_path.write_text(json.dumps(run_record, indent=2, sort_keys=True) + "\n")
    validation = subprocess.run(
        [str(REPOSITORY / "tools" / "experiment"), "validate-run", str(run_path)],
        cwd=REPOSITORY,
    )
    if validation.returncode != 0:
        return validation.returncode
    print(f"evaluation: {status.upper()} run={args.run_id} record={run_path}")
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
