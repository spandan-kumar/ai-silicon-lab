"""Second-method Q4 replay: symbolic Boolean ring, row kernels, Pfaffian truth tables.

No imports from the production scanner or its polynomial/rank routines.
Same primary author; algorithmic independence is not an external peer review.
"""
import argparse
from collections import Counter
from concurrent.futures import ProcessPoolExecutor
from functools import cache
import hashlib
import itertools
import json
from pathlib import Path
import random
import time

ROOT = Path(__file__).resolve().parents[3]
HERE = None
PAIRS = list(itertools.combinations(range(8), 2))
DIAGONALS = [(2*i, 2*i+1) for i in range(4)]
DIAGONAL_BITS = [PAIRS.index(pair) for pair in DIAGONALS]
DIAGONAL_MASK = sum(1 << bit for bit in DIAGONAL_BITS)
HIGH = sum(1 << m for m in range(256) if m.bit_count() > 2)
RAW = [1 << (1 << i) for i in range(8)]
BASE = RAW + [1 << ((1 << a) | (1 << b)) for a, b in DIAGONALS]
MONOMIAL_TRUTHS = [sum((point & m == m) << point for point in range(256)) for m in range(256)]
MONOMIAL_16 = [sum((point & m == m) << point for point in range(16)) for m in range(16)]


def support(value):
    while value:
        low = value & -value
        yield low.bit_length()-1
        value ^= low


def xor_select(values, selector):
    result = 0
    for i in support(selector):
        result ^= values[i]
    return result


def multiply(a, b):
    value = 0
    for i in support(a):
        for j in support(b):
            value ^= 1 << (i | j)
    return value


def truth(form):
    return xor_select(MONOMIAL_TRUTHS, form)


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


def right_kernel(columns):
    # Equations indexed by monomials; unlike producer's labelled column reduction.
    equations = {}
    for j, column in enumerate(columns):
        for m in support(column):
            equations[m] = equations.get(m, 0) ^ (1 << j)
    rows = low_rows(equations.values())
    kernel = []
    for free in range(len(columns)):
        if free in rows:
            continue
        vector = 1 << free
        for pivot in sorted(rows, reverse=True):
            if (rows[pivot] & vector).bit_count() % 2:
                vector ^= 1 << pivot
        assert xor_select(columns, vector) == 0
        kernel.append(vector)
    assert len(kernel) == len(columns)-len(rows)
    return kernel


def packed_polar(form):
    return sum(((form >> ((1 << a) | (1 << b))) & 1) << k
               for k, (a, b) in enumerate(PAIRS))


def matchings(vertices):
    if not vertices:
        yield ()
        return
    first, *rest = vertices
    for index, other in enumerate(rest):
        for tail in matchings(rest[:index] + rest[index+1:]):
            yield ((first, other),) + tail


MATCHING_MASKS = [sum(1 << PAIRS.index(pair) for pair in matching)
                  for matching in matchings(list(range(8)))]
assert len(MATCHING_MASKS) == 105
MATCHING_POLYNOMIAL = [(mask & ~DIAGONAL_MASK,
                       sum(((mask >> bit) & 1) << i for i, bit in enumerate(DIAGONAL_BITS)))
                      for mask in MATCHING_MASKS]


@cache
def nonsingular_offsets(key):
    assert not key & DIAGONAL_MASK
    # In characteristic two det(A)=Pf(A)^2. Evaluate Pf for all 16 diagonal offsets.
    result = 0
    for required, diagonal_monomial in MATCHING_POLYNOMIAL:
        if key & required == required:
            result ^= MONOMIAL_16[diagonal_monomial]
    return result


def reversed16(value):
    return sum(((value >> i) & 1) << (15-i) for i in range(16))


def matrix_rank(packed, width):
    pairs = list(itertools.combinations(range(width), 2))
    rows = [sum(((packed >> pairs.index(tuple(sorted((i,j))))) & 1) << j
                for j in range(width) if i != j) for i in range(width)]
    return len(low_rows(rows))


def controls():
    start = time.monotonic()
    rng = random.Random(20261020)
    kernel_checks = 0
    for size in range(7):
        for _ in range(64):
            columns = [rng.randrange(4096) for _ in range(size)]
            K = right_kernel(columns)
            assert {xor_select(K, s) for s in range(1 << len(K))} == {
                s for s in range(1 << size) if not xor_select(columns, s)}
            kernel_checks += 1
    rank_checks = 0
    for width in (2, 4, 6, 8):
        pairs = list(itertools.combinations(range(width), 2))
        masks = [sum(1 << pairs.index(pair) for pair in matching)
                 for matching in matchings(list(range(width)))]
        values = range(1 << len(pairs)) if width < 8 else [rng.randrange(1 << 28) for _ in range(1024)]
        for value in values:
            pf = sum(value & m == m for m in masks) % 2
            assert bool(pf) == (matrix_rank(value, width) == width)
            rank_checks += 1
    offset_checks = 0
    for _ in range(256):
        key = rng.randrange(1 << 28) & ~DIAGONAL_MASK
        table = nonsingular_offsets(key)
        for selector in range(16):
            packed = key ^ sum(((selector >> i) & 1) << bit for i, bit in enumerate(DIAGONAL_BITS))
            assert bool(table >> selector & 1) == (matrix_rank(packed, 8) == 8)
            offset_checks += 1
    Q = xor_select(BASE[8:], 15)
    p5 = multiply(xor_select(RAW, 5), xor_select(RAW, 160))
    p6 = multiply(xor_select(RAW, 80), xor_select(RAW, 10))
    R = p5 ^ p6 ^ BASE[8] ^ BASE[10]
    assert matrix_rank(packed_polar(R), 8) == matrix_rank(packed_polar(R ^ Q), 8) == 8
    packed = packed_polar(R)
    table = nonsingular_offsets(packed & ~DIAGONAL_MASK)
    assert table & reversed16(table)
    assert not (nonsingular_offsets(0) & reversed16(nonsingular_offsets(0)))
    result = {'status': 'pass', 'right_kernel_bruteforce_controls': kernel_checks,
              'Pfaffian_vs_elimination_controls': rank_checks,
              'all_offset_truth_table_controls': offset_checks,
              'actual_six_parallel_AND_positive_pair': True,
              'zero_coset_negative_control': True,
              'algorithm_seconds': time.monotonic()-start}
    save(HERE / 'controls.json', result)
    print(json.dumps(result), flush=True)


def save(path, value):
    with path.open('x') as handle:
        json.dump(value, handle, indent=2)
        handle.write('\n')


def scan(task):
    index, factors, expected, folder = task
    start = time.monotonic()
    h = multiply(xor_select(BASE, factors[0]), xor_select(BASE, factors[1]))
    P = BASE + [h]
    H = h & HIGH
    assert H and len(low_rows(P)) == 13
    pivot_mask = H & -H
    products = [[multiply(a,b) for b in P] for a in P]
    T = list(map(truth, P))
    assert T[12] == (xor_select(T, factors[0]) & xor_select(T, factors[1]))
    assert all(truth(products[i][j]) == (T[i] & T[j]) for i,j in itertools.product(range(13), repeat=2))
    cosets = {}
    histogram = Counter()
    eligible = 0
    previous_left = 0
    columns = [0]*13
    for left in range(1, 8192):
        for changed in support(previous_left ^ left):
            columns = [a ^ b for a,b in zip(columns, products[changed])]
        previous_left = left
        highs = [column & HIGH for column in columns]
        projected = [v ^ (H if v & pivot_mask else 0) for v in highs]
        K = right_kernel(projected)
        histogram[len(K)] += 1
        rights = [0]
        for vector in K:
            rights += [old ^ vector for old in rights]
        assert len(rights) == 1 << len(K)
        for right in rights[1:]:
            if right < left:
                continue
            eligible += 1
            product = xor_select(columns, right)
            residue = product ^ (h if product & pivot_mask else 0)
            assert not residue & HIGH
            key = packed_polar(residue) & ~DIAGONAL_MASK
            if key not in cosets:
                table = nonsingular_offsets(key)
                assert not table & reversed16(table), (index, left, right, key, table)
                cosets[key] = table
    assert 0 in cosets
    assert eligible == expected['eligible_unordered_pairs'], (index, eligible, expected)
    assert len(cosets) == expected['quadratic_polar_cosets'], (index, len(cosets), expected)
    inventory = sorted(cosets.items())
    digest = hashlib.sha256(json.dumps(inventory, separators=(',', ':')).encode()).hexdigest()
    result = {'status': 'pass', 'plane_orbit_index': index, 'factor_masks': factors,
        'full_left_forms': 8191, 'eligible_unordered_pairs': eligible,
        'quadratic_polar_cosets': len(cosets), 'rank8_pair_escapes': 0,
        'right_kernel_dimension_histogram': dict(sorted(histogram.items())),
        'symbolic_truth_product_checks': 169,
        'zero_coset_checked': True, 'all_sixteen_corrections_checked': True,
        'sorted_coset_and_Pfaffian_truth_inventory_sha256': digest,
        'coset_and_Pfaffian_truth_inventory': inventory,
        'algorithm_seconds': time.monotonic()-start}
    save(Path(folder) / (str(index) + '.json'), result)
    summary = {k:v for k,v in result.items() if k != 'coset_and_Pfaffian_truth_inventory'}
    print(json.dumps({'class': index, 'status': result['status'], 'seconds': result['algorithm_seconds']}), flush=True)
    return summary


def main():
    global HERE
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('mode', choices=['controls', 'pilot', 'campaign'])
    parser.add_argument('--output', type=Path, required=True,
                        help='Fresh directory for controls; reuse it for pilot/campaign.')
    args = parser.parse_args()
    HERE = args.output.resolve()
    if args.mode == 'controls':
        HERE.mkdir(parents=True, exist_ok=False)
        controls()
        return
    assert json.loads((HERE / 'controls.json').read_text())['status'] == 'pass'
    study = ROOT / 'workspace/aes-256-gcm/reports/sbox_norm_q4_snapshot.json'
    producer = json.loads(study.read_text())['producer_product_campaign']
    folder = HERE / ('pilot' if args.mode == 'pilot' else 'cases')
    folder.mkdir(exist_ok=False)
    selected = producer['cases'][:1] if args.mode == 'pilot' else producer['cases']
    tasks = [(row['plane_orbit_index'], row['factor_masks'], row, str(folder)) for row in selected]
    start = time.monotonic()
    with ProcessPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(scan, tasks))
    report = {'status': 'pass', 'classes_checked': len(results), 'cases': results,
        'algorithmic_independent_replay': True, 'external_independent_author': False,
        'producer_counts_all_match': True, 'rank8_pair_escapes': 0,
        'algorithm_seconds': time.monotonic()-start,
        'scope': 'Complete symbolic replay for supplied class representatives. Orbit completeness and general circuit reduction are separate obligations.',
        'unrestricted_eight_AND_excluded': False, 'world_first_established': False}
    save(HERE / (args.mode + '-report.json'), report)
    print(json.dumps({k:v for k,v in report.items() if k != 'cases'}), flush=True)


if __name__ == '__main__':
    main()
