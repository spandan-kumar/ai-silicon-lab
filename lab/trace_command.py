#!/usr/bin/env python3
"""Record one exploratory command with logs in a run directory."""

from __future__ import annotations

import argparse
import datetime as dt
import fcntl
import json
import os
from pathlib import Path
import re
import shlex
import subprocess
import sys
import tempfile
import time


ROOT = Path(__file__).resolve().parents[1]


def stamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def safe_name(value: str) -> str:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", value):
        raise argparse.ArgumentTypeError("use letters, digits, dots, underscores or hyphens, starting with a letter or digit")
    return value


def append_record(run_dir: Path, record: dict) -> None:
    # Different labels may finish concurrently in the same run directory.
    with (run_dir / ".trace.lock").open("a") as lock:
        fcntl.flock(lock, fcntl.LOCK_EX)
        commands_path = run_dir / "commands.json"
        records = json.loads(commands_path.read_text(encoding="utf-8")) if commands_path.exists() else []
        if not isinstance(records, list) or not all(isinstance(item, dict) for item in records):
            raise ValueError(f"{commands_path}: expected a list of command records")
        records.append(record)
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=run_dir,
                                         prefix=".commands-", delete=False) as handle:
            temporary = Path(handle.name)
            try:
                json.dump(records, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.replace(temporary, commands_path)
            finally:
                temporary.unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description="record an exploratory command")
    parser.add_argument("--run-id", required=True, type=safe_name)
    parser.add_argument("--label", default="trace", type=safe_name)
    parser.add_argument("command", nargs=argparse.REMAINDER)
    args = parser.parse_args()
    command = list(args.command)
    if command and command[0] == "--":
        command = command[1:]
    if not command:
        print("a command is required", file=sys.stderr)
        return 2
    run_dir = ROOT / "runs" / args.run_id
    if (ROOT / "runs").is_symlink() or run_dir.is_symlink():
        print("trace output directories must not be symlinks", file=sys.stderr)
        return 2
    traces = run_dir / "traces"
    if traces.is_symlink():
        print("trace output directories must not be symlinks", file=sys.stderr)
        return 2
    traces.mkdir(parents=True, exist_ok=True)
    attempt = Path(tempfile.mkdtemp(prefix=args.label + "-", dir=traces))
    stdout_path = attempt / "stdout.log"
    stderr_path = attempt / "stderr.log"
    started_at = stamp()
    started = time.monotonic()
    launch_error = None
    with stdout_path.open("xb") as stdout, stderr_path.open("xb") as stderr:
        try:
            completed = subprocess.run(command, cwd=ROOT, stdout=stdout, stderr=stderr, check=False)
            returncode = completed.returncode
        except OSError as exc:
            returncode = 127 if isinstance(exc, FileNotFoundError) else 126
            launch_error = str(exc)
            stderr.write((launch_error + "\n").encode("utf-8"))
    record = {
        "label": args.label,
        "command": shlex.join(command),
        "argv": command,
        "started_at": started_at,
        "finished_at": stamp(),
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "returncode": returncode,
        "stdout": str(stdout_path.relative_to(ROOT)),
        "stderr": str(stderr_path.relative_to(ROOT)),
    }
    if launch_error is not None:
        record["launch_error"] = launch_error
    # Keep an independent record even if the shared index cannot be updated.
    (attempt / "command.json").write_text(json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"trace artifacts: {attempt.relative_to(ROOT)}")
    append_record(run_dir, record)
    return returncode if returncode >= 0 else 128 - returncode


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as exc:
        print(f"trace failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
