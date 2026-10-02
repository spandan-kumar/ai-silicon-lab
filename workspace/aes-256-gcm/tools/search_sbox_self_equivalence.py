#!/usr/bin/env python3
"""Bounded AES self-equivalence boundary sweep; heuristic costs, not optima."""

from __future__ import annotations

import argparse
from collections import Counter
import itertools
import json
from pathlib import Path
import time

from benchmark_sbox_circuits import CIRCUITS, load_sbox, parse_slp, sha256_file


def mul(a: int, b: int) -> int:
    result = 0
    while b:
        if b & 1:
            result ^= a
        a <<= 1
        if a & 256:
            a ^= 0x11B
        b >>= 1
    return result


def frobenius(value: int, count: int) -> int:
    for _ in range(count % 8):
        value = mul(value, value)
    return value


def linear(value: int) -> int:
    result = value
    for shift in range(1, 5):
        result ^= ((value << shift) | (value >> (8 - shift))) & 255
    return result


INVERSE_LINEAR = {linear(value): value for value in range(256)}


def transforms(a: int, k: int) -> tuple[list[int], list[int]]:
    before = [mul(a, frobenius(value, k)) for value in range(256)]
    after = [linear(frobenius(mul(a, INVERSE_LINEAR[value ^ 0x63]), 8 - k)) ^ 0x63
             for value in range(256)]
    return before, after


def affine_rows(table: list[int]) -> tuple[list[int], list[int]]:
    """Rows use bit i for MSB-first input U_i; constants are separate."""
    constant = table[0]
    rows = [sum(((table[1 << (7 - j)] ^ constant) >> (7 - i) & 1) << j
                for j in range(8)) for i in range(8)]
    for value in range(256):
        bits = sum(((value >> (7 - i)) & 1) << i for i in range(8))
        reconstructed = sum((((row & bits).bit_count() & 1) ^ (constant >> (7 - i) & 1))
                            << (7 - i) for i, row in enumerate(rows))
        if reconstructed != table[value]:
            raise ValueError("transformation is not affine")
    return rows, [(constant >> (7 - i)) & 1 for i in range(8)]


class Emitter:
    def __init__(self):
        self.operations = []
        self.zero = None

    def gate(self, operation, left, right):
        output = f"w{len(self.operations)}"
        self.operations.append((operation, output, left, right))
        return output

    def constant_zero(self):
        if self.zero is None:
            self.zero = self.gate("XOR", "U0", "U0")
        return self.zero


def synthesize(emitter, sources, targets):
    """Deterministic common-pair factoring with explicit constant costs.

    This is an upper-bound heuristic. Sources are named available wires, not
    a free change of basis. Complements cost a gate unless absorbed by XOR.
    """
    terms = [{i for i in range(len(sources)) if mask >> i & 1} for mask, _ in targets]
    wires = list(sources)
    while any(len(term) > 1 for term in terms):
        counts = Counter(pair for term in terms for pair in itertools.combinations(sorted(term), 2))
        left, right = min(counts, key=lambda pair: (-counts[pair], pair))
        output = emitter.gate("XOR", wires[left], wires[right])
        index = len(wires)
        wires.append(output)
        for term in terms:
            if left in term and right in term:
                term.difference_update((left, right))
                term.add(index)
    result = []
    # Complements are initially explicit and then absorbed only when the
    # producer has no other consumers, preserving all fanout semantics.
    for term, (_, phase) in zip(terms, targets):
        wire = wires[next(iter(term))] if term else emitter.constant_zero()
        if phase:
            wire = emitter.gate("XNOR", wire, emitter.constant_zero())
        result.append(wire)
    return result


def symbolic(operations, sources):
    values = {name: (1 << index, 0) for index, name in enumerate(sources)}
    for operation, output, left, right in operations:
        if operation not in {"XOR", "XNOR"}:
            raise ValueError("non-affine boundary")
        a, ap = values[left]
        b, bp = values[right]
        values[output] = (a ^ b, ap ^ bp ^ (operation == "XNOR"))
    return values


def compose(rows, phases, values):
    result = []
    for row, phase in zip(rows, phases):
        mask = 0
        for index, (value, value_phase) in enumerate(values):
            if row >> index & 1:
                mask ^= value
                phase ^= value_phase
        result.append((mask, phase))
    return result


def prefix_lower_bound(targets):
    """Necessary gate bound, ignoring phases but never giving Ax for free."""
    available = {1 << i for i in range(8)}
    remaining = {mask for mask, _ in targets} - available - {0}
    count = len(remaining)
    # At this count, every new gate must be a required target: there is no
    # budget for an auxiliary form. Failure of target-only closure proves
    # at least one auxiliary gate is necessary. Passing does not claim
    # phase-correct achievability.
    while remaining:
        reached = {target for target in remaining
                   if any((target ^ source) in available for source in available)}
        if not reached:
            return count + 1
        available.update(reached)
        remaining.difference_update(reached)
    return count


def simplify(operations, outputs):
    """Absorb a single-use complement into its XOR/XNOR producer; remove dead gates."""
    uses = Counter(outputs)
    uses.update(wire for _, _, left, right in operations for wire in (left, right))
    producers = {output: (operation, left, right) for operation, output, left, right in operations}
    replacements = {}
    for operation, output, left, right in operations:
        zero = producers.get(right)
        producer = producers.get(left)
        if (operation == "XNOR" and zero and zero[0] == "XOR" and zero[1] == zero[2]
                and producer and producer[0] in {"XOR", "XNOR"} and uses[left] == 1):
            replacements[output] = ("XNOR" if producer[0] == "XOR" else "XOR", output,
                                    producer[1], producer[2])
    changed = [replacements.get(output, (operation, output, left, right))
               for operation, output, left, right in operations]
    required = set(outputs)
    retained = []
    for operation, output, left, right in reversed(changed):
        if output in required:
            retained.append((operation, output, left, right))
            required.update((left, right))
    return list(reversed(retained))


def evaluate_all(operations, outputs):
    """Evaluate all 256 inputs simultaneously as independently indexed truth bits."""
    universe = (1 << 256) - 1
    values = {f"U{i}": sum(((x >> (7 - i)) & 1) << x for x in range(256)) for i in range(8)}
    for operation, output, left, right in operations:
        if operation == "AND":
            values[output] = values[left] & values[right]
        else:
            values[output] = values[left] ^ values[right]
            if operation == "XNOR":
                values[output] ^= universe
    return [sum(((values[name] >> x) & 1) << (7 - i) for i, name in enumerate(outputs))
            for x in range(256)]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--circuit", choices=CIRCUITS, default="a29-ad6-g138-d38")
    parser.add_argument("--output", type=Path, required=True, help="new evidence directory")
    parser.add_argument("--limit", type=int, default=2040, help="first N (k,a) pairs; default entire orbit")
    parser.add_argument("--heuristic", choices=("common-pair", "distance"), default="common-pair")
    args = parser.parse_args()
    if not 1 <= args.limit <= 2040:
        parser.error("--limit must be between 1 and 2040")
    if args.output.exists():
        parser.error("output directory must be new")
    synthesizer = synthesize
    backend_sha256 = None
    if args.heuristic == "distance":
        import xor_distance_heuristic as backend
        synthesizer = backend.synthesize
        backend_sha256 = sha256_file(Path(backend.__file__))
    metadata = CIRCUITS[args.circuit]
    if sha256_file(args.source) != metadata["sha256"]:
        parser.error("source does not match the named pinned circuit")
    operations = parse_slp(args.source, metadata["gates"])
    and_indices = [i for i, gate in enumerate(operations) if gate[0] == "AND"]
    first, last = and_indices[0], and_indices[-1]
    prefix, middle, suffix = operations[:first], operations[first:last + 1], operations[last + 1:]
    inputs = [f"U{i}" for i in range(8)]
    prefix_values = symbolic(prefix, inputs)
    middle_defined = {gate[1] for gate in middle}
    boundary_in = sorted({name for _, _, left, right in middle + suffix for name in (left, right)
                          if name in prefix_values})
    suffix_defined = {gate[1] for gate in suffix}
    boundary_out = sorted({name for _, _, left, right in suffix for name in (left, right)
                           if name not in suffix_defined})
    if not set(boundary_out) <= set(boundary_in) | middle_defined:
        raise ValueError("tail uses an unavailable signal")
    suffix_values = symbolic(suffix, boundary_out)
    oracle = list(load_sbox())
    original_outputs = [f"S{i}" for i in range(8)]
    if evaluate_all(operations, original_outputs) != oracle:
        raise ValueError("pinned source differs from the independent AES oracle")
    started = time.monotonic()
    rows = []
    best = None
    args.output.mkdir(parents=True)
    for k, a in itertools.islice(itertools.product(range(8), range(1, 256)), args.limit):
        before, after = transforms(a, k)
        if any(after[oracle[before[x]]] != oracle[x] for x in range(256)):
            raise ValueError(f"invalid self-equivalence a={a}, k={k}")
        input_rows, input_phases = affine_rows(before)
        output_rows, output_phases = affine_rows(after)
        emitter = Emitter()
        head_targets = compose([prefix_values[name][0] for name in boundary_in],
                               [prefix_values[name][1] for name in boundary_in],
                               list(zip(input_rows, input_phases)))
        names = dict(zip(boundary_in, synthesizer(emitter, inputs, head_targets)))
        middle_names = set()
        for operation, output, left, right in middle:
            names[output] = emitter.gate(operation, names[left], names[right])
            middle_names.add(names[output])
        tail_targets = compose(output_rows, output_phases,
                               [suffix_values[name] for name in original_outputs])
        outputs = synthesizer(emitter, [names[name] for name in boundary_out], tail_targets)
        candidate = simplify(emitter.operations, outputs)
        if not middle_names <= {gate[1] for gate in candidate}:
            raise ValueError("candidate violates the fixed-middle retention constraint")
        if evaluate_all(candidate, outputs) != oracle:
            raise ValueError(f"emitted candidate fails exhaustive check a={a}, k={k}")
        nonlinear = sum(gate[0] == "AND" for gate in candidate)
        if nonlinear != 29:
            raise ValueError(f"expected exactly 29 retained ANDs, found {nonlinear}")
        result = {"a": a, "k": k, "and_gates": nonlinear,
                  "affine_gates": len(candidate) - nonlinear, "total_gates": len(candidate),
                  "prefix_gate_lower_bound": prefix_lower_bound(head_targets),
                  "functional_inputs_checked": 256}
        rows.append(result)
        if best is None or result["total_gates"] < best["total_gates"]:
            best = result
            (args.output / "best-circuit.json").write_text(json.dumps(
                {**result, "operations": candidate, "outputs": outputs}, indent=2) + "\n")
            print(json.dumps({"progress": len(rows), "best": best}), flush=True)
    report = {
        "circuit": args.circuit, "source_sha256": sha256_file(args.source),
        "script_sha256": sha256_file(Path(__file__)),
        "heuristic": args.heuristic,
        "backend_sha256": backend_sha256,
        "source_gates": len(operations), "source_affine_gates": len(operations) - 29,
        "retained_middle_gates": len(middle), "prefix_live_outputs": boundary_in,
        "suffix_available_inputs": boundary_out, "pairs_checked": len(rows),
        "identity_and_emitted_circuit_inputs_checked": len(rows) * 256,
        "elapsed_seconds": time.monotonic() - started,
        "best": best, "results": rows,
        "claim": "Deterministic heuristic boundary synthesis upper bounds only. Original middle retained. Prefix bounds are necessary, not whole-circuit optima. No physical, masking-security, or novelty claim.",
    }
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps({key: value for key, value in report.items() if key != "results"}), flush=True)


if __name__ == "__main__":
    main()
