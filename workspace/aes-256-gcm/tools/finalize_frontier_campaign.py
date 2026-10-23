"""Finalize preserved native scans; never execute or silently restart a scan.

Ports the run-local full streaming comparison, adding a pinned portable recipe,
fresh outputs, source-inventory replay and checks of both supervisors' actual
terminal evidence. Assertions are mathematical checks, so optimized Python is
explicitly refused. Historical absolute paths are mapped, not rewritten.
"""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import sys
import time

import verify_norm_frontier_pairs as symbolic


def digest(path):
    value = hashlib.sha256()
    with path.open('rb') as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b''):
            value.update(block)
    return value.hexdigest()


def load(path):
    return json.loads(path.read_bytes())


class Evidence:
    def __init__(self, root, recipe):
        self.root = root.resolve()
        self.recipe = recipe
        self.checked_hashes = {}

    def path(self, relative):
        path = Path(relative)
        if path.is_absolute() or '..' in path.parts:
            raise ValueError('Evidence paths must be root-relative: ' + relative)
        result = (self.root / path).resolve()
        if not result.is_relative_to(self.root):
            raise ValueError('Evidence path escapes root: ' + relative)
        return result

    def historical(self, absolute):
        relative = Path(absolute).relative_to(self.recipe['legacy_root']).as_posix()
        return self.path(relative)

    def verify(self):
        for relative, expected in self.recipe['pinned_files'].items():
            actual = digest(self.path(relative))
            if actual != expected:
                raise ValueError('Pinned evidence hash mismatch: ' + relative)
            self.checked_hashes[relative] = actual

    def pinned(self, path):
        relative = path.relative_to(self.root).as_posix()
        if relative not in self.checked_hashes:
            raise ValueError('Evidence was not pinned: ' + relative)
        return self.checked_hashes[relative]


def check_marks(record, qs, old_forms, Krows):
    assert [mark['Q_polar'] for mark in record['marks']] == qs
    assert len(set(qs)) == len(qs)
    statuses = []
    replays = 0
    for mark in record['marks']:
        q = mark['Q_polar']
        selector = mark['Q_old_gate_selector']
        assert type(selector) is int and 0 <= selector < 32
        assert not old_forms[selector] & symbolic.HIGH
        assert symbolic.polar(old_forms[selector]) == q
        assert symbolic.matrix_rank(q) == 8
        status = mark['status']
        assert status in ('positive', 'negative')
        if status == 'negative':
            assert record['complete']
        statuses.append(status)
        if status != 'positive':
            continue
        left, right, cancel = (mark[key] for key in
                               ('left_mask', 'right_mask', 'old_gate_selector'))
        assert all(type(value) is int for value in (left, right, cancel))
        assert 0 < left <= right < 8192 and 0 <= cancel < 32
        old = [old_forms[1 << i] for i in range(5)]
        replay = symbolic.witness_replay(list(symbolic.RAW) + old,
            old_forms, left, right, cancel, q)
        assert replay['candidate_anf_hex'] == hex(int(mark['t_anf_hex'], 0))
        assert replay['candidate_polar'] == mark['t_polar']
        assert mark['t_polar'] ^ q == mark['t_plus_Q_polar']
        assert symbolic.reduce(mark['t_polar'], Krows)
        replays += 1
    assert record['witness_truth_rows'] == 256 * replays
    return statuses, replays


def check_integrity(record):
    assert type(record['complete']) is bool
    lefts = record['left_forms']
    assert type(lefts) is int and 0 < lefts <= 8191
    histogram = record['right_kernel_dimension_histogram']
    assert len(histogram) == 14
    assert all(type(value) is int and value >= 0 for value in histogram)
    assert sum(histogram) == lefts
    if record['complete']:
        assert lefts == 8191
    else:
        assert all(mark['status'] == 'positive' for mark in record['marks'])


def preflight(evidence):
    recipe = evidence.recipe
    assert recipe['schema_version'] == 1
    assert recipe['kind'] == 'legacy-frontier-pair-finalization'
    evidence.verify()
    # --root may refer to a restored evidence tree, whereas Python imports the
    # helper beside this script. Bind the code actually used to the pinned copy.
    helper = evidence.path(recipe['symbolic_helper'])
    if digest(Path(symbolic.__file__)) != evidence.pinned(helper):
        raise ValueError('Imported symbolic helper differs from pinned evidence.')
    independent = evidence.path(recipe['independent_dir'])
    producer = evidence.path(recipe['producer_dir'])
    expected = recipe['expected']
    assert all(type(value) is int and value > 0 for value in expected.values())
    assert expected['states'] == expected['shards'] * expected['states_per_shard']
    manifest = load(independent / 'manifest.json')
    execution = load(independent / 'execution-complete.json')
    assert execution['status'] == 'pass'
    assert execution['shard_exit_codes'] == [0] * expected['shards']
    assert manifest['states'] == expected['states']
    assert manifest['marked_scalar_choices'] == expected['marked_Q_choices']
    assert manifest['shards'] == expected['shards']
    assert manifest['states_per_shard'] == expected['states_per_shard']
    assert manifest['assertions_enabled'] is True
    assert manifest['every_TSV_row_matched_to_fixed_coordinate_source'] is True
    assert manifest['compile_record']['exit_code'] == 0
    assert '-DNDEBUG' not in manifest['compile_record']['argv']
    for field in ('source', 'executable', 'input'):
        path = evidence.historical(manifest[field]['frozen_path'])
        assert evidence.pinned(path) == manifest[field]['sha256']
        assert path.stat().st_size == manifest[field]['bytes']
    producer_manifest = load(producer / 'launch-manifest.json')
    producer_terminal = load(producer / 'terminal-status.json')
    coverage = load(producer / 'coverage-audit.json')
    assert producer_terminal['status'] == coverage['status'] == 'pass'
    assert producer_manifest['assertions_enabled'] is True
    assert producer_manifest['automatic_restarts'] is False
    assert producer_manifest['compile_record']['exit_code'] == 0
    assert '-DNDEBUG' not in producer_manifest['compile_record']['argv']
    assert producer_manifest['expected_states'] == coverage['states'] == expected['states']
    assert producer_manifest['expected_Q_marks'] == coverage['Q_marks'] == expected['marked_Q_choices']
    assert producer_manifest['input_sha256'] == manifest['input']['sha256']
    assert len(producer_terminal['commands']) == len(producer_manifest['shards']) == expected['shards']
    assert len(coverage['shards']) == expected['shards']
    for field in ('source', 'binary', 'input'):
        assert producer_terminal[field + '_sha256_after'] == producer_manifest[field + '_sha256']
        assert evidence.pinned(evidence.historical(producer_manifest[field + '_path'])) == producer_manifest[field + '_sha256']
    # Do not trust an old flag: repeat the complete TSV-to-inventory mapping.
    source_path = evidence.path(recipe['fixed_coordinate_source'])
    assert evidence.pinned(source_path) == manifest['fixed_coordinate_source_sha256']
    groups = load(source_path)['groups']
    assert len(groups) == expected['states']
    marks = 0
    input_path = evidence.historical(manifest['input']['frozen_path'])
    with input_path.open() as handle:
        for state_id, group in enumerate(groups):
            words = handle.readline().split()
            assert len(words) >= 10
            index, code, coset, count = map(int, words[:4])
            assert index == state_id and count in (1, 2) and len(words) == 9 + count
            assert code == group['first_source']['code']
            assert coset == group['first_source']['polar_coset']
            assert [int(value, 0) for value in words[4:9]] == [int(value, 0) for value in group['nonlinear_rref_hex']]
            assert list(map(int, words[9:])) == group['marked_Q_polars']
            marks += count
        assert not handle.readline()
    assert marks == expected['marked_Q_choices']
    for shard in range(expected['shards']):
        item = producer_manifest['shards'][shard]
        command = load(producer / f'shard-{shard}.command.json')
        assert item['shard'] == shard and item['begin'] == shard * expected['states_per_shard']
        assert item['count'] == expected['states_per_shard']
        assert item['end_exclusive'] == item['begin'] + item['count']
        assert command == producer_terminal['commands'][shard]
        assert command['exit_code'] == 0
        for key, value in item.items():
            assert command[key] == value
        assert evidence.historical(item['output']) == producer / f'shard-{shard}.jsonl'
        assert command['argv'] == [producer_manifest['binary_path'], producer_manifest['input_path'],
            item['output'], '--begin', str(item['begin']), '--count', str(item['count'])]
        audited = coverage['shards'][shard]
        for filename, field in ((f'shard-{shard}.jsonl', 'output_sha256'),
                                (f'shard-{shard}.jsonl.summary.json', 'summary_sha256'),
                                (f'shard-{shard}.stdout.log', 'stdout_sha256'),
                                (f'shard-{shard}.stderr.log', 'stderr_sha256')):
            assert evidence.pinned(producer / filename) == audited[field]
        launch = load(independent / f'shard-{shard}.launch.json')
        terminal = load(independent / f'shard-{shard}.complete.json')
        assert terminal['exit_code'] == 0 and terminal['PID'] == launch['PID']
        for key, value in launch.items():
            assert terminal[key] == value
        assert launch['shard'] == shard and launch['begin'] == item['begin']
        assert launch['end_exclusive'] == item['end_exclusive']
        assert launch['expected_states'] == item['count']
        assert terminal['output_bytes'] == (independent / f'shard-{shard}.jsonl').stat().st_size
        assert evidence.historical(launch['argv'][0]) == evidence.historical(manifest['executable']['frozen_path'])
        assert evidence.historical(launch['argv'][1]) == input_path
        assert evidence.historical(launch['argv'][2]) == independent / f'shard-{shard}.jsonl'
        assert launch['argv'][3:] == ['--begin', str(item['begin']), '--count', str(item['count'])]
    return independent, producer, manifest, producer_manifest, coverage


def compare(evidence):
    start = time.monotonic()
    independent, producer, manifest, producer_manifest, coverage = preflight(evidence)
    expected = evidence.recipe['expected']
    next_id = total_marks = producer_replays = independent_replays = 0
    statuses = Counter()
    high_histogram, K_histogram, mark_histogram = Counter(), Counter(), Counter()
    lefts = pairs = nonzero_cosets = complete_states = producer_complete_states = 0
    kernel_histogram = [0] * 14
    shards = []
    input_path = evidence.historical(manifest['input']['frozen_path'])
    with input_path.open() as input_handle:
        for shard in range(expected['shards']):
            launch = load(independent / f'shard-{shard}.launch.json')
            terminal = load(independent / f'shard-{shard}.complete.json')
            assert launch['begin'] == next_id
            independent_path = independent / f'shard-{shard}.jsonl'
            producer_path = producer / f'shard-{shard}.jsonl'
            local_states = local_marks = local_pairs = local_lefts = local_nonzero = 0
            producer_lefts = producer_pairs = producer_cosets = 0
            independent_hash, producer_hash = hashlib.sha256(), hashlib.sha256()
            with independent_path.open('rb') as independent_handle, producer_path.open('rb') as producer_handle:
                for independent_line in independent_handle:
                    producer_line = producer_handle.readline()
                    assert independent_line.strip() and producer_line.strip(), ('truncated record', next_id)
                    independent_hash.update(independent_line)
                    producer_hash.update(producer_line)
                    actual, wanted = json.loads(independent_line), json.loads(producer_line)
                    words = input_handle.readline().split()
                    assert words
                    state_id, code, source_coset, nmarks = map(int, words[:4])
                    qs = list(map(int, words[9:]))
                    assert state_id == actual['state_id'] == wanted['state_id'] == next_id
                    assert (wanted['source_code'], wanted['source_polar_coset']) == (code, source_coset)
                    assert nmarks == len(qs) and len(words) == 9 + nmarks
                    check_integrity(actual)
                    check_integrity(wanted)
                    assert actual['high_rank'] == wanted['high_rank']
                    assert actual['K_dimension'] == wanted['K_dimension']
                    Kdim = actual['K_dimension']
                    assert actual['high_rank'] + Kdim == 5
                    old = [int(value, 0) for value in words[4:9]]
                    assert all(not value & symbolic.AFFINE for value in old)
                    old_forms = [symbolic.combine(old, selector) for selector in range(32)]
                    Kselectors = [s for s, form in enumerate(old_forms) if not form & symbolic.HIGH]
                    Kpolars = [symbolic.polar(old_forms[s]) for s in Kselectors]
                    assert len(Kselectors) == 1 << Kdim and len(set(Kpolars)) == len(Kpolars)
                    assert actual['K_all_selectors'] == Kselectors and actual['K_all_polars'] == Kpolars
                    assert len(wanted['K_polars']) == len(wanted['K_gate_selectors']) == Kdim
                    assert set(symbolic.span(wanted['K_polars'])) == set(Kpolars)
                    for selector, value in zip(wanted['K_gate_selectors'], wanted['K_polars']):
                        assert type(selector) is int and 0 <= selector < 32
                        assert not old_forms[selector] & symbolic.HIGH
                        assert symbolic.polar(old_forms[selector]) == value
                    Krows = symbolic.low_rows(Kpolars)
                    actual_statuses, ar = check_marks(actual, qs, old_forms, Krows)
                    wanted_statuses, wr = check_marks(wanted, qs, old_forms, Krows)
                    assert actual_statuses == wanted_statuses, ('verdict mismatch', next_id)
                    independent_replays += ar
                    producer_replays += wr
                    if 'negative' in wanted_statuses:
                        assert actual['complete'] and wanted['complete']
                        assert actual['left_forms'] == wanted['left_forms'] == 8191
                        assert actual['eligible_unordered_pairs'] == wanted['eligible_unordered_pairs'], ('pair total', next_id)
                        assert actual['right_kernel_dimension_histogram'] == wanted['right_kernel_dimension_histogram'], ('kernel histogram', next_id)
                        assert actual['quadratic_nonzero_cosets'] + 1 == wanted['quadratic_polar_cosets'], ('nonzero coset total', next_id)
                    statuses.update(actual_statuses)
                    high_histogram[actual['high_rank']] += 1
                    K_histogram[Kdim] += 1
                    mark_histogram[nmarks] += 1
                    complete_states += actual['complete']
                    producer_complete_states += wanted['complete']
                    producer_lefts += wanted['left_forms']
                    producer_pairs += wanted['eligible_unordered_pairs']
                    producer_cosets += wanted['quadratic_polar_cosets']
                    for i, value in enumerate(actual['right_kernel_dimension_histogram']):
                        kernel_histogram[i] += value
                    lefts += actual['left_forms']
                    pairs += actual['eligible_unordered_pairs']
                    nonzero_cosets += actual['quadratic_nonzero_cosets']
                    local_lefts += actual['left_forms']
                    local_pairs += actual['eligible_unordered_pairs']
                    local_nonzero += actual['quadratic_nonzero_cosets']
                    total_marks += nmarks
                    local_marks += nmarks
                    next_id += 1
                    local_states += 1
                assert not producer_handle.readline(), ('extra producer record', shard)
            assert local_states == launch['expected_states'] and next_id == launch['end_exclusive']
            assert independent_hash.hexdigest() == evidence.pinned(independent_path)
            assert producer_hash.hexdigest() == evidence.pinned(producer_path)
            audited = coverage['shards'][shard]
            assert (local_states, local_marks, producer_lefts, producer_pairs, producer_cosets) == (
                audited['states'], audited['Q_marks'], audited['left_forms'],
                audited['eligible_unordered_pairs'], audited['quadratic_polar_cosets'])
            shards.append({'shard': shard, 'state_interval': [launch['begin'], next_id],
                'states': local_states, 'marked_Q_choices': local_marks, 'left_forms': local_lefts,
                'eligible_unordered_pairs': local_pairs, 'nonzero_cosets': local_nonzero,
                'independent_JSONL_sha256': independent_hash.hexdigest(),
                'producer_JSONL_sha256': producer_hash.hexdigest(),
                'independent_process_exit_code': terminal['exit_code'],
                'producer_process_exit_code': 0,
                'independent_observed_wall_seconds': terminal['wall_seconds']})
            print(json.dumps({'event': 'shard_comparison_pass', **shards[-1]}), flush=True)
        assert not input_handle.readline()
    assert next_id == expected['states'] and total_marks == expected['marked_Q_choices']
    assert sum(statuses.values()) == total_marks and sum(kernel_histogram) == lefts
    assert producer_complete_states == coverage['complete_states']
    assert dict(statuses) == coverage['Q_statuses']
    # Detect mutation after preflight as well as truncated streamed data.
    evidence.verify()
    return {'status': 'pass', 'verification_state': 'verified',
        'campaign_id': evidence.recipe['campaign_id'], 'states': next_id,
        'marked_Q_choices': total_marks, 'exact_state_interval': [0, next_id],
        'no_missing_or_duplicate_states': True, 'all_marked_scalar_choices_checked': True,
        'Q_statuses': dict(statuses), 'complete_states': complete_states,
        'early_positive_states': next_id - complete_states,
        'higher_degree_rank_histogram': dict(high_histogram), 'K_dimension_histogram': dict(K_histogram),
        'mark_multiplicity_histogram': dict(mark_histogram),
        'left_forms': lefts, 'eligible_unordered_pairs': pairs, 'nonzero_cosets': nonzero_cosets,
        'right_kernel_dimension_histogram': kernel_histogram,
        'producer_positive_witnesses_replayed': producer_replays,
        'independent_positive_witnesses_replayed': independent_replays,
        'full_positive_truth_rows_checked': 256 * (producer_replays + independent_replays),
        'scope': evidence.recipe['scope'], 'external_peer_review': False,
        'independent_algorithm': 'monomial-union products, 18-variable row equations, projected right kernels, all old quadratic offsets, low-pivot rank',
        'producer_algorithm': 'truth-table products, Mobius ANF, high-column quotient kernels',
        'shards': shards, 'legacy_producer_candidate_commit': producer_manifest['candidate_commit'],
        'legacy_independent_candidate_commit': manifest['candidate_commit'],
        'independent_frozen_source_sha256': manifest['source']['sha256'],
        'independent_frozen_binary_sha256': manifest['executable']['sha256'],
        'producer_source_sha256': producer_manifest['source_sha256'],
        'producer_binary_sha256': producer_manifest['binary_sha256'],
        'input_sha256': manifest['input']['sha256'],
        'comparison_helper_sha256': digest(Path(symbolic.__file__)),
        'comparison_source_sha256': digest(Path(__file__)),
        'producer_coverage_audit_sha256': evidence.pinned(producer / 'coverage-audit.json'),
        'verified_evidence_sha256': evidence.checked_hashes,
        'algorithm_seconds': time.monotonic() - start}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--campaign', required=True, type=Path)
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[3])
    parser.add_argument('--out', required=True, type=Path)
    args = parser.parse_args()
    if not __debug__:
        parser.error('Optimized Python disables mathematical assertions; rerun without -O.')
    if args.out.exists():
        parser.error('Output already exists; preserve it and choose a fresh --out.')
    recipe_hash = digest(args.campaign)
    result = compare(Evidence(args.root, load(args.campaign)))
    if digest(args.campaign) != recipe_hash:
        raise ValueError('Campaign recipe changed during finalization.')
    result['campaign_recipe_sha256'] = recipe_hash
    with args.out.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps({key: value for key, value in result.items()
                      if key not in ('shards', 'verified_evidence_sha256')}, indent=2), flush=True)


if __name__ == '__main__':
    main()
