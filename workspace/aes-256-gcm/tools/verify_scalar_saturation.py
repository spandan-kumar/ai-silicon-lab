"""Finite controls for the raw-input-saturated optimal scalar lemma.

Truth-table reconstruction, not the production high-quotient scanner.
The lemma itself is an induction, not inferred from these finite controls.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import random
import time


def xor_select(rows, mask):
    result = 0
    for i, row in enumerate(rows):
        if mask >> i & 1:
            result ^= row
    return result


def rank(rows):
    pivots = {}
    for value in rows:
        while value:
            pivot = value.bit_length()-1
            if pivot not in pivots:
                pivots[pivot] = value
                break
            value ^= pivots[pivot]
    return len(pivots)


def table_data(width):
    raw = [sum(((point >> j) & 1) << point for point in range(1 << width))
           for j in range(width)]
    pairs = list(itertools.combinations(range(width), 2))
    monomials = [raw[i] & raw[j] for i, j in pairs]
    return raw, pairs, monomials


def quadratic_rank(value, raw, pairs, monomials):
    constant = value & 1
    predicted = ((1 << (1 << len(raw)))-1) if constant else 0
    linear = [((value >> (1 << i)) & 1) ^ constant for i in range(len(raw))]
    for i, bit in enumerate(linear):
        if bit:
            predicted ^= raw[i]
    rows = [0]*len(raw)
    for k, (i, j) in enumerate(pairs):
        bit = ((value >> ((1 << i) | (1 << j))) & 1) ^ constant ^ linear[i] ^ linear[j]
        if bit:
            predicted ^= monomials[k]
            rows[i] ^= 1 << j
            rows[j] ^= 1 << i
    return rank(rows) if value == predicted else None


def gates(raw, code, constants):
    old = []
    all_ones = (1 << (1 << len(raw)))-1
    for i in range(len(raw)//2):
        mask = (1 << i)-1
        left, code = code & mask, code >> i
        right, code = code & mask, code >> i
        a = raw[2*i] ^ xor_select(old, left)
        b = raw[2*i+1] ^ xor_select(old, right)
        if constants >> (2*i) & 1:
            a ^= all_ones
        if constants >> (2*i+1) & 1:
            b ^= all_ones
        old.append(a & b)
    assert not code
    return old


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    start = time.monotonic()
    rng = random.Random(20261022)
    controls = []
    for k in range(1, 5):
        raw, pairs, monomials = table_data(2*k)
        variants = range(1 << (2*k)) if k <= 3 else [0]
        cases = witnesses = 0
        gate_rank_histogram = Counter()
        for code in range(1 << (k*(k-1))):
            for constants in variants:
                old = gates(raw, code, constants)
                gate_ranks = [quadratic_rank(f, raw, pairs, monomials) for f in old]
                for selector in range(1 << k):
                    value = xor_select(old, selector)
                    result = quadratic_rank(value, raw, pairs, monomials)
                    cases += 1
                    if result == 2*k:
                        assert all(r is not None for r in gate_ranks)
                        witnesses += 1
                        gate_rank_histogram[tuple(gate_ranks)] += 1
        controls.append({'gates': k, 'raw_dimensions': 2*k,
                         'ordered_topologies': 1 << (k*(k-1)),
                         'operand_constant_variants': len(variants),
                         'scalar_decodes_checked': cases,
                         'rank_saturated_quadratic_decodes': witnesses,
                         'gate_rank_histogram': {str(key): value for key, value in sorted(gate_rank_histogram.items())}})
    # Affine output corrections cannot affect quadraticity or polar rank.
    raw, pairs, monomials = table_data(8)
    affine_checks = 0
    for _ in range(1024):
        code = rng.randrange(4096)
        old = gates(raw, code, rng.randrange(256))
        scalar = xor_select(old, rng.randrange(16))
        affine = xor_select(raw, rng.randrange(256))
        if rng.randrange(2):
            affine ^= (1 << 256)-1
        assert quadratic_rank(scalar, raw, pairs, monomials) == quadratic_rank(scalar ^ affine, raw, pairs, monomials)
        affine_checks += 1
    report = {'status': 'pass', 'controls': controls,
              'affine_output_invariance_controls': affine_checks,
              'scope': 'Finite controls for a separate induction: k ANDs computing quadratic polar rank 2k have only quadratic actual gate functions. No world-first or unrestricted GF16 bound follows.',
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'algorithm_seconds': time.monotonic()-start}
    with args.out.open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print(json.dumps(report), flush=True)


if __name__ == '__main__':
    main()
