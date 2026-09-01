#!/usr/bin/env python3
"""Render a BENCH affine-block problem for the SBP heuristic."""

from __future__ import annotations

import argparse
import re
from pathlib import Path


GATE_RE = re.compile(
    r"^([A-Za-z][A-Za-z0-9_]*)\s*=\s*(AND|XOR|XNOR)\(([^,]+),\s*([^)]+)\)$"
)
RANGE_RE = re.compile(r"^# gate_range=\[(\d+),(\d+)\)$")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bench", type=Path)
    parser.add_argument("problem", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--threshold", type=int, required=True)
    parser.add_argument("--depth-limit", type=int, default=30)
    parser.add_argument(
        "--representations",
        help="semicolon-separated, comma-separated source indices for each target",
    )
    args = parser.parse_args()

    source_names: list[str] | None = None
    target_names: list[str] = []
    gate_range: tuple[int, int] | None = None
    for line in args.problem.read_text().splitlines():
        if line.startswith("# source_names="):
            source_names = line.split("=", 1)[1].split(",")
        elif line.startswith("# target_") and "_names=" in line:
            target_names.append(line.split("=", 1)[1].split(",")[0])
        elif match := RANGE_RE.fullmatch(line):
            gate_range = (int(match.group(1)), int(match.group(2)))
    if source_names is None or not target_names or gate_range is None:
        raise ValueError("problem lacks affine-block metadata")
    if len(source_names) >= 63:
        raise ValueError("SBP implementation supports at most 62 logical inputs")

    problem_sources = [
        int(line.split()[1], 16)
        for line in args.problem.read_text().splitlines()
        if line.startswith("SOURCE ")
    ]
    problem_targets = [
        int(line.split()[1], 16)
        for line in args.problem.read_text().splitlines()
        if line.startswith("TARGET ")
    ]
    if len(problem_sources) != len(source_names):
        raise ValueError("problem source metadata does not match source vectors")

    gates: list[tuple[str, str, str, str]] = []
    for raw in args.bench.read_text().splitlines():
        if match := GATE_RE.fullmatch(raw.strip()):
            gates.append(tuple(piece.strip() for piece in match.groups()))

    start, end = gate_range
    representations = {name: 1 << index for index, name in enumerate(source_names)}
    for lhs, operation, left, right in gates[start:end]:
        if operation not in {"XOR", "XNOR"}:
            raise ValueError("selected range is not purely affine")
        if left not in representations or right not in representations:
            raise ValueError(f"missing source representation for {lhs}")
        representations[lhs] = representations[left] ^ representations[right]
    missing = [name for name in target_names if name not in representations]
    if missing:
        raise ValueError(f"missing target representations: {missing}")

    row_values = [representations[name] for name in target_names]
    if args.representations:
        supplied = [
            [int(index) for index in group.split(",") if index]
            for group in args.representations.split(";")
        ]
        if len(supplied) != len(problem_targets):
            raise ValueError("one supplied representation is required per target")
        row_values = []
        for target, indices in zip(problem_targets, supplied):
            actual = 0
            encoded = 0
            for index in indices:
                actual ^= problem_sources[index]
                encoded ^= 1 << index
            if actual != target:
                raise ValueError("supplied representation does not realize its target")
            row_values.append(encoded)

    rows = []
    for value in row_values:
        rows.append(" ".join(str((value >> bit) & 1) for bit in range(len(source_names))))
    rendered = [
        f"1 {args.threshold} {args.depth_limit}",
        f"{len(rows)} {len(source_names)}",
        *rows,
    ]
    args.output.write_text("\n".join(rendered) + "\n")
    print(
        f"inputs={len(source_names)} targets={len(rows)} "
        f"threshold={args.threshold} weights="
        + ",".join(str(value.bit_count()) for value in row_values)
    )


if __name__ == "__main__":
    main()
