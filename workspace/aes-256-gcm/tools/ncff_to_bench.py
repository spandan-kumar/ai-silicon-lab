#!/usr/bin/env python3
"""Convert a binary-gate NIST NCFF SLP into a small BENCH file."""

from __future__ import annotations

import argparse
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("ncff", type=Path)
    parser.add_argument("bench", type=Path)
    args = parser.parse_args()

    active = False
    operations: list[tuple[str, str, str, str]] = []
    for line_number, raw in enumerate(args.ncff.read_text().splitlines(), 1):
        line = raw.strip()
        if line == "begin SLP":
            if active:
                raise ValueError("nested SLP")
            active = True
            continue
        if line == "end SLP":
            active = False
            break
        if not active or not line or line.startswith(("#", "%")):
            continue
        fields = line.split()
        if len(fields) != 4 or fields[0] not in {"AND", "XOR", "XNOR"}:
            raise ValueError(f"{args.ncff}:{line_number}: unsupported SLP line")
        operations.append(tuple(fields))
    if active or not operations:
        raise ValueError("missing or unterminated SLP")

    rendered = [*(f"INPUT(U{i})" for i in range(8)), *(f"OUTPUT(S{i})" for i in range(8))]
    rendered.extend(
        f"{output} = {operation}({left}, {right})"
        for operation, output, left, right in operations
    )
    args.bench.write_text("\n".join(rendered) + "\n")
    print(
        f"gates={len(operations)} "
        f"ands={sum(operation == 'AND' for operation, *_ in operations)} "
        f"affines={sum(operation != 'AND' for operation, *_ in operations)}"
    )


if __name__ == "__main__":
    main()
