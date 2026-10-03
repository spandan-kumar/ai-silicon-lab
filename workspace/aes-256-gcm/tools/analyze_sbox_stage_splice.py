#!/usr/bin/env python3
"""Verify restricted six-AND lower bounds for three public AES middle stages.

The nine early gates and thirteen tail gates with their operand functions are
fixed. Check both norm-only middle circuits and middle circuits allowed to use
all early signals. These arguments do not bound changed early/tail gates or
refactored tail operand functions.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import time

from benchmark_sbox_circuits import load_sbox, parse_slp, sha256_file
from search_sbox_self_equivalence import mul

ALL = (1 << 256) - 1
INPUTS = [sum(((x >> (7-i)) & 1) << x for x in range(256)) for i in range(8)]
SOURCES = {
    "aes-sbox-a28-ad4-g131-gd32-xx103-47.circ.txt": (131, "9e6c8dbed90aab60b19587c9a281f7962813b8557aac6c3a7498bc454a8c48bb"),
    "aes-sbox-a28-ad4-g141-gd16-xx113-27.circ.txt": (141, "2539f43e53e7326eaddc021c734aaea429fcd4f837f4f9d8bc6eaad77e5f31f8"),
    "aes-sbox-a28-ad4-g177-gd14-xx149-24.circ.txt": (177, "7bc3b4fd1cef2bdae4bdbe12b582efdec3447e7abbe7aa224b8d0594af4d9746"),
}


class Span:
    """Gaussian elimination of truth vectors, retaining input coefficients."""
    def __init__(self, vectors=()):
        self.rows = {}
        for index, vector in enumerate(vectors):
            residual, mask = self.reduce(vector)
            if residual:
                self.rows[residual.bit_length()-1] = (residual, mask ^ (1 << index))

    def reduce(self, vector):
        mask = 0
        for pivot in sorted(self.rows, reverse=True):
            if vector >> pivot & 1:
                value, coefficients = self.rows[pivot]
                vector ^= value
                mask ^= coefficients
        return vector, mask

    def rank(self):
        return len(self.rows)


def power(x, exponent):
    result = 1
    while exponent:
        if exponent & 1:
            result = mul(result, x)
        x = mul(x, x)
        exponent >>= 1
    return result


def independent(vectors):
    result = []
    for vector in vectors:
        if Span(result).reduce(vector)[0]:
            result.append(vector)
    return result


def all_forms(vectors):
    result = [0]
    for vector in vectors:
        result += [value ^ vector for value in result]
    return result


def anf(truth):
    """Exact Boolean Mobius transform, indexed by the eight input byte bits."""
    coefficients = [(truth >> x) & 1 for x in range(256)]
    for bit in range(8):
        for mask in range(256):
            if mask >> bit & 1:
                coefficients[mask] ^= coefficients[mask ^ (1 << bit)]
    return sum(value << mask for mask, value in enumerate(coefficients))


def combine(vectors, mask):
    value = 0
    for index, vector in enumerate(vectors):
        if mask >> index & 1:
            value ^= vector
    return value


def first_product_search(initial, target):
    """Exhaust one affine factor, solving exactly for the other modulo initial."""
    quotient = Span(initial)
    assert initial[0] == ALL and quotient.rank() == len(initial) == 18
    vectors = initial[1:]
    products = [[quotient.reduce(a & b)[0] for b in vectors] for a in vectors]
    images = [0] * len(vectors)
    previous = 0
    started = time.monotonic()
    for step in range(1, 1 << len(vectors)):
        gray = step ^ (step >> 1)
        changed = (gray ^ previous).bit_length() - 1
        previous = gray
        images = [value ^ addition for value, addition in zip(images, products[changed])]
        # Pivot-chasing avoids scanning all 256 possible truth coordinates.
        rows = {}
        for index, value in enumerate(images):
            mask = 1 << index
            while value:
                pivot = value.bit_length() - 1
                if pivot not in rows:
                    rows[pivot] = (value, mask)
                    break
                row, coefficient = rows[pivot]
                value ^= row
                mask ^= coefficient
        residual, right_mask = target, 0
        while residual and residual.bit_length()-1 in rows:
            row, coefficient = rows[residual.bit_length()-1]
            residual ^= row
            right_mask ^= coefficient
        if not residual:
            left, right = combine(vectors, gray), combine(vectors, right_mask)
            assert quotient.reduce(left & right)[0] == target
            return {"status": "satisfiable", "forms_checked": step,
                    "left_truth": hex(left), "right_truth": hex(right),
                    "elapsed_seconds": time.monotonic() - started}
    return {"status": "exhausted-no-product", "forms_checked": (1 << len(vectors))-1,
            "elapsed_seconds": time.monotonic() - started}


def general_middle_bound(initial, operands, tail, outputs):
    """Degree and dimension obstruction when all early signals are available."""
    required_operands = independent(initial + operands)
    base = independent(required_operands + tail)
    full = independent(base + outputs)
    assert (len(initial), len(required_operands), len(base), len(full)) == (18, 22, 35, 36)
    high = sum(1 << mask for mask in range(256) if mask.bit_count() > 4)
    assert all(not (anf(value) & high) for value in initial)
    images, low_degree = [], []
    for value in full:
        image = anf(value) & high
        residual, mask = Span(images).reduce(image)
        if not residual:
            witness = value ^ combine(full[:len(images)], mask)
            assert not (anf(witness) & high)
            low_degree.append(witness)
        images.append(image)
    low_degree = independent(low_degree)
    assert len(low_degree) == len(full) - Span(images).rank() == 19
    assert all(Span(low_degree).reduce(value)[0] == 0 for value in initial)
    quotient = Span(initial)
    target = next(quotient.reduce(value)[0] for value in low_degree if quotient.reduce(value)[0])
    result = first_product_search(initial, target)
    assert result["status"] == "exhausted-no-product"
    return {"initial_rank": 18, "required_operand_span_rank": 22,
            "operand_and_tail_span_rank": 35, "operand_tail_output_span_rank": 36,
            "degree_at_most_four_subspace_rank": 19, "first_product_target": hex(target),
            "first_product_search": result, "minimum_middle_ands": 6,
            "scope": "Middle may use all raw inputs and nine early AND outputs; original thirteen tail operand truth functions remain fixed."}


def analyze(source, expected_count, norm_bits, inverse_bits, indicators, labels):
    operations = parse_slp(source, expected_count)
    values = dict(zip((f"U{i}" for i in range(8)), INPUTS))
    depths = {name: 0 for name in values}
    nonlinear = []
    for operation, output, left, right in operations:
        a, b = values[left], values[right]
        values[output] = a & b if operation == "AND" else a ^ b ^ (ALL if operation == "XNOR" else 0)
        depths[output] = max(depths[left], depths[right]) + (operation == "AND")
        if operation == "AND":
            nonlinear.append((depths[output], values[output], a, b))
    outputs = [values[f"S{i}"] for i in range(8)]
    actual = [sum(((truth >> x) & 1) << (7-i) for i, truth in enumerate(outputs)) for x in range(256)]
    assert actual == list(load_sbox())
    early = [truth for depth, truth, _, _ in nonlinear if depth == 1]
    middle = [truth for depth, truth, _, _ in nonlinear if 1 < depth < 4]
    tail = [truth for depth, truth, _, _ in nonlinear if depth == 4]
    operands = [truth for depth, _, a, b in nonlinear if depth == 4 for truth in (a, b)]
    assert (len(early), len(middle), len(tail)) == (9, 6, 13)
    norm_functions = Span(indicators)
    assert norm_functions.rank() == 16
    assert all(norm_functions.reduce(truth)[0] == 0 for truth in middle)

    affine_norm = [ALL] + norm_bits
    initial = [ALL] + INPUTS + early
    initial_span = Span(initial)
    assert all(initial_span.reduce(v)[0] == 0 for v in affine_norm)
    initial_norm_intersection = 16 - Span([initial_span.reduce(v)[0] for v in indicators]).rank()
    assert initial_norm_intersection == 5
    # The original six gates also admit a construction using only norm bits.
    middle_available = list(affine_norm)
    for depth, truth, left, right in nonlinear:
        if 1 < depth < 4:
            assert all(Span(middle_available).reduce(v)[0] == 0 for v in (left, right))
            middle_available.append(truth)
    # The required tail operand span adds exactly the four inverse coordinates.
    operand_span = Span(initial + operands)
    inverse_span = Span(initial + inverse_bits)
    assert operand_span.rank() == inverse_span.rank() == initial_span.rank() + 4
    assert all(operand_span.reduce(v)[0] == 0 for v in inverse_bits)
    assert all(inverse_span.reduce(v)[0] == 0 for v in operands)

    base = initial + tail + inverse_bits
    base_span = Span(base)
    projected_norm = [base_span.reduce(v)[0] for v in indicators]
    intersection_rank = 16 - Span(projected_norm).rank()
    norm_inverse_span = Span(affine_norm + inverse_bits)
    assert intersection_rank == norm_inverse_span.rank() == 9
    assert all(base_span.reduce(v)[0] == 0 for v in affine_norm + inverse_bits)
    residuals = [base_span.reduce(v)[0] for v in outputs]
    assert Span(residuals).rank() == 1
    target = next(v for v in residuals if v)
    residual, mask = Span(projected_norm).reduce(target)
    assert residual == 0
    needed = 0
    for index, truth in enumerate(indicators):
        if mask >> index & 1:
            needed ^= truth
    assert base_span.reduce(needed)[0] == target

    required = affine_norm + inverse_bits + [needed]
    required_span = Span(required)
    assert required_span.rank() == 10
    assert all(Span(base + [needed]).reduce(v)[0] == 0 for v in outputs)
    affine = all_forms(affine_norm)
    affine_span = Span(affine_norm)
    assert len(affine) == len(set(affine)) == 32
    qualifying = {a & b for a in affine for b in affine
                  if affine_span.reduce(a & b)[0] and not required_span.reduce(a & b)[0]}
    assert not qualifying

    def collapse(truth):
        result = 0
        for label in range(16):
            bits = {(truth >> x) & 1 for x in range(256) if labels[x] == label}
            assert len(bits) == 1
            result |= bits.pop() << label
        return result

    return {
        "source": source.name, "source_sha256": sha256_file(source), "source_inputs_verified": 256,
        "initial_span_rank": initial_span.rank(), "required_tail_operand_extension_rank": 4,
        "initial_norm_function_intersection_rank": initial_norm_intersection,
        "base_span_rank": base_span.rank(), "norm_function_intersection_rank": intersection_rank,
        "missing_output_rank": 1, "required_middle_span_rank": 10, "affine_norm_rank": 5,
        "required_function_16bit_truth": hex(collapse(needed)),
        "required_span_16bit_generators": [hex(collapse(v)) for v in required],
        "first_gate_operand_pairs_checked": 1024, "non_affine_first_products_in_required_span": len(qualifying),
        "minimum_middle_ands_lower_bound": 6, "existing_middle_ands": 6,
        "existing_six_and_middle_realizable_from_norm_bits": True,
        "fixed_early_and_tail_total_and_lower_bound": 28,
        "all_early_signals_middle": general_middle_bound(initial, operands, tail, outputs),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("output must be new")
    norm = [power(x, 17) for x in range(256)]
    inverse = [power(x, 254) for x in norm]
    norm_bits = independent([sum(((value >> bit) & 1) << x for x, value in enumerate(norm)) for bit in range(8)])
    inverse_bits = independent([sum(((value >> bit) & 1) << x for x, value in enumerate(inverse)) for bit in range(8)])
    assert len(norm_bits) == len(inverse_bits) == 4
    labels = [sum(((truth >> x) & 1) << i for i, truth in enumerate(norm_bits)) for x in range(256)]
    assert len(set(labels)) == 16
    indicators = [sum((label == i) << x for x, label in enumerate(labels)) for i in range(16)]
    cases = []
    for filename, (count, digest) in SOURCES.items():
        source = args.source_dir / filename
        if sha256_file(source) != digest:
            parser.error(f"pinned source hash mismatch: {filename}")
        cases.append(analyze(source, count, norm_bits, inverse_bits, indicators, labels))
    report = {
        "status": "restricted-lower-bound-verified", "world_first_established": False,
        "cases": cases, "script_sha256": sha256_file(Path(__file__)),
        "oracle_sha256": hashlib.sha256(bytes(load_sbox())).hexdigest(),
        "field_modulus": "0x11b", "norm": "x^17", "zero_inverse": 0,
        "argument": "The tail operands require all four inverse-norm coordinates. Completing the outputs additionally requires one independent norm function modulo those coordinates and affine norm functions. Their span has dimension 10, versus affine-input dimension 5. With only five ANDs, every new AND output must lie in this required span. Exhausting all 32x32 affine operand pairs finds no non-affine first AND in that span. Therefore at least six middle ANDs are necessary.",
        "all_early_signals_argument": "Let A span the 18 initial functions and M span A plus at most five middle AND outputs, so dim(M)<=23. Required tail operands lie in M. Together with the 13 fixed tail outputs and AES outputs these span V of dimension36. Thus V is contained in M+tail, whose dimension is at most36, forcing equality and M contained in V. The first useful middle AND has degree at most4. The degree<=4 subspace of V extends A by exactly one dimension. Exhausting every nonconstant left form in A and solving the right form over A excludes that sole direction; at least six middle ANDs are needed.",
        "scope": "Three pinned circuits; fixed nine early gates and thirteen tail gates with their original operand truth functions. Both norm-only and all-early-signals replacement middles are checked. Does not bound refactored tail operands, changed outer gates, interleaved middle/tail computation, or general AES S-box circuits. No physical or novelty claim.",
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
