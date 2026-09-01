#!/usr/bin/env python3
"""Independently audit an Extended-BP-Framework circuit result."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path


MARKER = "################### Here is your code !! ###################"
VALUE_RE = re.compile(r"^(?:[xyrtg]\[\d+\]|[01])$")


def load_sbox(path: Path) -> list[int]:
    spec = importlib.util.spec_from_file_location("extended_bp_candidate", path)
    if spec is None or spec.loader is None:
        raise ValueError(f"cannot import {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    values = list(module.AES_Sbox())
    expected = [module._aes_reference(value) for value in range(256)]
    if values != expected:
        mismatches = [i for i, (a, b) in enumerate(zip(values, expected)) if a != b]
        raise ValueError(f"AES S-box mismatch at {mismatches[:8]}")
    return values


def parse_metrics(path: Path) -> dict[str, int]:
    parts = path.read_text().split(MARKER)
    if len(parts) != 3:
        raise ValueError("expected exactly two circuit markers")

    gate_depth = {f"x[{index}]": 0 for index in range(8)}
    and_depth = dict(gate_depth)
    counts = {
        "and_gates": 0,
        "or_gates": 0,
        "xor_xnor_gates": 0,
        "not_gates": 0,
        "copies": 0,
    }

    for line_number, raw in enumerate(parts[1].splitlines(), 1):
        line = raw.strip().rstrip(";")
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        lhs, rhs = (piece.strip() for piece in line.split("=", 1))
        if rhs.startswith("[0]"):
            continue
        if not VALUE_RE.fullmatch(lhs) or lhs in {"0", "1"}:
            raise ValueError(f"circuit line {line_number}: invalid destination {lhs!r}")

        if "&" in rhs or "|" in rhs:
            if "^" in rhs or ("&" in rhs and "|" in rhs):
                raise ValueError(f"circuit line {line_number}: mixed expression {rhs!r}")
            operator = "&" if "&" in rhs else "|"
            operands = [piece.strip() for piece in rhs.split(operator)]
            if len(operands) != 2:
                raise ValueError(f"circuit line {line_number}: non-binary nonlinear gate")
            for operand in operands:
                if not VALUE_RE.fullmatch(operand) or operand not in gate_depth:
                    raise ValueError(f"circuit line {line_number}: unavailable operand {operand!r}")
            counts["and_gates" if operator == "&" else "or_gates"] += 1
            gate_depth[lhs] = max(gate_depth[value] for value in operands) + 1
            and_depth[lhs] = max(and_depth[value] for value in operands) + 1
            continue

        terms = [piece.strip() for piece in rhs.split("^")]
        for term in terms:
            if not VALUE_RE.fullmatch(term):
                raise ValueError(f"circuit line {line_number}: invalid affine term {term!r}")
        phase = sum(term == "1" for term in terms) & 1
        operands = [term for term in terms if term not in {"0", "1"}]
        for operand in operands:
            if operand not in gate_depth:
                raise ValueError(f"circuit line {line_number}: unavailable operand {operand!r}")
        if not operands:
            gate_depth[lhs] = 0
            and_depth[lhs] = 0
            counts["copies"] += 1
        elif len(operands) == 1:
            gate_depth[lhs] = gate_depth[operands[0]] + phase
            and_depth[lhs] = and_depth[operands[0]]
            counts["not_gates" if phase else "copies"] += 1
        elif len(operands) == 2:
            gate_depth[lhs] = max(gate_depth[value] for value in operands) + 1
            and_depth[lhs] = max(and_depth[value] for value in operands)
            counts["xor_xnor_gates"] += 1
        else:
            raise ValueError(
                f"circuit line {line_number}: expected normalized binary XOR/XNOR"
            )

    outputs = [f"y[{index}]" for index in range(8)]
    missing = [output for output in outputs if output not in gate_depth]
    if missing:
        raise ValueError(f"missing outputs: {missing}")
    phase_metrics = phase_normalization_metrics(parts[1])
    return {
        **counts,
        "nonlinear_gates": counts["and_gates"] + counts["or_gates"],
        "affine_gates_including_not": counts["xor_xnor_gates"] + counts["not_gates"],
        "normalized_affine_gates": counts["xor_xnor_gates"]
        + phase_metrics["phase_not_gates_after_absorption"],
        "total_gates": counts["and_gates"]
        + counts["or_gates"]
        + counts["xor_xnor_gates"]
        + counts["not_gates"],
        "normalized_total_gates": counts["and_gates"]
        + counts["or_gates"]
        + counts["xor_xnor_gates"]
        + phase_metrics["phase_not_gates_after_absorption"],
        "depth": max(gate_depth[output] for output in outputs),
        "and_depth": max(and_depth[output] for output in outputs),
        **phase_metrics,
    }


def phase_normalization_metrics(body: str) -> dict[str, int]:
    next_origin = 0
    labels: dict[str, tuple[int, int]] = {}
    kinds: dict[int, str] = {}
    demands: dict[int, set[int]] = {}

    def new_origin(kind: str) -> int:
        nonlocal next_origin
        origin = next_origin
        next_origin += 1
        kinds[origin] = kind
        demands[origin] = set()
        return origin

    for index in range(8):
        labels[f"x[{index}]"] = (new_origin("fixed"), 0)

    for raw in body.splitlines():
        line = raw.strip().rstrip(";")
        if not line or line.startswith("#") or "=" not in line:
            continue
        lhs, rhs = (piece.strip() for piece in line.split("=", 1))
        if rhs.startswith("[0]"):
            continue
        if "&" in rhs or "|" in rhs:
            operator = "&" if "&" in rhs else "|"
            operands = [piece.strip() for piece in rhs.split(operator)]
            for operand in operands:
                origin, phase = labels[operand]
                demands[origin].add(phase)
            labels[lhs] = (new_origin("fixed"), 0)
        else:
            terms = [piece.strip() for piece in rhs.split("^")]
            phase = sum(term == "1" for term in terms) & 1
            operands = [term for term in terms if term not in {"0", "1"}]
            if len(operands) == 1:
                origin, operand_phase = labels[operands[0]]
                desired_phase = operand_phase ^ phase
                labels[lhs] = (origin, desired_phase)
            elif len(operands) == 2:
                labels[lhs] = (new_origin("xor"), 0)
            elif not operands:
                labels[lhs] = (new_origin("fixed"), phase)
            else:
                raise ValueError("phase audit requires normalized binary XOR/XNOR")
        # XOR/XNOR consumers absorb either input polarity in their own gate
        # phase, so only nonlinear inputs and direct primary outputs constrain
        # the physical polarity of an affine origin.
        if lhs.startswith("y["):
            origin, output_phase = labels[lhs]
            demands[origin].add(output_phase)

    extra = 0
    conflicting_xor_origins = 0
    complemented_fixed_origins = 0
    for origin, phases in demands.items():
        if kinds[origin] == "xor":
            if phases == {0, 1}:
                extra += 1
                conflicting_xor_origins += 1
        elif 1 in phases:
            extra += 1
            complemented_fixed_origins += 1
    return {
        "phase_not_gates_after_absorption": extra,
        "conflicting_xor_polarities": conflicting_xor_origins,
        "complemented_fixed_polarities": complemented_fixed_origins,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("result", type=Path)
    args = parser.parse_args()
    data = args.result.read_bytes()
    sbox = load_sbox(args.result)
    report = {
        "schema_version": 1,
        "source": str(args.result.resolve()),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "sbox_sha256": hashlib.sha256(bytes(sbox)).hexdigest(),
        "exhaustive_inputs": 256,
        "equivalent_to_aes_sbox": True,
        **parse_metrics(args.result),
    }
    print(json.dumps(report, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
