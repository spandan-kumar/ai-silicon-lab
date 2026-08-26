#!/usr/bin/env python3
"""Apply the platform's strongest available local immutable-file control."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
TARGETS = (ROOT / "lab", ROOT / "ground_truth")


def main() -> int:
    parser = argparse.ArgumentParser(description="protect lab and ground truth")
    parser.add_argument("--apply", action="store_true", help="apply immutable flags")
    args = parser.parse_args()
    if not args.apply:
        print("Nothing changed. Re-run with --apply after the repository is complete.")
        return 0
    if not (ROOT / "ground_truth" / "trusted-manifest.json").is_file():
        print("trusted-manifest.json is missing; generate it before protection", file=sys.stderr)
        return 2

    for target in TARGETS:
        chmod = subprocess.run(["chmod", "-R", "a-w", str(target)], check=False)
        if chmod.returncode != 0:
            return chmod.returncode

    if shutil.which("chflags"):
        completed = subprocess.run(["chflags", "-R", "uchg", *(str(target) for target in TARGETS)], check=False)
        if completed.returncode == 0:
            print("Applied macOS uchg protection to lab/ and ground_truth/.")
            return 0
    if shutil.which("chattr"):
        completed = subprocess.run(["chattr", "-R", "+i", *(str(target) for target in TARGETS)], check=False)
        if completed.returncode == 0:
            print("Applied Linux immutable protection to lab/ and ground_truth/.")
            return 0
    print("No supported immutable-file control was available.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
