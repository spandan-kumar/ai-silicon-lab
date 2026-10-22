"""Exact first-eight-raw-factor input to the remaining five-gate search.

Enumerate the 4,096 ordinary four-AND prefixes with independent raw factor
forms. A common permutation of fresh coordinate pairs transports every actual
gate polynomial to a representative with sorted operand dependency masks.
This is a prefix-space normalization, not a field-multiplier exclusion.

The symbolic constructor is shared with the independent quintic replay. Gate
truths, packed Mobius transforms, quadratic decoders, and ranks are recomputed
here by separate code. No continuation search is performed.
"""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import random
import time

import verify_norm_q5_first8 as symbolic


RAW_TRUTHS = [sum(((x >> i) & 1) << x for x in range(256)) for i in range(8)]
MOBIUS_MASKS = [sum(bool(m & (1 << i)) << m for m in range(256))
                 for i in range(8)]
AFFINE_MASK = 1 | sum(1 << (1 << i) for i in range(8))
HIGH_MASK = sum((m.bit_count() > 2) << m for m in range(256))


def support(value):
    while value:
        bit = value & -value
        yield bit.bit_length() - 1
        value ^= bit


def xor_selected(values, selector):
    result = 0
    for i in support(selector):
        result ^= values[i]
    return result


def mobius(truth):
    for i, mask in enumerate(MOBIUS_MASKS):
        truth ^= (truth << (1 << i)) & mask
    return truth


def rank(values):
    # Independent leftmost-pivot elimination on integer rows.
    rows = list(values)
    result = 0
    for col in range(max((v.bit_length() for v in rows), default=0)):
        pivot = next((i for i in range(result, len(rows)) if rows[i] >> col & 1), None)
        if pivot is None:
            continue
        rows[result], rows[pivot] = rows[pivot], rows[result]
        for i in range(result + 1, len(rows)):
            if rows[i] >> col & 1:
                rows[i] ^= rows[result]
        result += 1
    return result


def polar_rows(form):
    rows = [0] * 8
    for a in range(8):
        for b in range(a + 1, 8):
            if form >> ((1 << a) | (1 << b)) & 1:
                rows[a] ^= 1 << b
                rows[b] ^= 1 << a
    return rows


def packed_polar(form):
    result = bit = 0
    for a in range(8):
        for b in range(a + 1, 8):
            result |= ((form >> ((1 << a) | (1 << b))) & 1) << bit
            bit += 1
    return result


def dependencies(code):
    result = []
    for i in range(4):
        mask = (1 << i) - 1
        left, code = code & mask, code >> i
        right, code = code & mask, code >> i
        result.append((left, right))
    assert not code
    return result


def encode(pairs):
    code = shift = 0
    for i, (left, right) in enumerate(pairs):
        assert 0 <= left < (1 << i) and 0 <= right < (1 << i)
        code |= left << shift
        shift += i
        code |= right << shift
        shift += i
    assert shift == 12
    return code


def canonical(code):
    pairs = dependencies(code)
    swaps = sum((left > right) << i for i, (left, right) in enumerate(pairs))
    return encode([tuple(sorted(p)) for p in pairs]), swaps


def permutation(swaps):
    result = list(range(8))
    for i in range(4):
        if swaps >> i & 1:
            result[2*i], result[2*i+1] = result[2*i+1], result[2*i]
    return result


def permute_index(index, p):
    return sum(1 << p[i] for i in support(index))


def permute_polynomial(form, p):
    result = 0
    for m in support(form):
        result ^= 1 << permute_index(m, p)
    return result


def permute_truth(truth, point_map):
    # Evaluation substitution, independently of monomial transport.
    return sum(((truth >> point_map[x]) & 1) << x for x in range(256))


def gate_truths(factors, constants=None):
    values = list(RAW_TRUTHS)
    constants = constants or [(0, 0)] * len(factors)
    for (left, right), (a, b) in zip(factors, constants):
        u = xor_selected(values, left) ^ (((1 << 256) - 1) if a else 0)
        v = xor_selected(values, right) ^ (((1 << 256) - 1) if b else 0)
        values.append(u & v)
    return values


def decoder_census(values):
    gate_forms = [mobius(t) for t in values[8:]]
    high_rank = rank(f & HIGH_MASK for f in gate_forms)
    quadratics = []
    for selector in range(16):
        # Decode the actual truth table first, rather than a symbolic selector.
        form = mobius(xor_selected(values[8:], selector))
        if not form & HIGH_MASK:
            quadratics.append({'selector': selector, 'polar_rank': rank(polar_rows(form)),
                               'polar': packed_polar(form)})
    k_dimension = len(quadratics).bit_length() - 1
    assert len(quadratics) == 1 << k_dimension
    assert k_dimension + high_rank == 4
    assert rank(q['polar'] for q in quadratics) == k_dimension
    return high_rank, k_dimension, quadratics


def random_dag_controls():
    rng = random.Random(20261022)
    cases = rows = 0
    for gates in (5, 8):
        for _ in range(32):
            factors = [(rng.randrange(1 << (8+i)), rng.randrange(1 << (8+i)))
                       for i in range(gates)]
            constants = [(rng.randrange(2), rng.randrange(2)) for _ in range(gates)]
            original = gate_truths(factors, constants)
            # These are not restricted to the normalized first-four topology.
            for swaps in range(16):
                p = permutation(swaps)
                mapped = [[permute_index(mask & 255, p) | (mask & ~255)
                           for mask in pair] for pair in factors]
                transported = gate_truths(mapped, constants)
                point_map = [permute_index(x, p) for x in range(256)]
                for i in range(gates):
                    assert permute_truth(original[8+i], point_map) == transported[8+i]
                    assert permute_polynomial(mobius(original[8+i]), p) == mobius(transported[8+i])
                    rows += 256
                cases += 1
    return {'status': 'pass', 'generic_full_dags': 64, 'dag_permutation_cases': cases,
            'gate_rows_checked': rows, 'operand_constants_included': True}


def classify():
    start = time.monotonic()
    records, grouped = [], defaultdict(list)
    degree_histogram, nonquintic_high = Counter(), Counter()
    rank8_by_four = []
    transported_gate_polynomials = transported_gate_rows = 0
    wrong_identity_rejected = 0
    for code in range(4096):
        forms, factors = symbolic.prefix(code)
        values = gate_truths(factors)
        assert list(map(mobius, values)) == forms
        assert rank(f & ~AFFINE_MASK for f in forms[8:]) == 4
        representative, swaps = canonical(code)
        rep_forms, rep_factors = symbolic.prefix(representative)
        rep_values = gate_truths(rep_factors)
        p = permutation(swaps)
        point_map = [permute_index(x, p) for x in range(256)]
        for i in range(8):
            assert permute_polynomial(forms[i], p) == rep_forms[p[i]]
        for i in range(4):
            assert permute_polynomial(forms[8+i], p) == rep_forms[8+i]
            assert permute_truth(values[8+i], point_map) == rep_values[8+i]
            transported_gate_polynomials += 1
            transported_gate_rows += 256
        if swaps and forms[8:] != rep_forms[8:]:
            wrong_identity_rejected += 1
        # Directly enumerate the full effective pair-swap action, rather than
        # assuming the sort formula produces complete orbits.
        orbit = set()
        for action in range(8):
            moved = [(right, left) if action >> (i-1) & 1 else (left, right)
                     for i, (left, right) in enumerate(dependencies(code)) if i]
            moved = [(0, 0)] + moved
            target = encode(moved)
            assert canonical(target)[0] == representative
            orbit.add(target)
        high_rank, k_dimension, quadratics = decoder_census(values)
        rank8_selectors = [q['selector'] for q in quadratics if q['polar_rank'] == 8]
        if rank8_selectors:
            rank8_by_four.append(code)
        degrees = [symbolic.degree(f) for f in forms[8:]]
        assert all(d <= 5 for d in degrees)
        nonquintic = degrees[-1] <= 4
        proper = nonquintic and not rank8_selectors
        degree_histogram[degrees[-1]] += 1
        if nonquintic:
            nonquintic_high[(degrees[-1], high_rank)] += 1
        record = {'code': code, 'factors': factors, 'degrees': degrees,
                  'high_rank': high_rank, 'quadratic_offset_dimension': k_dimension,
                  'quadratic_decoders': quadratics,
                  'rank8_by_four_selectors': rank8_selectors,
                  'nonquintic': nonquintic, 'proper_first_scalar_at_five': proper,
                  'representative': representative, 'pair_swap_mask': swaps,
                  'raw_coordinate_permutation': p,
                  'available_wire_index_transport': p + list(range(8, 12)),
                  'full_gate_polynomial_transport': True,
                  'full_gate_truth_transport_256_rows': True,
                  'direct_action_orbit_size': len(orbit)}
        records.append(record)
        grouped[representative].append(code)
    assert rank8_by_four == [0]
    assert dict(degree_histogram) == {2: 64, 3: 318, 4: 1194, 5: 2520}
    assert transported_gate_polynomials == 4096*4 and transported_gate_rows == 4096*4*256
    assert wrong_identity_rejected > 0
    orbits = []
    orbit_histogram = Counter()
    for representative, members in sorted(grouped.items()):
        r = records[representative]
        assert len(members) == r['direct_action_orbit_size']
        assert len(members) in (1, 2, 4, 8)
        for code in members:
            c = records[code]
            assert c['direct_action_orbit_size'] == len(members)
            assert c['nonquintic'] == r['nonquintic']
            assert c['proper_first_scalar_at_five'] == r['proper_first_scalar_at_five']
            assert c['degrees'] == r['degrees']
            assert c['high_rank'] == r['high_rank']
        orbit_histogram[(r['degrees'][-1], len(members))] += 1
        orbits.append({'representative': representative, 'members': members,
                       'multiplicity': len(members), 'degrees': r['degrees'],
                       'high_rank': r['high_rank'],
                       'quadratic_offset_dimension': r['quadratic_offset_dimension'],
                       'nonquintic': r['nonquintic'],
                       'proper_first_scalar_at_five': r['proper_first_scalar_at_five']})
    assert sum(o['multiplicity'] for o in orbits) == 4096
    assert len(orbits) == 1080
    nonquintic_orbits = [o for o in orbits if o['nonquintic']]
    proper_orbits = [o for o in orbits if o['proper_first_scalar_at_five']]
    assert len(nonquintic_orbits) == 494 and len(proper_orbits) == 493
    assert sum(o['multiplicity'] for o in nonquintic_orbits) == 1576
    assert sum(o['multiplicity'] for o in proper_orbits) == 1575
    controls = random_dag_controls()
    return {'scope': 'Exact input normalization for the r4=8 remaining five-AND scalar search; not a field exclusion.',
            'status': 'pass', 'canonicalization': 'Ascending operand dependency masks at each gate; the representative need not be the smallest integer code.',
            'coverage': {'all_ordered_prefixes': 4096, 'all_pair_swap_orbits': 1080,
                         'nonquintic_prefixes': 1576, 'nonquintic_orbits': 494,
                         'proper_prefixes': 1575, 'proper_prefix_orbits': 493,
                         'only_rank8_by_four_code': 0,
                         'weighted_orbit_count': sum(o['multiplicity'] for o in orbits)},
            'controls': {'transported_gate_polynomials': transported_gate_polynomials,
                         'transported_gate_rows': transported_gate_rows,
                         'nontrivial_maps_rejecting_identity': wrong_identity_rejected,
                         'generic_dag_coordinate_transport': controls},
            'degree_histogram': dict(sorted(degree_histogram.items())),
            'nonquintic_degree_high_rank_histogram': [
                {'g4_degree': d, 'high_rank': h, 'prefixes': n}
                for (d, h), n in sorted(nonquintic_high.items())],
            'orbit_degree_size_histogram': [
                {'g4_degree': d, 'orbit_size': s, 'orbits': n}
                for (d, s), n in sorted(orbit_histogram.items())],
            'proper_representatives': [o['representative'] for o in proper_orbits],
            'orbits': orbits, 'prefixes': records,
            'algorithm_seconds': time.monotonic() - start,
            'field_exclusion': False, 'world_first_established': False,
            'continuation_warning': 'An unmarked W5 is determined by its new quadratic polar coset modulo K4. A later test must retain or re-enumerate every admissible distinguished rank-eight scalar in that coset.'}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True, help='Fresh JSON output file.')
    args = parser.parse_args()
    assert not args.output.exists()
    result = classify()
    sources = [Path(__file__).resolve(), Path(symbolic.__file__).resolve()]
    result['source_sha256'] = {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                               for p in sources}
    with args.output.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps({'status': result['status'], **result['coverage'],
                      'controls': result['controls'], 'algorithm_seconds': result['algorithm_seconds']}, sort_keys=True))


if __name__ == '__main__':
    main()
