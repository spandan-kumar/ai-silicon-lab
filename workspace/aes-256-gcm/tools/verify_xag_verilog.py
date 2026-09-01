#!/usr/bin/env python3
"""Independently verify and phase-normalize a mockturtle XAG Verilog file."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
ASSIGN_RE = re.compile(r"^assign\s+(\w+)\s*=\s*(.+);$")
VALUE_RE = re.compile(r"^(~)?(\w+)$")


class ParityUnionFind:
    def __init__(self) -> None:
        self.parent: list[int] = []
        self.rank: list[int] = []
        self.parity: list[int] = []

    def add(self) -> int:
        index = len(self.parent)
        self.parent.append(index)
        self.rank.append(0)
        self.parity.append(0)
        return index

    def find(self, item: int) -> tuple[int, int]:
        if self.parent[item] == item:
            return item, 0
        root, above = self.find(self.parent[item])
        self.parity[item] ^= above
        self.parent[item] = root
        return root, self.parity[item]

    def constrain(self, left: int, right: int, parity: int) -> bool:
        left_root, left_phase = self.find(left)
        right_root, right_phase = self.find(right)
        if left_root == right_root:
            return (left_phase ^ right_phase) == parity
        if self.rank[left_root] < self.rank[right_root]:
            left_root, right_root = right_root, left_root
            left_phase, right_phase = right_phase, left_phase
        self.parent[right_root] = left_root
        self.parity[right_root] = left_phase ^ right_phase ^ parity
        if self.rank[left_root] == self.rank[right_root]:
            self.rank[left_root] += 1
        return True


def load_reference() -> tuple[int, ...]:
    path = ROOT / "reference" / "aes_gcm.py"
    spec = importlib.util.spec_from_file_location("aes_reference", path)
    if spec is None or spec.loader is None:
        raise ValueError("cannot load AES reference")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(module.SBOX)


def parse_value(text: str) -> tuple[str, int]:
    match = VALUE_RE.fullmatch(text.strip())
    if not match:
        raise ValueError(f"unsupported value {text!r}")
    return match.group(2), int(match.group(1) is not None)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("verilog", type=Path)
    args = parser.parse_args()

    data = args.verilog.read_bytes()
    inputs = [f"x{i}" for i in range(8)]
    outputs = [f"y{i}" for i in range(8)]
    operations: list[tuple[str, str, tuple[str, int], tuple[str, int] | None]] = []
    for raw in data.decode().splitlines():
        line = raw.strip()
        if not (match := ASSIGN_RE.fullmatch(line)):
            continue
        lhs, rhs = match.groups()
        if " ^ " in rhs:
            left, right = rhs.split(" ^ ")
            operations.append((lhs, "XOR", parse_value(left), parse_value(right)))
        elif " & " in rhs:
            left, right = rhs.split(" & ")
            operations.append((lhs, "AND", parse_value(left), parse_value(right)))
        else:
            operations.append((lhs, "COPY", parse_value(rhs), None))

    values: dict[str, int] = {}
    gate_depth = {name: 0 for name in inputs}
    and_depth = dict(gate_depth)
    gate_counts = {"AND": 0, "XOR": 0, "COPY": 0}
    for name in inputs:
        values[name] = 0
    for lhs, operation, left, right in operations:
        if left[0] not in values or (right is not None and right[0] not in values):
            raise ValueError(f"{lhs} uses an unavailable signal")
        gate_counts[operation] += 1
        if operation == "COPY":
            values[lhs] = values[left[0]] ^ left[1]
            gate_depth[lhs] = gate_depth[left[0]]
            and_depth[lhs] = and_depth[left[0]]
        elif operation == "XOR":
            assert right is not None
            values[lhs] = values[left[0]] ^ values[right[0]] ^ left[1] ^ right[1]
            gate_depth[lhs] = max(gate_depth[left[0]], gate_depth[right[0]]) + 1
            and_depth[lhs] = max(and_depth[left[0]], and_depth[right[0]])
        else:
            assert right is not None
            values[lhs] = (values[left[0]] ^ left[1]) & (values[right[0]] ^ right[1])
            gate_depth[lhs] = max(gate_depth[left[0]], gate_depth[right[0]]) + 1
            and_depth[lhs] = max(and_depth[left[0]], and_depth[right[0]]) + 1

    if any(output not in values for output in outputs):
        raise ValueError("missing one or more outputs")

    reference = load_reference()
    mismatches: list[int] = []
    for input_value in range(256):
        simulation = {f"x{i}": (input_value >> (7 - i)) & 1 for i in range(8)}
        for lhs, operation, left, right in operations:
            left_value = simulation[left[0]] ^ left[1]
            if operation == "COPY":
                simulation[lhs] = left_value
            else:
                assert right is not None
                right_value = simulation[right[0]] ^ right[1]
                simulation[lhs] = (
                    left_value ^ right_value
                    if operation == "XOR"
                    else left_value & right_value
                )
        output_value = sum(simulation[f"y{i}"] << (7 - i) for i in range(8))
        if output_value != reference[input_value]:
            mismatches.append(input_value)

    uf = ParityUnionFind()
    phase_variables = {name: uf.add() for name in values}
    constant = uf.add()
    consistent = True
    for name in inputs:
        consistent &= uf.constrain(phase_variables[name], constant, 0)
    for lhs, operation, left, right in operations:
        if operation == "AND":
            assert right is not None
            consistent &= uf.constrain(
                phase_variables[left[0]], phase_variables[lhs], left[1]
            )
            consistent &= uf.constrain(
                phase_variables[right[0]], phase_variables[lhs], right[1]
            )
        elif operation == "COPY" and lhs in outputs:
            consistent &= uf.constrain(
                phase_variables[left[0]], constant, left[1]
            )

    phase_assignment: dict[str, int] = {}
    constant_root, constant_phase = uf.find(constant)
    for name, variable in phase_variables.items():
        root, phase = uf.find(variable)
        phase_assignment[name] = phase ^ constant_phase if root == constant_root else phase

    normalized_types = {"AND": 0, "OR": 0, "XOR": 0, "XNOR": 0}
    if consistent:
        for lhs, operation, left, right in operations:
            if operation == "XOR":
                assert right is not None
                gate_phase = (
                    phase_assignment[lhs]
                    ^ phase_assignment[left[0]]
                    ^ phase_assignment[right[0]]
                    ^ left[1]
                    ^ right[1]
                )
                normalized_types["XNOR" if gate_phase else "XOR"] += 1
            elif operation == "AND":
                normalized_types["OR" if phase_assignment[lhs] else "AND"] += 1

    report = {
        "schema_version": 1,
        "source": str(args.verilog.resolve()),
        "source_sha256": hashlib.sha256(data).hexdigest(),
        "exhaustive_inputs": 256,
        "equivalent_to_aes_sbox": not mismatches,
        "mismatch_inputs": mismatches[:16],
        "raw_and_gates": gate_counts["AND"],
        "raw_xor_gates": gate_counts["XOR"],
        "output_copies": gate_counts["COPY"],
        "phase_normalization_possible": consistent,
        "normalized_gate_types": normalized_types,
        "normalized_nonlinear_gates": normalized_types["AND"] + normalized_types["OR"],
        "normalized_affine_gates": normalized_types["XOR"] + normalized_types["XNOR"],
        "normalized_total_gates": sum(normalized_types.values()),
        "gate_depth": max(gate_depth[output] for output in outputs),
        "and_depth": max(and_depth[output] for output in outputs),
    }
    print(json.dumps(report, indent=2, sort_keys=True))
    if mismatches or not consistent:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
