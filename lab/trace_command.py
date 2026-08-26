#!/usr/bin/env python3
"""Record one exploratory command with logs in a run directory."""

from __future__ import annotations

import argparse
import datetime as dt
import json
from pathlib import Path
import shlex
import subprocess
import sys
import time


ROOT = Path(__file__).resolve().parents[1]


def stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def main() -> int:
    parser = argparse.ArgumentParser(description="record an exploratory command")
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--label", default="trace")
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("a command is required", file=sys.stderr)
        return 2
    run_dir = ROOT / "runs" / args.run_id
    run_dir.mkdir(parents=True, exist_ok=True)
    stdout_path = run_dir / f"{args.label}.stdout.log"
    stderr_path = run_dir / f"{args.label}.stderr.log"
    started = time.monotonic()
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        completed = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr, check=False)
    record = {
        "label": args.label,
        "command": shlex.join(command),
        "started_at": stamp(),
        "finished_at": stamp(),
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "returncode": completed.returncode,
        "stdout": str(stdout_path.relative_to(ROOT)),
        "stderr": str(stderr_path.relative_to(ROOT)),
    }
    commands_path = run_dir / "commands.json"
    records = []
    if commands_path.is_file():
        records = json.loads(commands_path.read_text(encoding="utf-8"))
    records.append(record)
    commands_path.write_text(json.dumps(records, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return completed.returncode
