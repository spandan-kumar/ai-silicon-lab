"""Compare complete marked-frontier JSONL scans case by case.

This checks coverage, counters and witnesses, not a third enumeration method.
Actual process exit statuses/source snapshots must be retained separately.
The producer counts the zero polar coset; symbolic scanners omit it.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import time

import verify_norm_frontier_pairs as symbolic


def check(state, record, independent=False):
    assert type(record['complete']) is bool
    lefts = record['left_forms']
    assert type(lefts) is int and 0 < lefts <= 8191
    hist = record['right_kernel_dimension_histogram']
    assert len(hist) == 14 and all(type(n) is int and n >= 0 for n in hist)
    assert sum(hist) == lefts
    if record['complete']:
        assert lefts == 8191
    old = [int(value, 0) for value in state['nonlinear_rref_hex']]
    assert len(old) == len(symbolic.low_rows(old)) == 5
    assert all(not form & symbolic.AFFINE for form in old)
    old_forms = [symbolic.combine(old, s) for s in range(32)]
    selectors = [s for s, form in enumerate(old_forms) if not form & symbolic.HIGH]
    polars = [symbolic.polar(old_forms[s]) for s in selectors]
    Kdim = record['K_dimension']
    assert len(selectors) == len(set(polars)) == 1 << Kdim
    assert record['high_rank'] + Kdim == 5
    if independent:
        assert record['K_all_selectors'] == selectors and record['K_all_polars'] == polars
    else:
        assert len(record['K_polars']) == len(record['K_gate_selectors']) == Kdim
        assert set(symbolic.span(record['K_polars'])) == set(polars)
        for selector, polar in zip(record['K_gate_selectors'], record['K_polars']):
            assert type(selector) is int and 0 <= selector < 32
            assert not old_forms[selector] & symbolic.HIGH
            assert symbolic.polar(old_forms[selector]) == polar
        assert record['source_code'] == state['first_source']['code']
        assert record['source_polar_coset'] == state['first_source']['polar_coset']
    assert [mark['Q_polar'] for mark in record['marks']] == state['marked_Q_polars']
    Krows = symbolic.low_rows(polars)
    statuses = []
    replays = 0
    for mark in record['marks']:
        q = mark['Q_polar']
        assert q in polars and symbolic.matrix_rank(q) == 8
        decoder = mark['Q_old_gate_selector']
        assert type(decoder) is int and decoder in selectors
        assert symbolic.polar(old_forms[decoder]) == q
        status = mark['status']
        assert status in ('positive', 'negative')
        statuses.append(status)
        if status == 'negative':
            assert record['complete']
            continue
        left, right, cancel = (mark[key] for key in ('left_mask', 'right_mask', 'old_gate_selector'))
        assert all(type(n) is int for n in (left, right, cancel))
        assert 0 < left <= right < 8192 and 0 <= cancel < 32
        replay = symbolic.witness_replay(list(symbolic.RAW) + old,
                                         old_forms, left, right, cancel, q)
        assert replay['candidate_anf_hex'] == hex(int(mark['t_anf_hex'], 0))
        assert replay['candidate_polar'] == mark['t_polar']
        assert mark['t_polar'] ^ q == mark['t_plus_Q_polar']
        assert symbolic.reduce(mark['t_polar'], Krows)
        replays += 1
    assert record['witness_truth_rows'] == 256 * replays
    assert record['complete'] or all(s == 'positive' for s in statuses)
    return statuses, replays


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--producer', type=Path, nargs='+', required=True)
    parser.add_argument('--independent', type=Path, nargs='+', required=True)
    parser.add_argument('--out', type=Path, required=True)
    args = parser.parse_args()
    assert __debug__ and not args.out.exists()
    start = time.monotonic()
    raw = args.input.read_bytes()
    source = json.loads(raw)
    groups = source['groups']
    producer, producer_sources = symbolic.read_producer_jsonl(args.producer)
    independent, independent_sources = symbolic.read_producer_jsonl(args.independent)
    expected_ids = set(range(len(groups)))
    assert set(producer) == set(independent) == expected_ids
    statuses = Counter()
    totals = Counter()
    full_counter_comparisons = 0
    for index, state in enumerate(groups):
        actual, reference = independent[index], producer[index]
        ours, actual_replays = check(state, actual, True)
        theirs, reference_replays = check(state, reference)
        assert ours == theirs, (index, 'verdicts')
        assert actual['K_dimension'] == reference['K_dimension']
        if 'negative' in ours:
            assert actual['complete'] and reference['complete']
            for key in ('left_forms', 'eligible_unordered_pairs', 'right_kernel_dimension_histogram'):
                assert actual[key] == reference[key], (index, key)
            assert actual['quadratic_nonzero_cosets'] + 1 == reference['quadratic_polar_cosets']
            full_counter_comparisons += 1
        statuses.update(ours)
        totals.update({'states': 1, 'Q_marks': len(ours),
                       'left_forms': actual['left_forms'],
                       'eligible_pairs': actual['eligible_unordered_pairs'],
                       'nonzero_cosets': actual['quadratic_nonzero_cosets'],
                       'positive_witness_replays': actual_replays + reference_replays})
    result = {'status': 'pass', 'scope': 'Exact coverage and every-case comparison of supplied marked frontier only; no other branches or novelty claim.',
              'totals': dict(totals), 'Q_statuses': dict(statuses),
              'fully_negative_counter_comparisons': full_counter_comparisons,
              'all_input_states_and_marks_checked': True,
              'input_sha256': hashlib.sha256(raw).hexdigest(),
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
              'symbolic_helper_sha256': hashlib.sha256(Path(symbolic.__file__).read_bytes()).hexdigest(),
              'producer_sources': producer_sources, 'independent_sources': independent_sources,
              'external_peer_review': False, 'algorithm_seconds': time.monotonic() - start}
    with args.out.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
