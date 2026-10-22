"""Independent truth-table replay of the rank-six scalar/lifted frontier.

Six input bits, first three ANDs' six raw factors independent. Actual
truth-table AND and Mobius transforms build products; labelled HIGH-column
elimination constructs right kernels. No producer or symbolic-scanner
imports. Every retained scalar mark, actual product/decoder, full nonlinear
wire span and lifted TSV record is checked. Code zero is retained in the
scalar census; omitting it in the lifted field frontier needs the separate
all-quadratic-first-four field argument, not scalar equivalence.

This is an independent numerical method within the same research team,
not external peer review, a formal certificate or a global field bound.
"""
import argparse
from collections import Counter
import hashlib
import itertools
import json
from pathlib import Path
import random
import time


RAW = tuple(1 << (1 << i) for i in range(6))
HIGH = sum(1 << mask for mask in range(64) if mask.bit_count() > 2)
AFFINE = 1 | sum(RAW)
PAIRS = tuple(itertools.combinations(range(8), 2))
FRESH_XY = 1 << ((1 << 6) | (1 << 7))


def combine(rows, selector):
    value = 0
    for j, row in enumerate(rows):
        if selector >> j & 1:
            value ^= row
    return value


def mobius(value):
    for bit in range(6):
        for mask in range(64):
            if mask >> bit & 1 and value >> (mask ^ (1 << bit)) & 1:
                value ^= 1 << mask
    return value


def truth_direct(form):
    return sum((sum((form >> mask & 1) for mask in range(64)
                    if point & mask == mask) & 1) << point
               for point in range(64))


def polar(form):
    return sum(((form >> ((1 << a) | (1 << b))) & 1) << i
               for i, (a, b) in enumerate(PAIRS))


def rank(packed):
    rows = [0] * 8
    for bit, (a, b) in enumerate(PAIRS):
        if packed >> bit & 1:
            rows[a] ^= 1 << b
            rows[b] ^= 1 << a
    return len(canonical_rows(rows))


def canonical_rows(values):
    """Full Gauss-Jordan sweep, not producer's incremental insertion method."""
    rows = list(values)
    used = 0
    for bit in range(max((row.bit_length() for row in rows), default=0) - 1, -1, -1):
        pivot = next((j for j in range(used, len(rows)) if rows[j] >> bit & 1), None)
        if pivot is None:
            continue
        rows[pivot], rows[used] = rows[used], rows[pivot]
        for j in range(len(rows)):
            if j != used and rows[j] >> bit & 1:
                rows[j] ^= rows[used]
        used += 1
    assert not any(rows[used:])
    return tuple(rows[:used])


def reduce(value, basis):
    for row in basis:
        if value >> (row.bit_length() - 1) & 1:
            value ^= row
    return value


def kernel(columns):
    """Labelled high-pivot COLUMN elimination; each dependence is a right form."""
    pivots = {}
    result = []
    for j, value in enumerate(columns):
        selector = 1 << j
        while value:
            top = value.bit_length() - 1
            if top not in pivots:
                pivots[top] = (value, selector)
                break
            row, label = pivots[top]
            value ^= row
            selector ^= label
        if not value:
            assert selector and combine(columns, selector) == 0
            result.append(selector)
    assert len(result) + len(pivots) == len(columns)
    return result


def span(basis):
    values = [0]
    for row in basis:
        values += [old ^ row for old in values]
    return values


def make_prefix(code):
    truths = [sum(((point >> j) & 1) << point for point in range(64))
              for j in range(6)]
    bits = code
    factors = []
    for gate in range(3):
        mask = (1 << gate) - 1
        a, bits = bits & mask, bits >> gate
        b, bits = bits & mask, bits >> gate
        left = (1 << (2 * gate)) | (a << 6)
        right = (1 << (2 * gate + 1)) | (b << 6)
        factors.append((left, right))
        truths.append(combine(truths, left) & combine(truths, right))
    assert not bits
    forms = [mobius(value) for value in truths]
    assert tuple(forms[:6]) == RAW and len(canonical_rows(forms)) == 9
    for i, form in enumerate(forms):
        assert truth_direct(form) == truths[i]
    return forms, truths, factors


def scan(code):
    forms, truths, factors = make_prefix(code)
    old = forms[6:]
    old_space = [combine(old, s) for s in range(8)]
    offsets = [polar(value) for value in old_space if not value & HIGH]
    K = canonical_rows(offsets)
    assert len(set(offsets)) == len(offsets) == 1 << len(K)
    # Retain full old-wire representatives while reducing high components.
    high_rows = {}
    for form in old:
        value = form
        while value & HIGH:
            top = (value & HIGH).bit_length() - 1
            if top not in high_rows:
                high_rows[top] = value
                break
            value ^= high_rows[top]
    high_pivots = sorted(high_rows, reverse=True)

    def cancel_high(form):
        for pivot in high_pivots:
            if form >> pivot & 1:
                form ^= high_rows[pivot]
        return form

    products = [[mobius(a & b) for b in truths] for a in truths]
    reduced = [[cancel_high(value) for value in row] for row in products]
    for i, j in itertools.product(range(9), repeat=2):
        assert mobius(products[i][j]) == truths[i] & truths[j]
        assert products[i][j] ^ reduced[i][j] in old_space
    cosets = {}
    admitted = {}
    hist = Counter()
    pairs = 0
    columns, original = [0] * 9, [0] * 9
    previous = 0
    for left in range(1, 512):
        changed = previous ^ left
        previous = left
        for bit in range(9):
            if changed >> bit & 1:
                columns = [a ^ b for a, b in zip(columns, reduced[bit])]
                original = [a ^ b for a, b in zip(original, products[bit])]
        nullspace = kernel([value & HIGH for value in columns])
        hist[len(nullspace)] += 1
        for right in span(nullspace)[1:]:
            if right < left:
                continue
            pairs += 1
            residue = combine(columns, right)
            assert not residue & HIGH
            packed = polar(residue)
            key = reduce(packed, K)
            if key in cosets:
                continue
            marks = {packed ^ offset for offset in offsets
                     if rank(packed ^ offset) == 6}
            cosets[key] = max(rank(packed ^ offset) for offset in offsets)
            if marks:
                product = combine(original, right)
                assert product ^ residue in old_space
                assert mobius(product) == combine(truths, left) & combine(truths, right)
                admitted[key] = {'marks': marks, 'product': product}
    return {'code': code, 'forms': forms, 'truths': truths, 'factors': factors,
            'K': K, 'old_space': old_space, 'admitted': admitted,
            'counts': {'prefix_degrees': [max(mask.bit_count() for mask in range(64)
                                            if form >> mask & 1) for form in old],
                       'complete': True, 'lefts': 511, 'eligible_pairs': pairs,
                       'K_dimension': len(K), 'cosets': len(cosets),
                       'maximum_rank_histogram': dict(Counter(cosets.values())),
                       'kernel_histogram': dict(hist)}}


def controls():
    rng = random.Random(20261022)
    for _ in range(128):
        value = rng.getrandbits(64)
        assert mobius(mobius(value)) == value
        assert mobius(value) == truth_direct(value)
    checks = 0
    for width in range(10):
        for _ in range(16):
            columns = [rng.getrandbits(64) & HIGH for _ in range(width)]
            assert set(span(kernel(columns))) == {
                s for s in range(1 << width) if not combine(columns, s)}
            checks += 1
    # Preserve the full actual prefix and product for the explicit quartic example.
    forms, truths, _ = make_prefix(9)
    assert [max(m.bit_count() for m in range(64) if f >> m & 1)
            for f in forms[6:]] == [2, 3, 4]
    product = combine(truths, 40) & combine(truths, 132)
    scalar = mobius(product ^ combine(truths[6:], 7))
    assert not scalar & HIGH and rank(polar(scalar)) == 6
    assert mobius(scalar) == truth_direct(scalar)
    return {'status': 'pass', 'Mobius_direct_truth_controls': 128,
            'labelled_column_kernel_bruteforce_controls': checks,
            'quartic_prefix_code9_rank6_scalar': True, 'quartic_truth_rows': 64}


def audit(inventory, frontier, tsv):
    assert inventory['status'] == frontier['summary']['status'] == 'pass'
    assert [case['code'] for case in inventory['cases']] == list(range(64))
    rows = []
    expected_spaces = {}
    K_by_code = {}
    old_rank6_codes = []
    witness_rows = products_checked = marks_checked = 0
    fresh_polar = polar(FRESH_XY)
    for reference in inventory['cases']:
        code = reference['code']
        actual = scan(code)
        for key, value in actual['counts'].items():
            other = reference[key]
            if isinstance(value, dict):
                other = {int(k): v for k, v in other.items()}
            assert value == other, (code, key, value, other)
        old, truths, K = actual['forms'][6:], actual['truths'], actual['K']
        K_by_code[code] = K
        if any(not value & HIGH and rank(polar(value)) == 6
               for value in actual['old_space']):
            old_rank6_codes.append(code)
        producer_keys = set()
        for entry in reference['admitted_rank6_cosets']:
            key = reduce(entry['polar_coset'], K)
            assert key not in producer_keys and key in actual['admitted']
            producer_keys.add(key)
            left, right = entry['left'], entry['right']
            assert 1 <= left <= right < 512
            product_truth = combine(truths, left) & combine(truths, right)
            product = mobius(product_truth)
            ours = actual['admitted'][key]
            assert canonical_rows([f & ~AFFINE for f in old + [product]]) == canonical_rows(
                [f & ~AFFINE for f in old + [ours['product']]])
            marks = set()
            for choice in entry['rank6_choices']:
                scalar = int(choice['scalar_anf_hex'], 0)
                decoder = choice['old_decoder']
                assert 0 <= decoder < 8
                assert scalar == product ^ combine(old, decoder)
                assert mobius(scalar) == product_truth ^ combine(truths[6:], decoder)
                assert not scalar & HIGH and polar(scalar) == choice['polar']
                assert rank(choice['polar']) == 6
                assert choice['polar'] not in marks
                marks.add(choice['polar'])
                witness_rows += 64
            assert marks == ours['marks']
            products_checked += 1
            marks_checked += len(marks)
            if code:
                basis = canonical_rows([f & ~AFFINE for f in old + [ours['product']]] + [FRESH_XY])
                assert len(basis) == 5
                lifted_marks = {p ^ fresh_polar for p in marks}
                assert all(rank(p) == 8 for p in lifted_marks)
                if basis not in expected_spaces:
                    expected_spaces[basis] = {'marks': set(), 'sources': set()}
                expected_spaces[basis]['marks'].update(lifted_marks)
                expected_spaces[basis]['sources'].add((code, key))
        assert producer_keys == set(actual['admitted'])
        rows.append({'code': code, **actual['counts'],
                     'rank6_cosets': len(producer_keys),
                     'all_count_and_offset_comparisons_pass': True})
    assert old_rank6_codes == [0]
    groups = frontier['groups']
    assert len(groups) == len(expected_spaces) == 6120
    seen = set()
    for group in groups:
        basis = tuple(int(value, 0) for value in group['nonlinear_rref_hex'])
        assert basis == canonical_rows(basis) and basis not in seen
        seen.add(basis)
        assert basis in expected_spaces
        expected = expected_spaces[basis]
        assert set(group['marked_Q_polars']) == expected['marks']
        assert len(group['marked_Q_polars']) == len(expected['marks'])
        assert group['source_spaces'] == len(expected['sources'])
        code = group['first_source']['code']
        source = (code, reduce(group['first_source']['polar_coset'], K_by_code[code]))
        assert source in expected['sources']
    assert seen == set(expected_spaces)
    lines = tsv.splitlines()
    assert len(lines) == len(groups)
    for index, (line, group) in enumerate(zip(lines, groups)):
        fields = line.split()
        count = len(group['marked_Q_polars'])
        source = group['first_source']
        assert list(map(int, fields[:4])) == [index, source['code'], source['polar_coset'], count]
        assert fields[4:9] == group['nonlinear_rref_hex']
        assert list(map(int, fields[9:])) == group['marked_Q_polars']
    assert sum(len(g['marked_Q_polars']) for g in groups) == 6552
    return {'status': 'pass', 'per_code': rows,
            'prefix_codes': 64, 'left_forms': 64 * 511,
            'eligible_pairs': sum(row['eligible_pairs'] for row in rows),
            'quadratic_cosets': sum(row['cosets'] for row in rows),
            'rank6_admitted_cosets': products_checked,
            'rank6_scalar_marks_replayed': marks_checked,
            'scalar_witness_truth_rows': witness_rows,
            'only_rank6_by_three_code': old_rank6_codes,
            'distinct_lifted_spaces': len(groups), 'lifted_Q_marks': 6552,
            'all_per_code_counts_histograms_agree': True,
            'all_scalar_offset_sets_agree': True,
            'actual_product_decoder_and_full_wire_space_checks': True,
            'all_lifted_groups_and_TSV_rows_agree': True,
            'code_zero_field_exclusion_is_separate_dependency': True}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inventory', type=Path)
    parser.add_argument('--frontier', type=Path)
    parser.add_argument('--tsv', type=Path)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert __debug__ and not args.out.exists()
    start = time.monotonic()
    report = {'status': 'pass', 'controls': controls(),
              'algorithm': 'six-bit truth AND/Mobius, high-column quotient kernels, all old quadratic offsets, full Gauss-Jordan wire spans',
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'external_peer_review': False, 'full_field_continuations_tested': False,
              'scope': 'First-four raw rank six / first-three raw rank six scalar frontier only. No other raw-rank coverage, full field exclusion or novelty claim.'}
    if args.inventory:
        assert args.frontier and args.tsv
        inputs = [args.inventory, args.frontier, args.tsv]
        report['input_identities'] = [
            {'path': str(path), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()}
            for path in inputs]
        report['audit'] = audit(json.loads(args.inventory.read_text()),
                                json.loads(args.frontier.read_text()), args.tsv.read_text())
    report['algorithm_seconds'] = time.monotonic() - start
    with args.out.open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print(json.dumps({key: value if key != 'audit' else {k: v for k, v in value.items() if k != 'per_code'}
                      for key, value in report.items()}, indent=2))


if __name__ == '__main__':
    main()
