#!/usr/bin/env python3
"""Turn an exact XOR-completion solution into an executable BP result."""

from __future__ import annotations

import argparse
import os
import re
import sys
from pathlib import Path


STEP_RE = re.compile(r"^STEP\s+\d+\s+(\d+)\s+(\d+)\s+([0-9a-fA-F]+)$")


def read_problem(path: Path) -> tuple[list[int], list[int], bool]:
    text = path.read_text()
    sources: list[int] = []
    targets: list[int] = []
    for line in text.splitlines():
        if line.startswith("SOURCE "):
            sources.append(int(line.split()[1], 16))
        elif line.startswith("TARGET "):
            targets.append(int(line.split()[1], 16))
    if not sources or len(targets) != 8:
        raise ValueError("invalid completion problem")
    return sources, targets, "# BENCH last-AND" in text


def reverse_input_bits(value: int) -> int:
    low = sum(((value >> bit) & 1) << (7 - bit) for bit in range(8))
    return (value & ~0xFF) | low


def append_solution(sources: list[int], solution: Path) -> None:
    for line in solution.read_text().splitlines():
        if not (match := STEP_RE.fullmatch(line)):
            continue
        left, right = int(match.group(1)), int(match.group(2))
        declared = int(match.group(3), 16)
        if left >= len(sources) or right >= len(sources) or left == right:
            raise ValueError(f"invalid solution operands in {line!r}")
        computed = sources[left] ^ sources[right]
        if computed != declared:
            raise ValueError(f"incorrect solution value in {line!r}")
        if computed in sources:
            raise ValueError(f"solution recreates existing value in {line!r}")
        sources.append(computed)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--framework-root", type=Path, required=True)
    parser.add_argument("--target-name", required=True)
    parser.add_argument("--problem", type=Path, required=True)
    parser.add_argument("--solution", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    output = args.output.resolve()
    sources, targets, bench_order = read_problem(args.problem)
    original_source_count = len(sources)
    append_solution(sources, args.solution)
    missing = [f"{target:x}" for target in targets if target not in sources]
    if missing:
        raise ValueError(f"solution does not realize targets: {missing}")

    framework = args.framework_root.resolve()
    previous = Path.cwd()
    os.chdir(framework)
    sys.path.insert(0, str(framework))
    try:
        import Change_Circuit_Formal  # type: ignore
        import Extract_XOR_information  # type: ignore
        import Optimizer_RNBP  # type: ignore

        Change_Circuit_Formal.circuit_formal(8, 8, args.target_name)
        xors, nonlinear, nots = Extract_XOR_information.extract_XOR_NOTs(
            8, 8, args.target_name
        )
        _, _, all_targets, _ = Optimizer_RNBP.initialize_S_D_Y_Sname(
            8, 8, len(nonlinear), xors
        )
        if bench_order:
            transformed = [reverse_input_bits(value) for value in sources]
            sources = list(reversed(transformed[:8])) + transformed[8:]
            targets = list(reversed([reverse_input_bits(value) for value in targets]))
        if all_targets[-8:] != targets:
            raise ValueError("completion problem targets do not match target circuit")
        circuit = Optimizer_RNBP.make_Circuit(
            8, 8, len(nonlinear), sources, all_targets, nonlinear, nots
        )
        template = (framework / "code_target_imps" / f"{args.target_name}.py").read_text()
        head, _, tail = template.split(
            "        ################### Here is your code !! ###################"
        )
        t_count = sum("t" in line.split("=", 1)[0] for line in circuit)
        r_count = sum("r" in line.split("=", 1)[0] for line in circuit)
        rendered = [
            head,
            "        ################### Here is your code !! ###################\n",
            f"        t = [0] * {t_count}; r = [0] * {r_count}\n",
        ]
        rendered.extend(
            "        "
            + line.replace("=", " = ").replace("^", " ^ ").replace("&", " & ").replace("|", " | ")
            + "\n"
            for line in circuit
        )
        rendered.extend(
            ["        ################### Here is your code !! ###################\n", tail]
        )
        output.write_text("".join(rendered))
    finally:
        os.chdir(previous)

    print(
        f"output={args.output} sources={len(sources)} "
        f"completion_steps={len(sources) - original_source_count}"
    )


if __name__ == "__main__":
    main()
