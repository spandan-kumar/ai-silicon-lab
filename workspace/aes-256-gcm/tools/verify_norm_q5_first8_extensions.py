"""Full symbolic replay of the proper first-eight one-product inventory.

Imports the independently reasoned monomial-union / joint-row-equation
enumerator, not the truth/Mobius producer. Repeats complete one-product scans,
then checks every retained product and every marked rank-8 scalar offset.
Same research author: algorithmic independence is not external peer review.
"""
import argparse
from concurrent.futures import ProcessPoolExecutor
import hashlib
import json
from pathlib import Path
import time

import verify_norm_q5_first8 as symbolic


COMPARE_FIELDS = (
    'code', 'factors', 'degrees', 'high_rank', 'quadratic_offset_dimension',
    'complete', 'lefts', 'pairs', 'polar_cosets', 'maximum_rank_histogram',
    'right_kernel_histogram',
)


def replay(case):
    start = time.monotonic()
    independent = symbolic.scan(case['code'], require_quintic=False)
    for field in COMPARE_FIELDS:
        assert independent[field] == case[field], (case['code'], field)
    assert independent['maximum_rank_histogram'][8] == len(case['admitted'])
    forms, factors = symbolic.prefix(case['code'])
    assert factors == case['factors']
    assert all(symbolic.degree(f) <= 4 for f in forms[8:])
    truths = list(map(symbolic.truth, forms))
    old = forms[8:]
    old_forms = [symbolic.combine(old, s) for s in range(16)]
    old_truths = [symbolic.truth(f) for f in old_forms]
    K = [s for s, f in enumerate(old_forms) if not f & symbolic.HIGH]
    offsets = {s: symbolic.packed_polar(old_forms[s]) for s in K}
    assert len(K) == 1 << independent['quadratic_offset_dimension']
    assert not any(symbolic.matrix_rank(p) == 8 for p in offsets.values())
    unique_cosets = set()
    marked_choices = product_checks = offset_checks = 0
    for admission in case['admitted']:
        left, right = admission['left'], admission['right']
        assert 0 < left <= right < 4096
        product = symbolic.multiply(symbolic.combine(forms, left),
                                    symbolic.combine(forms, right))
        actual_product_truth = (symbolic.combine(truths, left)
                                & symbolic.combine(truths, right))
        assert symbolic.truth(product) == actual_product_truth
        product_checks += 1
        base = admission['base_gate_cancel']
        assert 0 <= base < 16
        residue = product ^ old_forms[base]
        assert not residue & symbolic.HIGH
        p = symbolic.packed_polar(residue)
        key = min(p ^ offset for offset in offsets.values())
        assert key == admission['polar_coset'] and key not in unique_cosets
        unique_cosets.add(key)
        expected = {}
        for k, offset in offsets.items():
            candidate_polar = p ^ offset
            offset_checks += 1
            if symbolic.matrix_rank(candidate_polar) == 8:
                expected[base ^ k] = candidate_polar
        actual = {q['gate_decoder']: q['polar'] for q in admission['rank8_choices']}
        assert len(actual) == len(admission['rank8_choices'])
        assert actual == expected and actual
        for decoder, candidate_polar in actual.items():
            scalar = product ^ old_forms[decoder]
            assert not scalar & symbolic.HIGH
            assert symbolic.packed_polar(scalar) == candidate_polar
            assert symbolic.matrix_rank(candidate_polar) == 8
            assert symbolic.truth(scalar) == actual_product_truth ^ old_truths[decoder]
            marked_choices += 1
    # Full independent enumeration establishes the total number of admitted
    # cosets; distinct valid witnesses of that cardinality establish coverage.
    assert len(unique_cosets) == independent['maximum_rank_histogram'][8]
    assert len(unique_cosets) == case['rank8_cosets']
    assert marked_choices == case['rank8_choices']
    assert 256*marked_choices == case['replayed_truth_rows']
    independent['admitted_inventory_audit'] = {
        'status': 'pass', 'cosets_checked': len(unique_cosets),
        'marked_scalar_choices_checked': marked_choices,
        'symbolic_product_truth_rows_checked': 256*product_checks,
        'marked_scalar_truth_rows_checked': 256*marked_choices,
        'all_K4_offset_rank_checks': offset_checks,
        'sorted_admitted_min_cosets_sha256': hashlib.sha256(json.dumps(
            sorted(unique_cosets), separators=(',', ':')).encode()).hexdigest(),
        'choice_completeness': 'All rank-8 K4 offsets of each actual product are retained.',
        'coset_completeness': 'Independent complete rank8 count equals number of distinct witnessed cosets.',
    }
    independent['combined_algorithm_seconds'] = time.monotonic()-start
    return independent


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--out', required=True)
    parser.add_argument('--jobs', type=int, default=1)
    parser.add_argument('--limit', type=int)
    args = parser.parse_args()
    assert args.jobs > 0
    output = Path(args.out)
    assert not output.exists()
    start = time.monotonic()
    raw = Path(args.input).read_bytes()
    source = json.loads(raw)
    cases = source['cases'] if args.limit is None else source['cases'][:args.limit]
    assert cases and source['complete']
    if args.jobs == 1:
        results = [replay(case) for case in cases]
    else:
        with ProcessPoolExecutor(max_workers=args.jobs) as pool:
            results = list(pool.map(replay, cases))
    result = {
        'status': 'pass',
        'algorithm': 'Boolean-ring monomial-union products, joint row-equation kernel, low-pivot polar rank',
        'external_peer_review': False,
        'scope': 'Full independent one-product scans and all retained marked scalar offsets for supplied proper r4=8 representatives; not a field-continuation result.',
        'producer_inventory_sha256': hashlib.sha256(raw).hexdigest(),
        'source_helpers_sha256': hashlib.sha256(Path(symbolic.__file__).read_bytes()).hexdigest(),
        'verifier_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        'jobs': args.jobs,
        'prefixes_checked': len(results),
        'full_supplied_inventory_checked': len(results) == len(source['cases']),
        'lefts_checked': sum(r['lefts'] for r in results),
        'pairs_checked': sum(r['pairs'] for r in results),
        'polar_cosets_checked': sum(r['polar_cosets'] for r in results),
        'admitted_cosets_checked': sum(r['admitted_inventory_audit']['cosets_checked'] for r in results),
        'marked_scalar_choices_checked': sum(r['admitted_inventory_audit']['marked_scalar_choices_checked'] for r in results),
        'algorithm_seconds': time.monotonic()-start,
        'cases': results,
    }
    with output.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k != 'cases'}, indent=2))


if __name__ == '__main__':
    main()
