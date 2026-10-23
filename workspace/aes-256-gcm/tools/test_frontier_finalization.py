"""Preflight controls only; synthetic records are never mathematical results.

The preserved-campaign test also checks real terminal evidence and all pinned
bytes when that ignored local archive is available. No test changes it.
"""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import finalize_frontier_campaign as finalizer


ROOT = Path(__file__).resolve().parents[3]
CAMPAIGN = ROOT / 'experiments/gf16-multiplicative-complexity/campaigns/frontier-pairs.json'


class PreflightFixture:
    """Small internally consistent capture metadata, not scan correctness data."""

    def __init__(self, root):
        self.root = root
        self.legacy = '/preserved-fixture'
        self.recipe = {
            'schema_version': 1, 'kind': 'legacy-frontier-pair-finalization',
            'legacy_root': self.legacy, 'producer_dir': 'producer',
            'independent_dir': 'independent', 'fixed_coordinate_source': 'groups.json',
            'symbolic_helper': 'helper.py', 'pinned_files': {},
            'expected': {'states': 1, 'marked_Q_choices': 1, 'shards': 1,
                         'states_per_shard': 1}}
        self.write('groups.json', {'groups': [{
            'first_source': {'code': 0, 'polar_coset': 0},
            'nonlinear_rref_hex': ['0x1', '0x2', '0x4', '0x8', '0x10'],
            'marked_Q_polars': [1]}]})
        for directory in ('producer', 'independent'):
            self.write(directory + '/source.cpp', '// synthetic capture only\n')
            self.write(directory + '/binary', 'not executable; never run\n')
            self.write(directory + '/input.tsv', '0 0 0 1 0x1 0x2 0x4 0x8 0x10 1\n')
            self.write(directory + '/shard-0.jsonl', '{"synthetic":true}\n')
            for suffix in ('stdout.log', 'stderr.log'):
                self.write(directory + '/shard-0.' + suffix, '')
        self.write('producer/shard-0.jsonl.summary.json', {'synthetic': True})
        shutil.copyfile(finalizer.symbolic.__file__, root / 'helper.py')
        self.pin('helper.py')

        item = {'shard': 0, 'begin': 0, 'count': 1, 'end_exclusive': 1,
                'output': self.old('producer/shard-0.jsonl')}
        command = {**item, 'exit_code': 0, 'argv': [self.old('producer/binary'),
            self.old('producer/input.tsv'), item['output'], '--begin', '0', '--count', '1']}
        producer = {'assertions_enabled': True, 'automatic_restarts': False,
                    'compile_record': {'exit_code': 0, 'argv': ['c++']},
                    'expected_states': 1, 'expected_Q_marks': 1, 'shards': [item]}
        terminal = {'status': 'pass', 'commands': [command]}
        for field, name in (('source', 'source.cpp'), ('binary', 'binary'), ('input', 'input.tsv')):
            relative = 'producer/' + name
            producer[field + '_path'] = self.old(relative)
            producer[field + '_sha256'] = self.recipe['pinned_files'][relative]
            terminal[field + '_sha256_after'] = producer[field + '_sha256']
        self.write('producer/launch-manifest.json', producer)
        self.write('producer/terminal-status.json', terminal)
        self.write('producer/shard-0.command.json', command)
        coverage = {'status': 'pass', 'states': 1, 'Q_marks': 1, 'shards': [{}]}
        for suffix, field in (('jsonl', 'output'), ('jsonl.summary.json', 'summary'),
                              ('stdout.log', 'stdout'), ('stderr.log', 'stderr')):
            coverage['shards'][0][field + '_sha256'] = self.recipe['pinned_files']['producer/shard-0.' + suffix]
        self.write('producer/coverage-audit.json', coverage)

        manifest = {'states': 1, 'marked_scalar_choices': 1, 'shards': 1,
                    'states_per_shard': 1, 'assertions_enabled': True,
                    'every_TSV_row_matched_to_fixed_coordinate_source': True,
                    'compile_record': {'exit_code': 0, 'argv': ['c++']},
                    'fixed_coordinate_source_sha256': self.recipe['pinned_files']['groups.json']}
        for field, name in (('source', 'source.cpp'), ('executable', 'binary'), ('input', 'input.tsv')):
            relative = 'independent/' + name
            manifest[field] = {'frozen_path': self.old(relative),
                               'sha256': self.recipe['pinned_files'][relative],
                               'bytes': (root / relative).stat().st_size}
        launch = {'PID': 42, 'shard': 0, 'begin': 0, 'end_exclusive': 1,
                  'expected_states': 1, 'argv': [self.old('independent/binary'),
            self.old('independent/input.tsv'), self.old('independent/shard-0.jsonl'),
            '--begin', '0', '--count', '1']}
        self.write('independent/manifest.json', manifest)
        self.write('independent/execution-complete.json', {'status': 'pass', 'shard_exit_codes': [0]})
        self.write('independent/shard-0.launch.json', launch)
        self.write('independent/shard-0.complete.json', {**launch, 'exit_code': 0,
            'output_bytes': (root / 'independent/shard-0.jsonl').stat().st_size})

    def old(self, relative):
        return self.legacy + '/' + relative

    def pin(self, relative):
        self.recipe['pinned_files'][relative] = finalizer.digest(self.root / relative)

    def write(self, relative, value):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(value if isinstance(value, str) else json.dumps(value))
        self.pin(relative)

    def evidence(self):
        return finalizer.Evidence(self.root, copy.deepcopy(self.recipe))


class FrontierFinalizationTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory(prefix='frontier-preflight-')
        self.addCleanup(self.temporary.cleanup)
        self.fixture = PreflightFixture(Path(self.temporary.name))

    def test_synthetic_capture_preflight(self):
        finalizer.preflight(self.fixture.evidence())

    def test_imported_helper_must_match_pinned_copy(self):
        # The restored tree is internally pinned, but does not match the helper
        # actually imported beside the finalizer. Hashing only the tree misses it.
        self.fixture.write('helper.py', '# different implementation\n')
        with self.assertRaisesRegex(ValueError, 'Imported symbolic helper'):
            finalizer.preflight(self.fixture.evidence())

    def test_corrupted_pinned_output_is_refused(self):
        path = self.fixture.root / 'independent/shard-0.jsonl'
        path.write_text('truncated')  # Intentionally do not update its pin.
        with self.assertRaisesRegex(ValueError, 'Pinned evidence hash mismatch'):
            finalizer.preflight(self.fixture.evidence())

    def test_nonzero_individual_exit_is_refused(self):
        relative = 'independent/shard-0.complete.json'
        record = finalizer.load(self.fixture.root / relative)
        record['exit_code'] = 7
        self.fixture.write(relative, record)  # Fresh pin isolates the exit check.
        with self.assertRaises(AssertionError):
            finalizer.preflight(self.fixture.evidence())

    def test_nonzero_supervisor_exit_is_refused(self):
        self.fixture.write('independent/execution-complete.json',
                           {'status': 'pass', 'shard_exit_codes': [7]})
        with self.assertRaises(AssertionError):
            finalizer.preflight(self.fixture.evidence())

    def test_preserved_real_campaign_preflight_when_available(self):
        recipe = finalizer.load(CAMPAIGN)
        if not all((ROOT / path).is_file() for path in recipe['pinned_files']):
            self.skipTest('Ignored preserved campaign evidence is unavailable; synthetic controls still run.')
        evidence = finalizer.Evidence(ROOT, recipe)
        finalizer.preflight(evidence)
        self.assertEqual(len(evidence.checked_hashes), len(recipe['pinned_files']))


if __name__ == '__main__':
    unittest.main()
