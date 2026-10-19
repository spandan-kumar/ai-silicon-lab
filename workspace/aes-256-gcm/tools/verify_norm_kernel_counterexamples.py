"""Replay the two rank1-kernel examples and the local-lemma refutation.

No solver or ignored run archive is required. This is not a full multiplier.
"""
import json

from verify_norm_family import add, low_basis, multiply, polar, rank, truth
from verify_norm_prefix import multiply as field


def signals(factors):
    values = [1 << (1 << bit) for bit in range(8)]
    for gate, (left, right) in enumerate(factors):
        assert left < 1 << (8 + gate) and right < 1 << (8 + gate)
        values.append(multiply(add(values, left), add(values, right)))
    return values


def pack(form):
    return sum(row << (8 * bit) for bit, row in enumerate(polar(form)))


def replay(label, factors, decoder, histogram, parallel, selectors, decoders, parallel_Q):
    values = signals(factors)
    high = sum(1 << mask for mask in range(256) if mask.bit_count() > 2)
    assert len(low_basis(values)) == 13
    assert len(low_basis([value & high for value in values[8:]])) == 1
    Q = add(values, decoder)
    expected = sum((field(point & 15, point >> 4) & 1) << point for point in range(256))
    assert truth(Q) == expected and rank(Q) == 8 and not Q & high
    K = [add(values[8:], mask) for mask in range(32) if not add(values[8:], mask) & high]
    assert len(K) == 16 and len(low_basis(list(map(pack, K)))) == 4
    actual = {}
    for value in K:
        actual[rank(value)] = actual.get(rank(value), 0) + 1
    assert actual == histogram
    assert len(low_basis([pack(value) for value in K if rank(value) == 2])) == 3
    raw_upper = signals(parallel)
    assert all(left < 256 and right < 256 for left, right in parallel)
    for selector, output in zip(selectors, decoders):
        assert add(values[8:], selector) == add(raw_upper, output)
    assert add(raw_upper, parallel_Q) == Q
    return {'label': label, 'factor_masks': factors, 'scalar_decoder': decoder,
        'verified_inputs': 256, 'scalar_polar_rank': 8, 'higher_degree_rank': 1,
        'K_dimension': 4, 'K_polar_rank_histogram_including_zero': actual,
        'rank2_member_span_dimension': 3, 'K_parallel_AND_complexity': 5,
        'lower_bound_reason': 'A4-product parallel cover of dimension4 must equalK, '
            'but rank2members spanonly3.',
        'parallel_upper_factors': parallel, 'parallel_K_selectors': selectors,
        'parallel_K_decoders': decoders, 'parallel_Q_decoder': parallel_Q}


def main():
    cases = [replay('explicit', [[1, 2], [128, 272], [129, 274], [4, 64], [8, 32]],
        7680, {0: 1, 2: 3, 4: 5, 6: 5, 8: 2},
        [[1, 2], [1, 16], [2, 128], [4, 64], [8, 32]],
        [1, 6, 8, 16], [256, 1536, 2048, 4096], 7680),
        replay('solver', [[1, 112], [12, 434], [13, 498], [106, 130], [105, 139]],
        7947, {0: 1, 2: 3, 4: 6, 6: 5, 8: 1},
        [[1, 112], [130, 232], [105, 226], [1, 130], [12, 64]],
        [1, 8, 16, 6], [256, 642, 1129, 6144], 8160)]
    forms = [0x11501120061, 0x1010c, 0x1000400030010, 0x101110117067e]
    high = sum(1 << mask for mask in range(64) if mask.bit_count() > 2)
    assert all(not value & high for value in forms)
    h = multiply(forms[0], forms[1])
    q = h ^ multiply(forms[2], forms[3])
    assert h & high and not q & high and q == 0x110015c
    assert truth(q) == (truth(forms[0]) & truth(forms[1])) ^ (truth(forms[2]) & truth(forms[3]))
    ranks = [rank(q ^ add(forms, mask)) for mask in range(16)]
    assert ranks == [4] * 16
    print(json.dumps({'status': 'pass', 'prefixes': cases,
        'kernel_basis_conjecture_refuted': True,
        'local_lemma_counterexample': {'P_Q_A_B_ANF_hex': list(map(hex, forms)),
            'h_ANF_hex': hex(h), 'q_ANF_hex': hex(q), 'all16_corrected_polar_ranks': ranks,
            'distinct_input_rows': 64, 'quadratic_precursor_cost_constrained': False},
        'general_rankone_flattening_refuted': False,
        'complete_GF16_candidate': False, 'world_first_established': False}, indent=2))


if __name__ == '__main__':
    main()
