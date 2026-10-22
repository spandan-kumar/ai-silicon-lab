"""Controls for a necessary GF(16) quadratic-pair operator condition.

Rows are packed bits of an 8 by 8 matrix acting on COLUMN vectors: bit j
of row i is entry (i,j), and mm(A,B) means A times B. For a quadratic
scalar f, B_f is its alternating polar matrix, not an ANF coefficient
matrix. A shared affine input substitution x=S*y+a gives B'=S^T B S;
therefore J=B_Q^-1 B_t transforms by J'=S^-1 J S.

In the genuine field target f_c(a,b)=Tr(c*a*b), J is simultaneous
multiplication by d/c on a and b. For independent nonzero c,d, its
minimal polynomial is one of 0x7, 0x13, 0x19, 0x1f. Thus satisfying one
of those irreducible polynomial identities is NECESSARY. We do not claim
that the test proves a supplied pair's field embedding, finds gates,
excludes a frontier, or establishes novelty. If the polynomial has degree
four, any full field target containing the pair has the forced polar
space span(B_Q, B_Q*J, B_Q*J^2, B_Q*J^3).

Self-contained standard-library implementation; no scanner imports.
Do not run with assertions disabled. Output files are exclusive.
"""

import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import random
import time


I = tuple(1 << i for i in range(8))
ZERO = (0,) * 8
PAIRS = tuple(itertools.combinations(range(8), 2))
POLYNOMIALS = (0x7, 0x13, 0x19, 0x1f)


def xor(*matrices):
    result = [0] * 8
    for matrix in matrices:
        for i, row in enumerate(matrix):
            result[i] ^= row
    return tuple(result)


def mv(matrix, column):
    return sum(((row & column).bit_count() & 1) << i
               for i, row in enumerate(matrix))


def mm(left, right):
    rows = []
    for selector in left:
        row = 0
        for j in range(8):
            if selector >> j & 1:
                row ^= right[j]
        rows.append(row)
    return tuple(rows)


def transpose(matrix):
    return tuple(sum(((matrix[j] >> i) & 1) << j for j in range(8))
                 for i in range(8))


def rank(matrix):
    basis = {}
    for row in matrix:
        while row:
            pivot = row.bit_length() - 1
            if pivot not in basis:
                basis[pivot] = row
                break
            row ^= basis[pivot]
    return len(basis)


def inverse(matrix):
    rows = [row | (1 << (8 + i)) for i, row in enumerate(matrix)]
    for j in range(8):
        pivot = next(i for i in range(j, 8) if rows[i] >> j & 1)
        rows[pivot], rows[j] = rows[j], rows[pivot]
        for i in range(8):
            if i != j and rows[i] >> j & 1:
                rows[i] ^= rows[j]
    assert tuple(row & 255 for row in rows) == I
    result = tuple(row >> 8 for row in rows)
    assert mm(matrix, result) == mm(result, matrix) == I
    return result


def polynomial_value(matrix, polynomial):
    result = ZERO
    power = I
    while polynomial:
        if polynomial & 1:
            result = xor(result, power)
        power = mm(power, matrix)
        polynomial >>= 1
    return result


def accepted_polynomials(matrix):
    return [p for p in POLYNOMIALS if polynomial_value(matrix, p) == ZERO]


def alternating(matrix):
    return matrix == transpose(matrix) and all(
        not (row >> i & 1) for i, row in enumerate(matrix))


def packed_polar(matrix):
    assert alternating(matrix)
    return sum(((matrix[a] >> b) & 1) << i
               for i, (a, b) in enumerate(PAIRS))


def matrix_span(basis):
    values = {ZERO}
    for matrix in basis:
        values |= {xor(old, matrix) for old in values}
    return values


def quadratic_value(matrix, point):
    return sum((matrix[a] >> b & 1) * (point >> a & 1)
               * (point >> b & 1) for a, b in PAIRS) & 1


def polar_from_truth(table):
    rows = [0] * 8
    for a, b in PAIRS:
        value = table[(1 << a) | (1 << b)] ^ table[1 << a] ^ table[1 << b] ^ table[0]
        rows[a] |= value << b
        rows[b] |= value << a
    return tuple(rows)


def gf_mul(left, right):
    result = 0
    for _ in range(4):
        if right & 1:
            result ^= left
        right >>= 1
        left <<= 1
        if left & 16:
            left ^= 0x13
    return result


def gf_trace(value):
    result = 0
    for _ in range(4):
        result ^= value
        value = gf_mul(value, value)
    assert result in (0, 1)
    return result


def field_polar(coefficient):
    rows = [0] * 8
    for a, b in itertools.product(range(4), repeat=2):
        value = gf_trace(gf_mul(coefficient, gf_mul(1 << a, 1 << b)))
        rows[a] |= value << (4 + b)
        rows[4 + b] |= value << a
    return tuple(rows)


def field_operator(coefficient):
    # Column j is the coordinate vector coefficient*(1<<j).
    block = tuple(sum(((gf_mul(coefficient, 1 << j) >> i) & 1) << j
                      for j in range(4)) for i in range(4))
    return block + tuple(row << 4 for row in block)


def polynomial_remainder(value, divisor):
    while value.bit_length() >= divisor.bit_length():
        value ^= divisor << (value.bit_length() - divisor.bit_length())
    return value


def irreducible(polynomial):
    degree = polynomial.bit_length() - 1
    return all(polynomial_remainder(polynomial, divisor)
               for d in range(1, degree // 2 + 1)
               for divisor in range(1 << d, 1 << (d + 1)))


def controls():
    assert [p for p in range(4, 8) if irreducible(p)] == [0x7]
    assert [p for p in range(16, 32) if irreducible(p)] == [0x13, 0x19, 0x1f]
    polars = tuple(field_polar(c) for c in range(16))
    assert len(set(polars)) == 16 and polars[0] == ZERO
    assert all(alternating(matrix) and rank(matrix) == 8 for matrix in polars[1:])
    counts = Counter()
    coefficient_cases = []
    for c, d in itertools.permutations(range(1, 16), 2):
        BQ, Bt = polars[c], polars[d]
        ratio = next(r for r in range(1, 16) if gf_mul(c, r) == d)
        J = mm(inverse(BQ), Bt)
        assert J == field_operator(ratio)
        choices = accepted_polynomials(J)
        assert len(choices) == 1
        p = choices[0]
        assert rank(Bt) == rank(xor(Bt, BQ)) == 8
        counts[p] += 1
        regenerated = None
        if p != 0x7:
            J2 = mm(J, J)
            generated = [BQ, Bt, mm(BQ, J2), mm(BQ, mm(J2, J))]
            assert all(alternating(matrix) for matrix in generated)
            assert matrix_span(generated) == set(polars)
            regenerated = True
        coefficient_cases.append({'Q_coefficient': c, 't_coefficient': d,
                                  'coefficient_ratio': ratio, 'polynomial': hex(p),
                                  'degree_four_target_regenerated': regenerated})
    assert counts == {0x7: 30, 0x13: 60, 0x19: 60, 0x1f: 60}

    # Companion C of x^4+x^2+1 = (x^2+x+1)^2, then J=diag(C,C^T).
    C = (8, 1, 10, 4)
    CT = tuple(sum(((C[j] >> i) & 1) << j for j in range(4)) for i in range(4))
    Q = tuple(1 << (i + 4) if i < 4 else 1 << (i - 4) for i in range(8))
    J = C + tuple(row << 4 for row in CT)
    t = mm(Q, J)
    assert alternating(Q) and alternating(t)
    assert rank(Q) == rank(t) == rank(xor(t, Q)) == 8
    assert mm(inverse(Q), t) == J
    assert polynomial_value(J, 0x7) != ZERO
    assert polynomial_value(J, 0x15) == ZERO
    assert not accepted_polynomials(J)
    counterexample = {'Q_rows': Q, 't_rows': t, 'J_rows': J,
                      'Q_polar': packed_polar(Q), 't_polar': packed_polar(t),
                      'ranks_Q_t_t_plus_Q': [8, 8, 8],
                      'minimal_polynomial': '0x15=(X^2+X+1)^2',
                      'accepted_polynomials': [], 'rejected_by_filter': True}

    rng = random.Random(20261022)
    transformations = []
    truth_rows = composition_rows = 0
    for index in range(64):
        while True:
            S = tuple(rng.randrange(256) for _ in range(8))
            if rank(S) == 8:
                break
        Si = inverse(S)
        c, d = rng.sample(range(1, 16), 2)
        for label, BQ, Bt in [('field', polars[c], polars[d]),
                              ('nonsemisimple_counterexample', Q, t)]:
            shift, lq, lt = (rng.randrange(256) for _ in range(3))
            cq, ct = rng.randrange(2), rng.randrange(2)
            changed = []
            for B, linear, constant in [(BQ, lq, cq), (Bt, lt, ct)]:
                table = [quadratic_value(B, mv(S, point) ^ shift)
                         ^ ((linear & point).bit_count() & 1) ^ constant
                         for point in range(256)]
                expected = mm(transpose(S), mm(B, S))
                assert polar_from_truth(table) == expected
                coefficients = table.copy()
                for bit in range(8):
                    for mask in range(256):
                        if mask >> bit & 1:
                            coefficients[mask] ^= coefficients[mask ^ (1 << bit)]
                assert all(not value or mask.bit_count() <= 2
                           for mask, value in enumerate(coefficients))
                for point in range(256):
                    assert table[point] == (sum(value for mask, value in enumerate(coefficients)
                                               if point & mask == mask) & 1)
                truth_rows += 256
                changed.append(expected)
            oldJ = mm(inverse(BQ), Bt)
            newJ = mm(inverse(changed[0]), changed[1])
            assert newJ == mm(Si, mm(oldJ, S))
            assert accepted_polynomials(newJ) == accepted_polynomials(oldJ)
            for point in range(256):
                assert mv(mm(oldJ, S), point) == mv(oldJ, mv(S, point))
                composition_rows += 1
            transformations.append({'index': index, 'kind': label, 'S_rows': S,
                                    'input_shift': shift, 'Q_output_linear': lq,
                                    't_output_linear': lt, 'Q_output_constant': cq,
                                    't_output_constant': ct,
                                    'accepted_polynomials': list(map(hex, accepted_polynomials(newJ)))})
    return {'status': 'pass', 'ordered_field_coefficient_pairs': 210,
            'polynomial_counts': {hex(p): counts[p] for p in POLYNOMIALS},
            'degree_four_target_regenerations': 180,
            'coefficient_cases': coefficient_cases,
            'bent_pair_not_field_counterexample': counterexample,
            'random_GL8_affine_pair_controls': len(transformations),
            'full_truth_rows_replayed': truth_rows,
            'matrix_composition_vector_checks': composition_rows,
            'transformations': transformations, 'random_seed': 20261022}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert __debug__, 'Assertions must remain enabled'
    assert not args.out.exists()
    start = time.monotonic()
    report = controls()
    report.update({'scope': 'Necessary pair-operator filter and finite controls only. No frontier scan, circuit construction, sufficiency or novelty claim.',
                   'matrix_convention': 'Packed rows, column vectors, J=B_Q^-1 B_t; input x=S*y+a gives J_new=S^-1 J S.',
                   'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                   'algorithm_seconds': time.monotonic() - start,
                   'external_peer_review': False, 'frontier_tested': False,
                   'world_first_established': False})
    with args.out.open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print(json.dumps({key: value for key, value in report.items()
                      if key not in ('coefficient_cases', 'transformations')}, indent=2))


if __name__ == '__main__':
    main()
