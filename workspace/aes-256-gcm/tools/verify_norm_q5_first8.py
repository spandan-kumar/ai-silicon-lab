"""Symbolic second-method replay of independent-raw-input four-gate prefixes.

Boolean-ring monomial unions, joint row equations for product high terms and
old-gate cancellation, and low-pivot polar row rank. No production imports,
truth-table Mobius transform, or labelled high-column quotient reduction.
Same research team: algorithmic independence is not external peer review.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
import hashlib
import itertools
import json
from pathlib import Path
import random
import time


PAIRS = list(itertools.combinations(range(8), 2))
HIGH = sum(1 << m for m in range(256) if m.bit_count() > 2)
RAW = [1 << (1 << i) for i in range(8)]
MONOMIAL_TRUTHS = [sum((point & m == m) << point for point in range(256))
                   for m in range(256)]


def support(value):
    while value:
        bit = value & -value
        yield bit.bit_length() - 1
        value ^= bit


def combine(rows, selector):
    result = 0
    for i in support(selector):
        result ^= rows[i]
    return result


def multiply(a, b):
    result = 0
    for i in support(a):
        for j in support(b):
            result ^= 1 << (i | j)
    return result


def truth(form):
    return combine(MONOMIAL_TRUTHS, form)


def low_rows(values):
    rows = {}
    for value in values:
        while value:
            pivot = (value & -value).bit_length()-1
            if pivot not in rows:
                rows[pivot] = value
                break
            value ^= rows[pivot]
    return rows


def equation_kernel(equations, width):
    rows = low_rows(equations)
    result = []
    for free in range(width):
        if free in rows:
            continue
        vector = 1 << free
        for pivot in sorted(rows, reverse=True):
            if (rows[pivot] & vector).bit_count() & 1:
                vector ^= 1 << pivot
        result.append(vector)
    assert len(result) == width-len(rows)
    return result


def column_equations(columns):
    rows = {}
    for j, column in enumerate(columns):
        for monomial in support(column):
            rows[monomial] = rows.get(monomial, 0) ^ (1 << j)
    return list(rows.values())


def projected_right_kernel(columns, old_highs):
    # Solve high(product) + high(old gates) = 0 jointly in 16 variables.
    # Project the nullspace to the 12 right coefficients; keep a cancellation
    # witness. Zero-right kernel elements are precisely the old quadratic K.
    joint = equation_kernel(column_equations(columns + old_highs), 16)
    rows = {}
    cancellations = {}
    for value in joint:
        right, cancel = value & 4095, value >> 12
        while right:
            pivot = (right & -right).bit_length()-1
            if pivot not in rows:
                rows[pivot] = right
                cancellations[pivot] = cancel
                break
            right ^= rows[pivot]
            cancel ^= cancellations[pivot]
    return [(rows[p], cancellations[p]) for p in sorted(rows)]


def degree(form):
    return max((m.bit_count() for m in support(form)), default=0)


def packed_polar(form):
    return sum(((form >> ((1 << a) | (1 << b))) & 1) << k
               for k, (a, b) in enumerate(PAIRS))


def matrix_rank(value, width=8):
    rows = [0]*width
    for k, (a, b) in enumerate(itertools.combinations(range(width), 2)):
        if value >> k & 1:
            rows[a] |= 1 << b
            rows[b] |= 1 << a
    return len(low_rows(rows))


def matching_masks(vertices, pairs):
    if not vertices:
        return [0]
    first, *rest = vertices
    result = []
    for i, other in enumerate(rest):
        edge = 1 << pairs.index((first, other))
        result.extend(edge | tail for tail in
                      matching_masks(rest[:i] + rest[i+1:], pairs))
    return result


def prefix(code):
    assert 0 <= code < 4096
    forms = list(RAW)
    factors = []
    bits = code
    for i in range(4):
        mask = (1 << i)-1
        left, bits = bits & mask, bits >> i
        right, bits = bits & mask, bits >> i
        left = (1 << (2*i)) | (left << 8)
        right = (1 << (2*i+1)) | (right << 8)
        factors.append([left, right])
        forms.append(multiply(combine(forms, left), combine(forms, right)))
    assert not bits and len(low_rows(forms)) == 12
    return forms, factors


def controls():
    start = time.monotonic()
    rng = random.Random(20261020)
    kernel_checks = 0
    for width in range(8):
        for _ in range(64):
            columns = [rng.randrange(1 << 12) for _ in range(width)]
            equations = column_equations(columns)
            basis = equation_kernel(equations, width)
            assert {combine(basis, s) for s in range(1 << len(basis))} == {
                s for s in range(1 << width) if not combine(columns, s)}
            kernel_checks += 1
    # The projection operation itself is checked with a reduced right width
    # embedded in the full 12+4 system against direct enumeration.
    projection_checks = 0
    for _ in range(64):
        columns = [rng.randrange(32) for _ in range(5)] + [0]*7
        old = [rng.randrange(32) for _ in range(4)]
        basis = projected_right_kernel(columns, old)
        got = {combine([r for r, _ in basis], s) & 31
               for s in range(1 << len(basis))}
        expected = {r for r in range(32) if any(
            combine(columns, r) == combine(old, c) for c in range(16))}
        assert got == expected
        for right, cancel in basis:
            assert combine(columns, right) == combine(old, cancel)
        projection_checks += 1
    rank_checks = 0
    for width in (2, 4, 6, 8):
        pairs = list(itertools.combinations(range(width), 2))
        matchings = matching_masks(list(range(width)), pairs)
        values = range(1 << len(pairs)) if width < 8 else [rng.randrange(1 << 28) for _ in range(1024)]
        for value in values:
            pfaffian = sum(value & m == m for m in matchings) & 1
            assert bool(pfaffian) == (matrix_rank(value, width) == width)
            rank_checks += 1
    forms, _ = prefix(1586)
    scalar = multiply(combine(forms, 84), combine(forms, 768))
    scalar ^= combine(forms[8:], 1 | 4 | 8)
    assert degree(forms[11]) == 4 and not scalar & HIGH
    assert matrix_rank(packed_polar(scalar)) == 8
    truths = list(map(truth, forms))
    assert truth(scalar) == ((combine(truths, 84) & combine(truths, 768))
                             ^ combine(truths[8:], 13))
    positive_scan = scan(1586, require_quintic=False)
    assert positive_scan['maximum_polar_rank'] == 8 and positive_scan['rank8_witness']
    return {'status': 'pass', 'small_kernel_bruteforce_controls': kernel_checks,
            'projected_kernel_bruteforce_controls': projection_checks,
            'Pfaffian_vs_row_rank_controls': rank_checks,
            'quartic_positive_control_code': 1586,
            'quartic_positive_factors': [84, 768],
            'quartic_positive_old_gate_decoder': 13,
            'quartic_positive_complete_scan': positive_scan,
            'algorithm_seconds': time.monotonic()-start}


def scan(code, require_quintic=True):
    start = time.monotonic()
    forms, factors = prefix(code)
    assert not require_quintic or degree(forms[11]) == 5
    old = forms[8:]
    old_highs = [f & HIGH for f in old]
    high_rank = len(low_rows(old_highs))
    offsets = [(s, packed_polar(combine(old, s))) for s in range(16)
               if not combine(old_highs, s)]
    offset_dimension = len(low_rows(p for _, p in offsets))
    assert len(offsets) == 1 << (4-high_rank) and offset_dimension == 4-high_rank
    products = [[multiply(a, b) for b in forms] for a in forms]
    truths = list(map(truth, forms))
    for i, j in itertools.product(range(12), repeat=2):
        assert truth(products[i][j]) == truths[i] & truths[j]
    columns = [0]*12
    previous = 0
    eligible = 0
    right_hist = Counter()
    rank_hist = Counter()
    cosets = {}
    witness = None
    for left in range(1, 4096):
        for i in support(previous ^ left):
            columns = [a ^ b for a, b in zip(columns, products[i])]
        previous = left
        kernel = projected_right_kernel([f & HIGH for f in columns], old_highs)
        right_hist[len(kernel)] += 1
        images = []
        for right, cancel in kernel:
            residue = combine(columns, right) ^ combine(old, cancel)
            assert not residue & HIGH
            images.append(packed_polar(residue))
        right = cancel = packed = old_gray = 0
        for number in range(1, 1 << len(kernel)):
            gray = number ^ (number >> 1)
            index = (gray ^ old_gray).bit_length()-1
            old_gray = gray
            right ^= kernel[index][0]
            cancel ^= kernel[index][1]
            packed ^= images[index]
            if right < left:
                continue
            eligible += 1
            key = min(packed ^ offset for _, offset in offsets)
            if key in cosets:
                continue
            maximum = max(matrix_rank(packed ^ offset) for _, offset in offsets)
            cosets[key] = maximum
            rank_hist[maximum] += 1
            if maximum == 8 and witness is None:
                extra = next(s for s, offset in offsets
                             if matrix_rank(packed ^ offset) == 8)
                decoder = cancel ^ extra
                scalar = multiply(combine(forms, left), combine(forms, right)) ^ combine(old, decoder)
                assert not scalar & HIGH and matrix_rank(packed_polar(scalar)) == 8
                assert truth(scalar) == ((combine(truths, left) & combine(truths, right))
                                         ^ combine(truths[8:], decoder))
                witness = {'left': left, 'right': right, 'gate_decoder': decoder}
    assert 0 in cosets and sum(right_hist.values()) == 4095
    inventory = sorted(cosets.items())
    return {'status': 'pass', 'code': code, 'factors': factors,
            'degrees': [degree(f) for f in old], 'high_rank': high_rank,
            'quadratic_offset_dimension': offset_dimension, 'complete': True,
            'lefts': 4095, 'pairs': eligible, 'polar_cosets': len(cosets),
            'maximum_polar_rank': max(rank_hist),
            'maximum_rank_histogram': [rank_hist[i] for i in range(9)],
            'right_kernel_histogram': [right_hist[i] for i in range(13)],
            'symbolic_truth_product_checks': 144*256,
            'sorted_coset_maximum_rank_sha256': hashlib.sha256(
                json.dumps(inventory, separators=(',', ':')).encode()).hexdigest(),
            'rank8_witness': witness, 'algorithm_seconds': time.monotonic()-start}


def save(path, value):
    with Path(path).open('x') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--out', required=True)
    parser.add_argument('--codes', type=int, nargs='*', default=[])
    parser.add_argument('--inventory', action='store_true')
    parser.add_argument('--all-quintics', action='store_true')
    parser.add_argument('--controls', action='store_true')
    parser.add_argument('--jobs', type=int, default=1)
    parser.add_argument('--compare', nargs='*', default=[])
    args = parser.parse_args()
    start = time.monotonic()
    result = {'algorithm': 'symbolic Boolean-ring products and joint row-equation kernel',
              'external_peer_review': False}
    if args.inventory or args.all_quintics:
        histogram = Counter()
        quintics = []
        for code in range(4096):
            forms, _ = prefix(code)
            d = degree(forms[11])
            assert 2 <= d <= 5
            histogram[d] += 1
            if d == 5:
                quintics.append(code)
        result['inventory'] = {'prefixes': 4096, 'degree_histogram': dict(sorted(histogram.items())),
                               'quintic_codes': quintics, 'quintic_prefixes': len(quintics)}
        if args.all_quintics:
            assert not args.codes
            args.codes = quintics
    if args.controls:
        result['controls'] = controls()
    expected = {}
    for path in args.compare:
        document = json.loads(Path(path).read_text())
        expected.update((row['code'], row) for row in document['cases'])
    cases = []
    if args.jobs == 1:
        stream = map(scan, args.codes)
        pool = None
    else:
        pool = ProcessPoolExecutor(max_workers=args.jobs)
        stream = pool.map(scan, args.codes)
    try:
        for row in stream:
            if expected:
                other = expected[row['code']]
                for key in ('degrees', 'high_rank', 'quadratic_offset_dimension', 'lefts',
                            'pairs', 'polar_cosets', 'maximum_polar_rank',
                            'maximum_rank_histogram', 'right_kernel_histogram', 'complete'):
                    assert row[key] == other[key], (row['code'], key, row[key], other[key])
                row['production_case_comparison'] = 'pass'
            cases.append(row)
            print(json.dumps(row), flush=True)
    finally:
        if pool:
            pool.shutdown()
    result['cases'] = cases
    result['complete'] = True
    result['algorithm_seconds'] = time.monotonic()-start
    save(args.out, result)
    print(json.dumps({'status': 'pass', 'cases': len(cases), 'output': args.out,
                      'algorithm_seconds': result['algorithm_seconds']}), flush=True)


if __name__ == '__main__':
    main()
