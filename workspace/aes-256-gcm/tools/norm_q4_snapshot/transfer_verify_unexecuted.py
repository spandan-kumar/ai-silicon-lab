"""Exact controls for the diagonal transfer and quadratic annihilator proofs."""
import itertools
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent


def combine(values, selector):
    output = 0
    for index, value in enumerate(values):
        if selector >> index & 1:
            output ^= value
    return output


def basis(width):
    raw = [sum(((point >> i) & 1) << point for point in range(1 << width)) for i in range(width)]
    return [(1 << (1 << width)) - 1] + raw, raw


def transform(truth, width):
    bits = [(truth >> point) & 1 for point in range(1 << width)]
    for bit in range(width):
        for point in range(1 << width):
            if point & (1 << bit):
                bits[point] ^= bits[point ^ (1 << bit)]
    return sum(value << point for point, value in enumerate(bits))


def matrix_rank(rows):
    pivots = {}
    for row in rows:
        while row:
            pivot = row.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = row
                break
            row ^= pivots[pivot]
    return len(pivots)


def polar_rank(polynomial, width):
    rows = [0] * width
    for i, j in itertools.combinations(range(width), 2):
        value = (polynomial >> ((1 << i) | (1 << j))) & 1
        rows[i] ^= value << j
        rows[j] ^= value << i
    return matrix_rank(rows)


def nullspace(columns):
    pivots, kernel = {}, []
    for index, column in enumerate(columns):
        label = 1 << index
        while column:
            pivot = column.bit_length() - 1
            if pivot not in pivots:
                pivots[pivot] = column, label
                break
            old, old_label = pivots[pivot]
            column ^= old
            label ^= old_label
        if not column:
            kernel.append(label)
    return kernel


start = time.monotonic()
affine, raw = basis(6)
diagonal = [raw[i] & raw[i + 1] for i in (0, 2, 4)]
low = affine + diagonal
wires = [combine(low, selector) for selector in range(1024)]
affines = [combine(affine, selector) for selector in range(128)]
stage_masks = [sum(1 << point for point in range(64) if not point & (1 << bit)) for bit in range(6)]
diagonal_anf = [1 << ((1 << i) | (1 << (i + 1))) for i in (0, 2, 4)]
quadratic_mask = sum(1 << ((1 << i) | (1 << j)) for i, j in itertools.combinations(range(6), 2))
off_diagonal_mask = quadratic_mask ^ combine(diagonal_anf, 7)


def fast_transform(value):
    for bit, mask in enumerate(stage_masks):
        value ^= (value & mask) << (1 << bit)
    return value


for point in range(64):
    assert fast_transform(1 << point) == transform(1 << point, 6)
checks = 0
for left in range(1024):
    for right in range(left, 1024):
        actual = fast_transform(wires[left] & wires[right])
        raw_only = fast_transform(affines[left & 127] & affines[right & 127])
        assert not ((actual ^ raw_only) & off_diagonal_mask)
        checks += 1
assert checks == 524800

affine8, raw8 = basis(8)
products = [raw8[i] & raw8[i + 1] for i in (0, 2, 4, 6)]
h = raw8[2] & (products[0] ^ raw8[4])
g = (raw8[0] ^ raw8[2]) & (products[0] ^ raw8[3])
q = h ^ g
flat = products[0] ^ (raw8[2] & raw8[4]) ^ ((raw8[0] ^ raw8[2]) & raw8[3])
assert q == flat
q_anf, h_anf = transform(q, 8), transform(h, 8)
assert max(mask.bit_count() for mask in range(256) if q_anf >> mask & 1) == 2
assert max(mask.bit_count() for mask in range(256) if h_anf >> mask & 1) == 3
corrected_ranks = [polar_rank(transform(q ^ combine(products, selector), 8), 8) for selector in range(16)]
assert min(corrected_ranks) >= 4
assert polar_rank(transform(combine(products, 15), 8), 8) == 8
bent_pair_options = [selector for selector in range(16)
                     if corrected_ranks[selector] == corrected_ranks[selector ^ 15] == 8]

annihilators = []
for width, pairs in [(6, 3), (8, 3), (8, 4)]:
    affine_basis, raw_basis = basis(width)
    full = affine_basis[0]
    quadratics = [raw_basis[i] & raw_basis[j] for i, j in itertools.combinations(range(width), 2)]
    polynomial_basis = affine_basis + quadratics
    canonical = combine([raw_basis[2 * i] & raw_basis[2 * i + 1] for i in range(pairs)], (1 << pairs) - 1)
    count = 0
    for affine_selector in range(1 << len(affine_basis)):
        target = canonical ^ combine(affine_basis, affine_selector)
        kernel = nullspace([target & value for value in polynomial_basis])
        assert len(kernel) == 1
        annihilator = combine(polynomial_basis, kernel[0])
        assert annihilator == (full ^ target)
        count += 1
    annihilators.append({'input_bits': width, 'quadratic_polar_rank': 2 * pairs,
                         'affine_perturbations_checked': count,
                         'annihilator_dimension_in_degree_at_most_two': 1,
                         'nonzero_annihilator_always_one_plus_target': True})
affine4, raw4 = basis(4)
q4 = (raw4[0] & raw4[1]) ^ (raw4[2] & raw4[3])
quadratic4 = affine4 + [raw4[i] & raw4[j] for i, j in itertools.combinations(range(4), 2)]
rank4_kernel = nullspace([q4 & value for value in quadratic4])
assert len(rank4_kernel) > 1

report = {'status': 'pass', 'diagonal_product_shadow_checks': checks,
    'bit_parallel_transform_basis_controls': 64,
    'embedded_counterexample_rows': 256, 'embedded_corrected_polar_ranks': corrected_ranks,
    'embedded_bent_pair_options': bent_pair_options,
    'embedded_h_degree': 3, 'embedded_q_degree': 2, 'two_raw_product_replacement_exact': True,
    'annihilator_checks': annihilators, 'rank_four_boundary_control_kernel_dimension': len(rank4_kernel),
    'algorithm_seconds': time.monotonic() - start,
    'scope': 'Finite controls accompany separate algebraic proofs; they do not enumerate all rank-eight quadratics '
             'or all eight-input seed-reusing gates. Counterexample does not form a bent pair with Q.',
    'world_first_established': False}
with (HERE / 'verification.json').open('x') as handle:
    json.dump(report, handle, indent=2)
print(json.dumps(report))
