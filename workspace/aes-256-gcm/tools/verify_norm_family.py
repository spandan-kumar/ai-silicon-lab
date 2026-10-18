"""Standalone exhaustive check of the shared-product scalar-prefix barrier."""
import itertools
import json
import random
import time


def add(values, selector):
    value = 0
    for index, old in enumerate(values):
        if selector >> index & 1:
            value ^= old
    return value


def terms(form):
    while form:
        bit = form & -form
        yield bit.bit_length() - 1
        form ^= bit


def multiply(left, right):
    result = 0
    for a in terms(left):
        for b in terms(right):
            result ^= 1 << (a | b)
    return result


def low_basis(vectors):
    rows = {}
    for vector in vectors:
        while vector:
            bit = (vector & -vector).bit_length() - 1
            if bit not in rows:
                rows[bit] = vector
                break
            vector ^= rows[bit]
    return rows


def nullspace(columns):
    equations = {}
    for index, column in enumerate(columns):
        for monomial in terms(column):
            equations[monomial] = equations.get(monomial, 0) ^ (1 << index)
    rows = low_basis(equations.values())
    basis = []
    for free in range(len(columns)):
        if free in rows:
            continue
        vector = 1 << free
        for pivot in sorted(rows, reverse=True):
            if (rows[pivot] & vector).bit_count() & 1:
                vector ^= 1 << pivot
        assert add(columns, vector) == 0
        basis.append(vector)
    assert len(basis) == len(columns) - len(rows)
    return basis


def polar(form):
    return [sum(((form >> ((1 << i) | (1 << j))) & 1) << j
                for j in range(8) if i != j) for i in range(8)]


def rank(form):
    return len(low_basis(polar(form)))


def truth(form):
    return sum((sum(1 for monomial in terms(form) if point & monomial == monomial) % 2) << point
               for point in range(256))


def main():
    start = time.monotonic()
    raw = [1 << (1 << index) for index in range(8)]
    a, b, c, d, e, f, g, h = raw
    p = multiply(a, b)
    gates = [p, multiply(p ^ c, d), multiply(p ^ e, f),
             multiply(p ^ g, h), multiply(p, d ^ f ^ h)]
    Q = p ^ multiply(c, d) ^ multiply(e, f) ^ multiply(g, h)
    assert add(gates, 31) == Q and rank(Q) == 8 and rank(p) == 2
    P = raw + gates
    high_mask = sum(1 << monomial for monomial in range(256) if monomial.bit_count() > 2)
    cubic = [11, 35, 131]
    permitted = sum(1 << monomial for monomial in cubic)
    assert len(low_basis(P)) == 13 and len(low_basis([form & high_mask for form in P])) == 3
    assert [selector for selector in range(32) if not (add(gates, selector) & high_mask)] == [0, 1, 30, 31]
    product_table = [[multiply(left, right) for right in P] for left in P]
    products = [[truth(left) & truth(right) for right in P] for left in P]
    assert all(truth(product_table[i][j]) == products[i][j] for i in range(13) for j in range(13))
    kernel_histogram = {}
    histogram = {}
    residue_cosets = set()
    eligible = 0
    for left in range(1, 8192):
        columns = [add([product_table[i][j] for i in range(13)], left) for j in range(13)]
        kernel = nullspace([column & high_mask & ~permitted for column in columns])
        kernel_histogram[len(kernel)] = kernel_histogram.get(len(kernel), 0) + 1
        for coefficients in range(1, 1 << len(kernel)):
            right = add(kernel, coefficients)
            if right < left:
                continue
            form = add(columns, right)
            assert not (form & high_mask & ~permitted)
            for gate, monomial in zip(gates[1:4], cubic):
                if form >> monomial & 1:
                    form ^= gate
            assert not (form & high_mask)
            representatives = [form, form ^ p, form ^ Q, form ^ p ^ Q]
            minimum = min(map(rank, representatives))
            assert minimum <= 4
            histogram[minimum] = histogram.get(minimum, 0) + 1
            residue_cosets.add(min(tuple(polar(value)) for value in representatives))
            eligible += 1
    assert eligible == 61504
    assert histogram == {0: 8431, 2: 44811, 4: 8262}
    assert kernel_histogram == {10: 10, 8: 224, 9: 21, 6: 242, 7: 14, 2: 1344, 3: 192, 1: 5632, 5: 64, 4: 448}
    assert len(residue_cosets) == 13081
    # All small right kernels are compared to brute-force masks independently.
    rng = random.Random(20261018)
    controls = 0
    for size in range(7):
        for _ in range(64):
            columns = [rng.randrange(1 << 12) for _ in range(size)]
            K = nullspace(columns)
            assert {add(K, mask) for mask in range(1 << len(K))} == {
                mask for mask in range(1 << size) if add(columns, mask) == 0}
            controls += 1
    # Matrix-rank inequality used in the proof, including every 4x4 symmetric
    # zero-diagonal matrix and every rank-at-most-two elementary polar update.
    rank_inequalities = 0
    for form_bits in range(64):
        rows = [0] * 4
        for bit, (i, j) in enumerate(itertools.combinations(range(4), 2)):
            if form_bits >> bit & 1:
                rows[i] ^= 1 << j
                rows[j] ^= 1 << i
        for left in range(16):
            for right in range(16):
                update = [((left >> i & 1) * right) ^ ((right >> i & 1) * left) for i in range(4)]
                assert len(low_basis([x ^ y for x, y in zip(rows, update)])) >= len(low_basis(rows)) - 2
                rank_inequalities += 1
    result = {'status': 'pass', 'full_nonzero_left_forms': 8191,
              'full_unordered_eligible_pairs': eligible, 'rank_histogram': histogram,
              'quadratic_polar_cosets': len(residue_cosets), 'independent_right_kernel_controls': controls,
              'rank_inequality_controls': rank_inequalities,
              'symbolic_truth_product_checks': 169 * 256,
              'quadratic_gate_selector_kernel': [0, 1, 30, 31],
              'family_argument': 'For any invertible linear input substitution mapping Q modulo affine '
                  'into a four-dimensional quadratic target space whose every nonzero polar has rank8, '
                  'a useful in-envelope product would give a quadratic residue outside span(p,Q). '
                  'Its entire coset modulo(p,Q) has polar rank>=6 because target combinations '
                  'outside Q have rank8 and p has rank2. The complete canonical product inventory '
                  'gives a representative of rank<=4 for every eligible product. Contradiction. '
                  'Thus P is product-closed within P+target and cannot complete in three ANDs.',
              'all_five_gate_prefixes_classified': False, 'unrestricted_eight_AND_excluded': False,
              'world_first_established': False, 'algorithm_seconds': time.monotonic() - start}
    print(json.dumps(result), flush=True)


if __name__ == '__main__':
    main()
