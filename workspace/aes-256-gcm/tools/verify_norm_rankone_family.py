"""Standalone finite obstruction for one shared-cubic prefix's linear family.

Uses only the committed symbolic Boolean-ring helpers; no solver/raw archive.
This does not classify all rank-one prefixes or exclude unrestricted8AND.
"""
import itertools
import json
import time

from verify_norm_family import add, low_basis, multiply, nullspace, rank, truth

PAIRS = list(itertools.combinations(range(8), 2))


def packed_polar(form):
    return sum(((form >> ((1 << i) | (1 << j))) & 1) << bit
               for bit, (i, j) in enumerate(PAIRS))


def packed_rank(value):
    rows = [0] * 8
    for bit, (i, j) in enumerate(PAIRS):
        if value >> bit & 1:
            rows[i] ^= 1 << j
            rows[j] ^= 1 << i
    return len(low_basis(rows))


def reduce(value, basis):
    for bit in sorted(basis):
        if value >> bit & 1:
            value ^= basis[bit]
    return value


def field(left, right):
    output = 0
    for _ in range(4):
        if right & 1:
            output ^= left
        right >>= 1
        left <<= 1
        if left & 16:
            left ^= 19
    return output


def main():
    start = time.monotonic()
    P = [1 << (1 << bit) for bit in range(8)]
    factors = [[1, 16], [258, 128], [256, 128], [4, 64], [8, 32]]
    for left, right in factors:
        P.append(multiply(add(P, left), add(P, right)))
    Q = add(P, 7936)
    high = sum(1 << monomial for monomial in range(256) if monomial.bit_count() > 2)
    assert len(low_basis(P)) == 13 and rank(Q) == 8
    assert not Q & high and len(low_basis([value & high for value in P])) == 1
    cubic = P[10]
    assert cubic == (P[9] & high) == (1 << 145)
    K_forms = [P[8], P[9] ^ P[10], P[11], P[12]]
    K = [packed_polar(add(K_forms, mask)) for mask in range(16)]
    K_basis = low_basis(K)
    q = packed_polar(Q)
    assert len(K_basis) == 4 and q in K
    assert not any(packed_rank(offset) == packed_rank(offset ^ q) == 8 for offset in K)
    # Form all four bilinear target polynomials and independently replay them.
    targets = [0] * 4
    for i, j in itertools.product(range(4), repeat=2):
        coefficient = field(1 << i, 1 << j)
        for bit in range(4):
            if coefficient >> bit & 1:
                targets[bit] ^= 1 << ((1 << i) | (1 << (4 + j)))
    target_truths = list(map(truth, targets))
    assert targets[0] == Q
    for point in range(256):
        output = field(point & 15, point >> 4)
        assert all((value >> point & 1) == (output >> bit & 1)
                   for bit, value in enumerate(target_truths))
    assert all(rank(add(targets, selector)) == 8 for selector in range(1, 16))
    products = [[multiply(left, right) for right in P] for left in P]
    for i, left in enumerate(P):
        for j, right in enumerate(P):
            assert truth(products[i][j]) == (truth(left) & truth(right))
    cosets = set()
    eligible = 0
    for left in range(1, 8192):
        columns = [add([products[i][j] for i in range(13)], left) for j in range(13)]
        kernel = nullspace([value & high & ~cubic for value in columns])
        for selector in range(1, 1 << len(kernel)):
            right = add(kernel, selector)
            if right < left:
                continue
            form = add(columns, right)
            if form & cubic:
                form ^= cubic
            assert not form & high
            packed = packed_polar(form)
            key = reduce(packed, K_basis)
            if key not in cosets:
                assert not any(packed_rank(packed ^ offset) ==
                               packed_rank(packed ^ offset ^ q) == 8 for offset in K)
                cosets.add(key)
            eligible += 1
    assert eligible == 53776 and len(cosets) == 10036 and 0 in cosets
    print(json.dumps({'status': 'pass', 'nonzero_left_forms': 8191,
        'eligible_unordered_pairs': eligible, 'quadratic_polar_cosets': len(cosets),
        'quadratic_kernel_dimension_mod_affine': 4, 'zero_K_coset_checked': True,
        'cosets_admitting_rank8_pair_with_Q': 0,
        'nonzero_field_output_combinations_with_polar_rank8': 15,
        'factor_masks': factors, 'scalar_Q_decoder_mask': 7936,
        'scope': 'All invertible linear raw-input versions of this specified prefix '
            'mapping Q modulo affine into a field-output direction. Not all rank1prefixes.',
        'unrestricted_eight_AND_excluded': False, 'world_first_established': False,
        'algorithm_seconds': time.monotonic() - start}), flush=True)


if __name__ == '__main__':
    main()
