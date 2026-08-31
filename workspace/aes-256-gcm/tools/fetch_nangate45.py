#!/usr/bin/env python3
"""Fetch and hash-verify the pinned Nangate45 typical Liberty file."""

from __future__ import annotations

import argparse
import hashlib
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REVISION = "be0dca0b1fd41df54792b3012350cd52bccd99bb"
URL = (
    "https://raw.githubusercontent.com/The-OpenROAD-Project/"
    f"OpenROAD-flow-scripts/{REVISION}/flow/platforms/nangate45/lib/"
    "NangateOpenCellLibrary_typical.lib"
)
EXPECTED_SHA256 = "8d540a4d4cf6d09d27c87ad067857a9c0c2eeb023ab7a56e058cd3113db4e9b1"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "build" / "technology" / "nangate45" /
        "NangateOpenCellLibrary_typical.lib",
    )
    args = parser.parse_args()
    output = args.output.resolve()
    if output.exists() and digest(output) == EXPECTED_SHA256:
        print(f"technology: PASS cached=nangate45-typical sha256={EXPECTED_SHA256}")
        return 0
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_suffix(output.suffix + ".new")
    with urllib.request.urlopen(URL, timeout=60) as response:
        temporary.write_bytes(response.read())
    observed = digest(temporary)
    if observed != EXPECTED_SHA256:
        temporary.unlink(missing_ok=True)
        raise SystemExit(
            f"Nangate45 SHA-256 mismatch: expected {EXPECTED_SHA256}, got {observed}"
        )
    temporary.replace(output)
    print(f"technology: PASS downloaded=nangate45-typical sha256={observed}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
