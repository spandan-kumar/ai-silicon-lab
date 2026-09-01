#!/usr/bin/env python3
"""Extract exact resynthesis problems for maximal affine BENCH blocks."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path


PORT_RE = re.compile(r"^(INPUT|OUTPUT)\(([^)]+)\)$")
GATE_RE = re.compile(
    r"^([A-Za-z][A-Za-z0-9_]*)\s*=\s*(AND|XOR|XNOR)\(([^,]+),\s*([^)]+)\)$"
)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("bench", type=Path)
    parser.add_argument("output_dir", type=Path)
    args = parser.parse_args()

    data = args.bench.read_bytes()
    inputs: list[str] = []
    outputs: list[str] = []
    gates: list[tuple[str, str, str, str]] = []
    for line_number, raw in enumerate(data.decode().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if match := PORT_RE.fullmatch(line):
            (inputs if match.group(1) == "INPUT" else outputs).append(match.group(2))
            continue
        if not (match := GATE_RE.fullmatch(line)):
            raise ValueError(f"{args.bench}:{line_number}: unsupported syntax {line!r}")
        gates.append(tuple(piece.strip() for piece in match.groups()))

    if inputs != [f"U{i}" for i in range(8)] or outputs != [f"S{i}" for i in range(8)]:
        raise ValueError("expected U0..U7 inputs and S0..S7 outputs")

    values = {name: 1 << index for index, name in enumerate(inputs)}
    producer: dict[str, int] = {}
    and_count = 0
    for index, (lhs, operation, left, right) in enumerate(gates):
        if left not in values or right not in values:
            raise ValueError(f"gate {index} uses unavailable input")
        if operation == "AND":
            values[lhs] = 1 << (8 + and_count)
            and_count += 1
        else:
            values[lhs] = values[left] ^ values[right]
        producer[lhs] = index
    if and_count != 29:
        raise ValueError(f"expected 29 AND gates, got {and_count}")

    last_use: dict[str, int] = {name: -1 for name in values}
    for index, (_, _, left, right) in enumerate(gates):
        last_use[left] = max(last_use[left], index)
        last_use[right] = max(last_use[right], index)
    for name in outputs:
        last_use[name] = len(gates)

    blocks: list[tuple[int, int]] = []
    start: int | None = None
    for index, (_, operation, _, _) in enumerate(gates):
        if operation in {"XOR", "XNOR"} and start is None:
            start = index
        if operation == "AND" and start is not None:
            blocks.append((start, index))
            start = None
    if start is not None:
        blocks.append((start, len(gates)))

    args.output_dir.mkdir(parents=True, exist_ok=True)
    source_sha = hashlib.sha256(data).hexdigest()
    manifest: list[dict[str, object]] = []
    for block_index, (start, end) in enumerate(blocks):
        available_names = inputs + [lhs for lhs, _, _, _ in gates[:start]]
        source_values: list[int] = []
        source_names: list[str] = []
        seen: set[int] = set()
        for name in available_names:
            value = values[name]
            if value not in seen:
                seen.add(value)
                source_values.append(value)
                source_names.append(name)

        boundary_names = [
            gates[index][0]
            for index in range(start, end)
            if last_use[gates[index][0]] >= end
        ]
        target_values: list[int] = []
        target_names: list[list[str]] = []
        target_index: dict[int, int] = {}
        for name in boundary_names:
            value = values[name]
            if value in seen:
                continue
            if value in target_index:
                target_names[target_index[value]].append(name)
            else:
                target_index[value] = len(target_values)
                target_values.append(value)
                target_names.append([name])

        known_steps = end - start
        closure_values = list(source_values)
        closure_steps: list[tuple[int, int, int]] = []
        remaining = set(target_values)
        progress = True
        while remaining and progress:
            progress = False
            for target in list(remaining):
                pair: tuple[int, int] | None = None
                for left in range(len(closure_values)):
                    for right in range(left + 1, len(closure_values)):
                        if closure_values[left] ^ closure_values[right] == target:
                            pair = (left, right)
                            break
                    if pair is not None:
                        break
                if pair is None:
                    continue
                closure_steps.append((pair[0], pair[1], target))
                closure_values.append(target)
                remaining.remove(target)
                progress = True

        path = args.output_dir / f"affine-block-{block_index:02d}.txt"
        rendered = [
            "# BENCH maximal affine-block completion problem",
            f"# source_bench={args.bench.resolve()}",
            f"# source_bench_sha256={source_sha}",
            f"# gate_range=[{start},{end})",
            f"# known_completion={known_steps}",
            f"# source_names={','.join(source_names)}",
        ]
        for index, names in enumerate(target_names):
            rendered.append(f"# target_{index}_names={','.join(names)}")
        rendered.append("DIM 37")
        rendered.extend(f"SOURCE {value:x}" for value in source_values)
        rendered.extend(f"TARGET {value:x}" for value in target_values)
        path.write_text("\n".join(rendered) + "\n")
        manifest.append(
            {
                "block": block_index,
                "gate_start": start,
                "gate_end": end,
                "known_steps": known_steps,
                "sources": len(source_values),
                "targets": len(target_values),
                "target_names": target_names,
                "target_only_completion_possible": not remaining,
                "target_only_reached": len(target_values) - len(remaining),
                "target_only_steps": [
                    {"left": left, "right": right, "value": f"{value:x}"}
                    for left, right, value in closure_steps
                ],
                "problem": str(path.resolve()),
            }
        )

    print(json.dumps(manifest, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
