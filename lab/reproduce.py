#!/usr/bin/env python3
"""Replay a clean, committed evaluation in a detached Git worktree."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    parser = argparse.ArgumentParser(description="reproduce a recorded AI Silicon Lab run")
    parser.add_argument("run_id")
    args = parser.parse_args()
    if not args.run_id.replace("-", "").replace("_", "").replace(".", "").isalnum():
        print("invalid run ID", file=sys.stderr)
        return 2
    run_dir = ROOT / "runs" / args.run_id
    metrics_path = run_dir / "metrics.json"
    if not metrics_path.is_file():
        print(f"run not found: {args.run_id}", file=sys.stderr)
        return 2
    metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
    if not metrics.get("git", {}).get("reproducible"):
        print("run was not made from a clean committed Git revision", file=sys.stderr)
        return 2
    revision = metrics["git"]["before"].get("head")
    if not revision:
        print("run has no Git revision", file=sys.stderr)
        return 2
    worktree = ROOT / ".aisl" / "reproduce" / args.run_id
    if worktree.exists():
        print(f"reproduction worktree already exists: {worktree}", file=sys.stderr)
        return 2
    worktree.parent.mkdir(parents=True, exist_ok=True)
    added = subprocess.run(["git", "worktree", "add", "--detach", str(worktree), revision], cwd=ROOT, check=False)
    if added.returncode != 0:
        return added.returncode

    if metrics.get("validation_mode") == "self-test":
        self_test = "known-good" if "known-good" in metrics.get("candidate", {}).get("name", "") else "broken"
        command = [str(worktree / "lab" / "evaluate"), "--self-test", self_test]
    else:
        manifest = metrics.get("candidate", {}).get("manifest")
        if not manifest:
            print("run has no candidate manifest", file=sys.stderr)
            return 2
        command = [str(worktree / "lab" / "evaluate"), "--candidate", manifest]
    print(f"reproduction worktree: {worktree}")
    return subprocess.run(command, cwd=worktree, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
