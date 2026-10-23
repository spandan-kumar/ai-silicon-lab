"""Real subprocess tests of campaign failure, interruption, resume and tampering."""
import hashlib
import json
import os
from pathlib import Path
import signal
import subprocess
import sys
import tempfile
import time
import unittest

TOOL = Path(__file__).with_name('campaign.py')


class CampaignTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.run = self.root / 'runs' / 'test'
        self.script = self.root / 'worker.py'
        self.script.write_text('''import json, pathlib, sys, time
role, mode, directory, root = sys.argv[1:]
p = pathlib.Path(directory)
with (pathlib.Path(root) / 'calls').open('a') as f: f.write(role + ':' + p.name + '\\n')
if role == 'audit' and mode == 'fail' and p.name == '0001': sys.exit(7)
if role == 'scan' and mode == 'wait' and p.name == '0001': time.sleep(30)
(p / 'result.json').write_text(json.dumps({'status': 'pass', 'count': 3}))
''')
        self.ledger = {'schema_version': 1, 'claim': 'fixture audit only', 'novelty_status': 'reproduction',
                       'reviewed_on': '2026-10-23', 'searches': [{'query': 'fixture', 'date': '2026-10-23'}],
                       'sources': [{'url': 'https://example.org', 'title': 'fixture', 'verified_fact': 'fixture only', 'limitation': 'not research'}],
                       'decision': {'action': 'continue', 'rationale': 'Test execution plumbing, not novelty.'}}
        self.write('prior.json', self.ledger)
        self.record = {'schema_version': 1, 'record_type': 'experiment-run', 'run_id': 'fixture',
                       'experiment_id': 'fixture', 'experiment_revision': 1, 'status': 'draft',
                       'measurement_status': 'unavailable', 'agent': {'model': {}, 'harness': {}, 'reasoning': {}},
                       'usage': {'source': 'unavailable'}, 'time': {'source': 'unavailable'},
                       'cost': {'source': 'unavailable'}, 'execution': {}, 'result': {}, 'evidence': []}
        self.write('record.json', self.record)
        self.recipe = {'schema_version': 1, 'campaign_id': 'fixture', 'experiment_id': 'fixture', 'experiment_revision': 1,
                       'claim': 'fixture audit only', 'prior_art': 'prior.json', 'prior_art_max_age_days': 14,
                       'inputs': [{'path': 'worker.py', 'sha256': hashlib.sha256(self.script.read_bytes()).hexdigest()}],
                       'stages': []}
        self.configure('normal')

    def write(self, name, obj):
        (self.root / name).write_text(json.dumps(obj))

    def configure(self, mode):
        self.recipe['stages'] = [{'id': role, 'role': role, 'time_kind': 'software',
                                 'argv': [sys.executable, '{root}/worker.py', role, mode, '{stage}', '{root}'],
                                 'outputs': [{'path': 'result.json', 'equals': {'status': 'pass', 'count': 3}}]}
                                for role in ('scan', 'replay', 'audit')]
        self.write('recipe.json', self.recipe)

    def argv(self, command='run'):
        return [sys.executable, str(TOOL), command, '--root', str(self.root), '--recipe', str(self.root / 'recipe.json'),
                '--record', str(self.root / 'record.json'), '--run-dir', str(self.run), '--as-of', '2026-10-23']

    def invoke(self, command='run', good=True):
        p = subprocess.run(self.argv(command), capture_output=True, text=True)
        self.assertEqual(p.returncode, 0 if good else 1, p.stdout + p.stderr)
        return p

    def state(self):
        return json.loads((self.run / 'state.json').read_text())

    def test_automatic_audit_and_idempotent_resume(self):
        self.invoke()
        self.assertEqual(self.state()['status'], 'verified')
        calls = (self.root / 'calls').read_text()
        self.assertEqual(calls, 'scan:0001\nreplay:0001\naudit:0001\n')
        self.invoke()
        self.invoke('status')
        self.assertEqual((self.root / 'calls').read_text(), calls)

    def test_failed_audit_retained_and_only_failed_stage_retried(self):
        self.configure('fail')
        self.invoke(good=False)
        self.assertEqual(self.state()['status'], 'failed')
        self.assertFalse((self.run / 'verified.json').exists())
        receipt = self.run / 'attempts/audit/0001/receipt.json'
        before = receipt.read_bytes()
        self.assertEqual(json.loads(before)['exit_code'], 7)
        self.invoke()
        self.assertEqual(receipt.read_bytes(), before)
        self.assertEqual((self.root / 'calls').read_text(), 'scan:0001\nreplay:0001\naudit:0001\naudit:0002\n')

    def test_completed_output_corruption_is_not_reused(self):
        self.invoke()
        original_seal = (self.run / 'verified.json').read_bytes()
        (self.run / 'attempts/scan/0001/result.json').write_text('{"status":"pass","count":4}')
        self.invoke('status', good=False)
        self.assertEqual(self.state()['status'], 'invalid')
        self.assertEqual(json.loads((self.run / 'verified.json').read_text())['status'], 'invalid')
        history = list((self.run / 'verification-history').iterdir())
        self.assertEqual(len(history), 1)
        self.assertEqual(history[0].read_bytes(), original_seal)
        self.invoke(good=False)
        self.assertIn('stale/invalid', (self.run / 'STATUS.md').read_text())

    def test_later_stage_mutation_cannot_acquire_verified_status(self):
        self.script.write_text(self.script.read_text() + '''
if role == 'audit':
    (pathlib.Path(root) / 'runs/test/attempts/scan/0001/result.json').write_text(json.dumps({'status':'pass','count':999}))
''')
        self.recipe['inputs'][0]['sha256'] = hashlib.sha256(self.script.read_bytes()).hexdigest()
        self.write('recipe.json', self.recipe)
        self.invoke(good=False)
        self.assertEqual(self.state()['status'], 'invalid')
        self.assertFalse((self.run / 'verified.json').exists())
        self.assertEqual(json.loads((self.run / 'attempts/scan/0001/result.json').read_text())['count'], 999)
        self.assertEqual(json.loads((self.run / 'attempts/audit/0001/receipt.json').read_text())['exit_code'], 0)

    def test_receipt_launch_and_seal_tampering_are_invalid(self):
        self.invoke()
        paths = ('attempts/audit/0001/receipt.json', 'attempts/replay/0001/launch.json', 'verified.json')
        for relative in paths:
            with self.subTest(relative=relative):
                path = self.run / relative
                original = path.read_bytes()
                value = json.loads(original)
                value['tampered'] = True
                path.write_text(json.dumps(value))
                if relative == 'verified.json':
                    value['state_sha256'] = '0' * 64
                    path.write_text(json.dumps(value))
                self.invoke('status', good=False)
                self.assertEqual(self.state()['status'], 'invalid')
                self.assertEqual(json.loads((self.run / 'verified.json').read_text())['status'], 'invalid')
                path.write_bytes(original)
                self.invoke()  # Explicit revalidation, not automatic adoption by status.

    def test_changed_input_or_recipe_refuses_resume(self):
        self.invoke()
        self.script.write_text(self.script.read_text() + '\n# changed\n')
        self.invoke(good=False)
        self.recipe['inputs'][0]['sha256'] = hashlib.sha256(self.script.read_bytes()).hexdigest()
        self.write('recipe.json', self.recipe)
        self.invoke(good=False)

    def test_stale_or_mismatched_research_gate(self):
        for field, value in (('reviewed_on', '2026-01-01'), ('claim', 'different claim')):
            with self.subTest(field=field):
                old = self.ledger[field]
                self.ledger[field] = value
                self.write('prior.json', self.ledger)
                self.invoke(good=False)
                self.assertFalse((self.run / 'verified.json').exists())
                self.ledger[field] = old

    def test_wrong_audit_verdict_is_failure_even_with_zero_exit(self):
        self.recipe['stages'][-1]['outputs'][0]['equals']['count'] = 4
        self.write('recipe.json', self.recipe)
        self.invoke(good=False)
        receipt = json.loads((self.run / 'attempts/audit/0001/receipt.json').read_text())
        self.assertEqual(receipt['exit_code'], 0)
        self.assertEqual(receipt['status'], 'fail')
        self.assertFalse((self.run / 'verified.json').exists())

    def test_interruption_and_exclusive_runner_lock(self):
        self.configure('wait')
        process = subprocess.Popen(self.argv(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if (self.run / 'state.json').exists() and self.state()['status'] == 'running':
                    break
                time.sleep(0.02)
            else:
                self.fail('runner failed to launch')
            status_before = (self.run / 'STATUS.md').read_bytes()
            state_before = (self.run / 'state.json').read_bytes()
            self.invoke(good=False)  # no duplicate scan while first runner holds flock
            self.assertEqual((self.run / 'STATUS.md').read_bytes(), status_before)
            self.assertEqual((self.run / 'state.json').read_bytes(), state_before)
            process.send_signal(signal.SIGTERM)
            stdout, stderr = process.communicate(timeout=10)
            self.assertEqual(process.returncode, 1, stdout + stderr)
            first = json.loads((self.run / 'attempts/scan/0001/receipt.json').read_text())
            self.assertEqual(first['exit_code'], -signal.SIGTERM)
            self.invoke()
            self.assertEqual(self.state()['status'], 'verified')
            self.assertEqual((self.root / 'calls').read_text(), 'scan:0001\nscan:0002\nreplay:0001\naudit:0001\n')
        finally:
            if process.poll() is None:
                process.terminate()
                process.communicate(timeout=10)

    def test_killed_supervisor_never_adopts_unobserved_child_exit(self):
        self.configure('wait')
        process = subprocess.Popen(self.argv(), stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        child_pid = None
        try:
            deadline = time.monotonic() + 10
            while time.monotonic() < deadline:
                if (self.run / 'state.json').exists() and self.state()['status'] == 'running':
                    launch = json.loads((self.run / 'attempts/scan/0001/launch.json').read_text())
                    child_pid = launch['pid']
                    break
                time.sleep(0.02)
            else:
                self.fail('runner failed to launch')
            process.kill()  # Real SIGKILL: the supervisor cannot record an exit.
            process.communicate(timeout=10)
            self.assertEqual(process.returncode, -signal.SIGKILL)
            self.invoke(good=False)  # Existing live child must not be duplicated.
            self.assertEqual((self.root / 'calls').read_text(), 'scan:0001\n')
            os.kill(child_pid, signal.SIGTERM)
            deadline = time.monotonic() + 5
            while time.monotonic() < deadline:
                try:
                    os.kill(child_pid, 0)
                except ProcessLookupError:
                    break
                time.sleep(0.02)
            self.invoke()
            lost = json.loads((self.run / 'attempts/scan/0001/interrupted.json').read_text())
            self.assertEqual(lost['status'], 'interrupted')
            self.assertIsNone(lost['exit_code'])
            self.assertEqual(self.state()['status'], 'verified')
            self.assertEqual((self.root / 'calls').read_text(), 'scan:0001\nscan:0002\nreplay:0001\naudit:0001\n')
        finally:
            if process.poll() is None:
                process.kill()
                process.communicate(timeout=10)
            if child_pid is not None:
                try:
                    os.kill(child_pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass


if __name__ == '__main__':
    unittest.main()
