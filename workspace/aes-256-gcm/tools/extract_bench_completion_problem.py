#!/usr/bin/env python3
"""Extract an affine completion problem after the last AND in an XAG BENCH."""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path


PORT_RE = re.compile(r"^(INPUT|OUTPUT)\(([^)]+)\)$")
GATE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s*=\s*(AND|XOR|XNOR)\(([^,]+),\s*([^)]+)\)$")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bench", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--tail-prefix", type=int, default=0)
    args = parser.parse_args()

    data = args.bench.read_bytes()
    parsed: list[tuple[str, ...]] = []
    outputs: list[str] = []
    for line_number, raw in enumerate(data.decode().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if match := PORT_RE.fullmatch(line):
            if match.group(1) == "OUTPUT":
                outputs.append(match.group(2))
            parsed.append((match.group(1), match.group(2)))
            continue
        if not (match := GATE_RE.fullmatch(line)):
            raise ValueError(f"{args.bench}:{line_number}: unsupported syntax {line!r}")
        parsed.append(match.groups())

    last_and = max(index for index, item in enumerate(parsed) if item[1] == "AND")
    tail_affines = [
        index
        for index, item in enumerate(parsed)
        if index > last_and and len(item) == 4 and item[1] in {"XOR", "XNOR"}
    ]
    if args.tail_prefix < 0 or args.tail_prefix > len(tail_affines):
        raise ValueError(f"tail prefix must be between 0 and {len(tail_affines)}")
    cutoff = last_and if args.tail_prefix == 0 else tail_affines[args.tail_prefix - 1]
    values: dict[str, int] = {}
    sources: list[int] = []
    and_count = 0
    affine_count = 0
    for position, item in enumerate(parsed):
        if item[0] == "INPUT":
            index = int(item[1].removeprefix("U"))
            values[item[1]] = 1 << index
            sources.append(1 << index)
            continue
        if item[0] == "OUTPUT":
            continue
        lhs, operation, left, right = item
        if operation == "AND":
            value = 1 << (8 + and_count)
            and_count += 1
        else:
            value = values[left.strip()] ^ values[right.strip()]
            affine_count += 1
        values[lhs] = value
        if position <= cutoff:
            if value in sources:
                raise ValueError(f"prefix recomputes affine value 0x{value:x} at {lhs}")
            sources.append(value)

    if and_count != 29 or outputs != [f"S{i}" for i in range(8)]:
        raise ValueError(f"expected 29 ANDs and S0..S7; got {and_count} and {outputs}")
    prefix_affine = len(sources) - 8 - 29
    targets = [values[name] for name in outputs]
    rendered = [
        "# BENCH last-AND affine completion problem",
        f"# source_bench={args.bench.resolve()}",
        f"# source_bench_sha256={hashlib.sha256(data).hexdigest()}",
        f"# existing_affine_gates={prefix_affine}",
        f"# total_affine_gates={affine_count}",
        "DIM 37",
    ]
    rendered.extend(f"SOURCE {value:x}" for value in sources)
    rendered.extend(f"TARGET {value:x}" for value in targets)
    args.output.write_text("\n".join(rendered) + "\n")
    print(
        f"sources={len(sources)} existing_affine_gates={prefix_affine} "
        f"known_completion={affine_count - prefix_affine} targets=8"
    )


if __name__ == "__main__":
    main()
