"""Exploratory rank-six scalar census: three independent raw operand pairs.

This treats four ANDs on SIX input bits, not the full eight-input field
problem. It reuses the existing symbolic row-equation primitives; it is
not an independent replay or a proof covering other raw-rank branches.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

from verify_norm_q5_first8 import (
    column_equations, combine, degree, equation_kernel, low_rows,
    matrix_rank, multiply, packed_polar, support,
)

RAW = [1 << (1 << i) for i in range(6)]
HIGH = sum(1 << m for m in range(64) if m.bit_count() > 2)


def prefix(code):
    assert 0 <= code < 64
    forms = list(RAW)
    factors = []
    bits = code
    for gate in range(3):
        mask = (1 << gate) - 1
        left, bits = bits & mask, bits >> gate
        right, bits = bits & mask, bits >> gate
        left = 1 << (2 * gate) | left << 6
        right = 1 << (2 * gate + 1) | right << 6
        factors.append([left, right])
        forms.append(multiply(combine(forms, left), combine(forms, right)))
    assert not bits and len(low_rows(forms)) == 9
    return forms, factors


def evaluate(form, point):
    return sum(point & m == m for m in support(form)) & 1


def scan(code):
    forms, factors = prefix(code)
    old = forms[6:]
    old_space = [combine(old, selector) for selector in range(8)]
    offsets = [packed_polar(p) for p in old_space if not p & HIGH]
    Krows = low_rows(offsets)
    products = [[multiply(a, b) for b in forms] for a in forms]
    cosets = {}
    pairs = 0
    kernel_histogram = Counter()
    witness = None
    admitted = []
    for left in range(1, 512):
        columns = [combine([products[i][j] for i in range(9)], left)
                   for j in range(9)]
        high_columns = [p & HIGH for p in columns + old]
        joint = equation_kernel(column_equations(high_columns), 12)
        # Project the complete joint nullspace to nine right coefficients.
        lifted = {}
        for vector in joint:
            right = vector & 511
            while right:
                pivot = (right & -right).bit_length() - 1
                if pivot not in lifted:
                    lifted[pivot] = vector
                    break
                vector ^= lifted[pivot]
                right = vector & 511
        basis = list(lifted.values())
        kernel_histogram[len(basis)] += 1
        for selector in range(1, 1 << len(basis)):
            solution = combine(basis, selector)
            right, cancel = solution & 511, solution >> 9
            assert right and cancel < 8
            if right < left:
                continue
            pairs += 1
            residue = combine(columns, right) ^ old_space[cancel]
            assert not residue & HIGH
            packed = packed_polar(residue)
            key = packed
            for bit in sorted(Krows):
                if key >> bit & 1:
                    key ^= Krows[bit]
            if key in cosets:
                continue
            maximum = max(matrix_rank(packed ^ offset) for offset in offsets)
            cosets[key] = maximum
            if maximum == 6:
                choices = []
                for extra, p in enumerate(old_space):
                    if p & HIGH or matrix_rank(packed ^ packed_polar(p)) != 6:
                        continue
                    scalar = residue ^ p
                    decoder = cancel ^ extra
                    assert scalar == multiply(combine(forms, left), combine(forms, right)) ^ old_space[decoder]
                    choices.append({'polar': packed_polar(scalar),
                                    'scalar_anf_hex': hex(scalar), 'old_decoder': decoder})
                assert choices
                admitted.append({'polar_coset': key, 'left': left, 'right': right,
                                 'rank6_choices': choices})
            if maximum == 6 and witness is None:
                decoder = next(s for s, p in enumerate(old_space)
                               if not p & HIGH and matrix_rank(packed ^ packed_polar(p)) == 6)
                decoder ^= cancel
                scalar = multiply(combine(forms, left), combine(forms, right)) ^ old_space[decoder]
                assert degree(scalar) == 2 and matrix_rank(packed_polar(scalar)) == 6
                for point in range(64):
                    wires = point
                    for gate, (a, b) in enumerate(factors):
                        value = ((wires & a).bit_count() & 1) * ((wires & b).bit_count() & 1)
                        assert value == evaluate(old[gate], point)
                        wires |= value << (6 + gate)
                    value = ((wires & left).bit_count() & 1) * ((wires & right).bit_count() & 1)
                    value ^= ((wires >> 6 & decoder).bit_count() & 1)
                    assert value == evaluate(scalar, point)
                witness = {'left': left, 'right': right, 'old_decoder': decoder,
                           'scalar_anf_hex': hex(scalar), 'truth_rows_checked': 64}
    assert sum(kernel_histogram.values()) == 511
    return {'code': code, 'prefix_degrees': list(map(degree, old)),
            'complete': True, 'lefts': 511, 'eligible_pairs': pairs,
            'K_dimension': len(Krows), 'cosets': len(cosets),
            'maximum_rank_histogram': dict(Counter(cosets.values())),
            'kernel_histogram': dict(kernel_histogram), 'rank6_witness': witness,
            'admitted_rank6_cosets': admitted}


def canonical_rows(values):
    rows = {}
    for value in values:
        while value:
            pivot = value.bit_length() - 1
            if pivot not in rows:
                rows[pivot] = value
                break
            value ^= rows[pivot]
    for pivot in sorted(rows):
        for other in rows:
            if other != pivot and rows[other] >> pivot & 1:
                rows[other] ^= rows[pivot]
    return tuple(rows[p] for p in sorted(rows, reverse=True))


def lifted_frontier(cases):
    affine = 1 | sum(RAW)
    fresh_xy = 1 << ((1 << 6) | (1 << 7))
    fresh_polar = packed_polar(fresh_xy)
    spaces = {}
    sources = marks = 0
    old_rank6_codes = []
    for case in cases:
        code = case['code']
        forms, _ = prefix(code)
        old = forms[6:]
        if any(degree(p) <= 2 and matrix_rank(packed_polar(p)) == 6
               for p in (combine(old, s) for s in range(8))):
            old_rank6_codes.append(code)
        if code == 0:
            # Requires the separate all-quadratic-first-four FIELD argument.
            # Not all these scalar extensions already lie in W3.
            continue
        for entry in case['admitted_rank6_cosets']:
            sources += 1
            product = multiply(combine(forms, entry['left']), combine(forms, entry['right']))
            actual_rows = [p & ~affine for p in old + [product]] + [fresh_xy]
            basis = canonical_rows(actual_rows)
            assert len(basis) == 5
            qmarks = set()
            for choice in entry['rank6_choices']:
                scalar = int(choice['scalar_anf_hex'], 0)
                assert scalar == product ^ combine(old, choice['old_decoder'])
                assert degree(scalar) == 2 and matrix_rank(packed_polar(scalar)) == 6
                equivalent_rows = [p & ~affine for p in old + [scalar]] + [fresh_xy]
                assert canonical_rows(equivalent_rows) == basis
                q = choice['polar'] ^ fresh_polar
                assert matrix_rank(q) == 8
                qmarks.add(q)
            marks += len(qmarks)
            if basis not in spaces:
                spaces[basis] = {'nonlinear_rref_hex': list(map(hex, basis)),
                                 'first_source': {'code': code, 'polar_coset': entry['polar_coset']},
                                 'source_spaces': 0, 'marked_Q_polars': set()}
            spaces[basis]['source_spaces'] += 1
            spaces[basis]['marked_Q_polars'].update(qmarks)
    assert old_rank6_codes == [0]
    groups = list(spaces.values())
    for group in groups:
        group['marked_Q_polars'] = sorted(group['marked_Q_polars'])
    return {'summary': {'status': 'pass', 'independent_replay': False,
                        'scope': 'First-four raw rank six, first-three raw rank six; field code-zero exclusion is a separate dependency.',
                        'source_scalar_cosets': sources, 'source_rank8_marks': marks,
                        'distinct_fixed_coordinate_W5_spaces': len(groups),
                        'union_marked_scalar_choices': sum(len(g['marked_Q_polars']) for g in groups),
                        'maximum_marks_per_space': max(len(g['marked_Q_polars']) for g in groups),
                        'only_rank6_by_three_code': 0,
                        'full_field_continuations_tested': False},
            'groups': groups}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--frontier-out', type=Path)
    args = parser.parse_args()
    assert not args.out.exists()
    start = time.monotonic()
    cases = [scan(code) for code in range(64)]
    result = {'status': 'pass', 'scope': 'four-AND/six-input scalar, first-three raw rank six only',
              'independent_replay': False,
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'cases': cases,
              'third_gate_degree_histogram': dict(Counter(c['prefix_degrees'][2] for c in cases)),
              'admitting_rank6_by_third_gate_degree': dict(Counter(
                  c['prefix_degrees'][2] for c in cases if c['rank6_witness'])),
              'algorithm_seconds': time.monotonic() - start}
    if args.frontier_out is not None:
        frontier = lifted_frontier(cases)
        frontier['source_sha256'] = result['source_sha256']
        with args.frontier_out.open('x') as handle:
            json.dump(frontier, handle, indent=2)
            handle.write('\n')
        tsv = args.frontier_out.with_suffix('.tsv')
        with tsv.open('x') as handle:
            for index, group in enumerate(frontier['groups']):
                source = group['first_source']
                marks = group['marked_Q_polars']
                handle.write(' '.join(map(str, [index, source['code'], source['polar_coset'], len(marks)]))
                             + ' ' + ' '.join(group['nonlinear_rref_hex'])
                             + ' ' + ' '.join(map(str, marks)) + '\n')
        result['lifted_frontier_summary'] = frontier['summary']
        result['frontier_tsv_sha256'] = hashlib.sha256(tsv.read_bytes()).hexdigest()
        result['frontier_export_seconds'] = time.monotonic() - start - result['algorithm_seconds']
    with args.out.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}))


if __name__ == '__main__':
    main()
