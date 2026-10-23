#!/usr/bin/env python3
"""Sequential research campaigns with retained attempts and fail-closed resume.

This is execution plumbing, not an oracle. Only the supplied independent audit
defines the scientific scope of a verified result. Recipes are trusted code.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import fcntl
import hashlib
import json
import os
from pathlib import Path
import re
import signal
import subprocess
import sys
import time

from experiment_registry import validate_run_record

ROOT = Path(__file__).resolve().parents[1]
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def sha(path):
    h = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def read(path):
    return json.loads(path.read_text(), parse_constant=lambda x: (_ for _ in ()).throw(ValueError(x)))


def save(path, value):
    temporary = path.with_name(path.name + '.tmp')
    with temporary.open('w') as handle:
        json.dump(value, handle, indent=2, allow_nan=False)
        handle.write('\n')
        handle.flush()
        os.fsync(handle.fileno())
    temporary.replace(path)


def timestamp():
    return datetime.now(timezone.utc).isoformat()


def inside(root, value):
    path = root / value
    if path.is_symlink() or not path.resolve().is_relative_to(root.resolve()):
        raise ValueError(f'unsafe path: {value}')
    return path


def require(condition, message):
    if not condition:
        raise ValueError(message)


def prior_art(root, recipe, as_of):
    ledger_path = inside(root, recipe['prior_art'])
    ledger = read(ledger_path)
    require(ledger['schema_version'] == 1, 'unsupported prior-art ledger')
    require(ledger['claim'] == recipe['claim'], 'prior-art claim mismatch')
    age = (date.fromisoformat(as_of) - date.fromisoformat(ledger['reviewed_on'])).days
    require(0 <= age <= recipe['prior_art_max_age_days'], 'prior-art review stale or future-dated; refresh it')
    require(ledger['novelty_status'] in ('known', 'reproduction', 'possibly-new', 'unverified'), 'invalid novelty state')
    require(bool(ledger['searches']) and bool(ledger['sources']), 'missing recorded searches/sources')
    for search in ledger['searches']:
        require(bool(search['query']) and date.fromisoformat(search['date']) <= date.fromisoformat(as_of), 'invalid search')
    for source in ledger['sources']:
        require(source['url'].startswith('https://') and all(source.get(k) for k in ('title', 'verified_fact', 'limitation')), 'incomplete source record')
    require(ledger['decision']['action'] == 'continue' and bool(ledger['decision']['rationale']), 'campaign needs an explicit continue decision')
    return ledger_path


def prepare(root, recipe_path, record_path, as_of):
    recipe = read(recipe_path)
    require(recipe['schema_version'] == 1, 'unsupported campaign recipe')
    require(SLUG.fullmatch(recipe['campaign_id']) is not None, 'invalid campaign id')
    require(recipe['stages'] and recipe['stages'][-1]['role'] == 'audit', 'last stage must be an independent audit')
    ids = [s['id'] for s in recipe['stages']]
    require(len(set(ids)) == len(ids) and all(SLUG.fullmatch(s) for s in ids), 'invalid/duplicate stage ids')
    for stage in recipe['stages']:
        require(stage['role'] in ('build', 'scan', 'replay', 'audit'), 'invalid stage role')
        require(stage['time_kind'] in ('build', 'software', 'simulation', 'physical'), 'invalid time kind')
        require(stage['argv'] and all(isinstance(a, str) and a for a in stage['argv']), 'argv must be nonempty strings')
        require(stage['outputs'], 'stage must declare outputs')
        for output in stage['outputs']:
            p = Path(output['path'])
            require(not p.is_absolute() and '..' not in p.parts and str(p) not in ('.', ''), 'unsafe output path')
        if stage['role'] == 'audit':
            require(any(o.get('equals', {}).get('status') == 'pass' for o in stage['outputs']), 'audit needs an explicit JSON status=pass check')
    record = read(record_path)
    issues = validate_run_record(record, record_path)
    require(not issues, f'invalid provenance: {issues}')
    require(record['experiment_id'] == recipe['experiment_id'] and record['experiment_revision'] == recipe['experiment_revision'], 'provenance experiment mismatch')
    ledger_path = prior_art(root, recipe, as_of)
    inputs = {}
    for entry in recipe['inputs']:
        path = inside(root, entry['path'])
        require(path.is_file() and sha(path) == entry['sha256'], f"missing or changed pinned input: {entry['path']}")
        inputs[entry['path']] = entry['sha256']
    # The recipe pins executable sources/dependencies explicitly, not just argv.
    require(bool(inputs), 'recipe must pin its code and input files')
    identity = {'recipe_sha256': sha(recipe_path), 'runner_sha256': sha(Path(__file__)),
                'record_sha256': sha(record_path), 'prior_art_sha256': sha(ledger_path), 'inputs': inputs}
    return recipe, identity


def output_hashes(stage, directory):
    hashes = {}
    for output in stage['outputs']:
        path = inside(directory, output['path'])
        require(path.is_file(), f'missing output: {path}')
        if 'equals' in output:
            value = read(path)
            for key, expected in output['equals'].items():
                actual = value
                for part in key.split('.'):
                    actual = actual[part]
                require(type(actual) is type(expected) and actual == expected, f'{path}: {key} check failed')
        hashes[output['path']] = sha(path)
    for name in ('stdout.log', 'stderr.log', 'launch.json'):
        hashes[name] = sha(directory / name)
    return hashes


def completed(stage, directory, receipt_sha256):
    require(sha(directory / 'receipt.json') == receipt_sha256, 'completed stage receipt changed')
    receipt = read(directory / 'receipt.json')
    require(receipt['status'] == 'pass' and type(receipt['exit_code']) is int and receipt['exit_code'] == 0, 'stage not successfully observed')
    require(output_hashes(stage, directory) == receipt['sha256'], 'completed stage output/log hash changed')
    return receipt


def check_stages(run, recipe, state):
    for stage in recipe['stages']:
        item = state['stages'].get(stage['id'])
        if item and item['status'] == 'pass':
            completed(stage, run / item['directory'], item['receipt_sha256'])


def check_seal(run, recipe, state):
    if state['status'] == 'verified':
        seal = read(run / 'verified.json')
        require(seal['status'] == 'pass' and seal['identity'] == state['identity']
                and seal['scope'] == recipe['claim']
                and seal['state_sha256'] == sha(run / 'state.json'), 'verification seal changed or stale')


def retain_seal(run):
    seal = run / 'verified.json'
    if seal.exists():
        history = run / 'verification-history'
        history.mkdir(exist_ok=True)
        # Preserve the exact old bytes, including malformed seals, before replacement.
        with (history / f'{time.time_ns()}.json').open('xb') as handle:
            handle.write(seal.read_bytes())


def invalidate(run, reason):
    state_path = run / 'state.json'
    if not state_path.exists():
        return
    state = read(state_path)
    if state['status'] != 'failed' or (run / 'verified.json').exists():
        state['status'] = 'invalid'
    state['validation_error'] = reason
    state['updated'] = timestamp()
    save(state_path, state)
    if (run / 'verified.json').exists():
        retain_seal(run)
        save(run / 'verified.json', {'status': 'invalid', 'reason': reason,
                                    'invalidated_at': timestamp(), 'state_sha256': sha(state_path)})
    if (run / 'recipe.json').exists():
        render(run, read(run / 'recipe.json'), state, reason)


def alive(pid):
    try:
        os.kill(pid, 0)
        return True
    except ProcessLookupError:
        return False


def render(run, recipe, state, validation_error=None):
    lines = [f"# {recipe['campaign_id']} — current state", '',
             f"Generated: {timestamp()}", f"Experiment: {recipe['experiment_id']} revision {recipe['experiment_revision']}",
             f"Workflow: **{'stale/invalid' if validation_error else state['status']}**", '',
             'Verified means the declared audit passed, not a global theorem, novelty claim, or physical improvement.',
             'Publication: not performed by this runner.', '', f"Claim: {recipe['claim']}", '']
    if validation_error:
        lines += [f'Validation error: {validation_error}', '']
    for stage in recipe['stages']:
        item = state['stages'].get(stage['id'], {})
        lines.append(f"- {stage['id']} ({stage['role']}): {item.get('status', 'pending')}; attempt {item.get('attempt', 'none')}")
    lines += ['', f"Run state: `{run / 'state.json'}`", f"Prior art: `{recipe['prior_art']}`", '',
              'Old failed/interrupted attempts are retained. Unknown agent/token/cost telemetry remains null in the attached run record.', '']
    (run / 'STATUS.md').write_text('\n'.join(lines))


def execute(root, recipe, identity, run, record_path):
    state_path = run / 'state.json'
    if state_path.exists():
        state = read(state_path)
        require(state['identity'] == identity, 'campaign identity changed; use a fresh run directory')
        check_seal(run, recipe, state)
    else:
        state = {'schema_version': 1, 'identity': identity, 'status': 'pending', 'stages': {}, 'created': timestamp()}
        save(run / 'provenance.json', read(record_path))
        save(run / 'recipe.json', recipe)
        save(state_path, state)

    def checkpoint():
        state['updated'] = timestamp()
        save(state_path, state)
        render(run, recipe, state)

    for stage in recipe['stages']:
        previous = state['stages'].get(stage['id'])
        if previous and previous['status'] == 'pass':
            completed(stage, run / previous['directory'], previous['receipt_sha256'])
            continue
        if previous and previous['status'] == 'running':
            launch = read(run / previous['directory'] / 'launch.json')
            require(not alive(launch['pid']), f"stage {stage['id']} may still be running (PID {launch['pid']}); inspect it before resuming")
            # Exit was never observed. Do not adopt a possibly complete output.
            previous['status'] = 'interrupted'
            save(run / previous['directory'] / 'interrupted.json', {'status': 'interrupted', 'exit_code': None, 'observed': timestamp()})
        number = previous['attempt'] + 1 if previous else 1
        relative = f"attempts/{stage['id']}/{number:04d}"
        directory = run / relative
        directory.mkdir(parents=True, exist_ok=False)
        argv = [a.replace('{root}', str(root)).replace('{run}', str(run)).replace('{stage}', str(directory)) for a in stage['argv']]
        item = {'status': 'running', 'attempt': number, 'directory': relative}
        state['stages'][stage['id']] = item
        state['status'] = 'running'
        start = time.monotonic()
        process = None
        interrupted = []

        def stop(signum, _frame):
            interrupted.append(signum)
            if process is not None and process.poll() is None:
                os.killpg(process.pid, signal.SIGTERM)

        old_handlers = {s: signal.signal(s, stop) for s in (signal.SIGINT, signal.SIGTERM)}
        try:
            with (directory / 'stdout.log').open('xb') as stdout, (directory / 'stderr.log').open('xb') as stderr:
                process = subprocess.Popen(argv, cwd=root, stdout=stdout, stderr=stderr, start_new_session=True)
                save(directory / 'launch.json', {'argv': argv, 'pid': process.pid, 'started': timestamp(), 'time_kind': stage['time_kind']})
                checkpoint()
                code = process.wait()
            receipt = {'status': 'fail', 'exit_code': code, 'wall_seconds': time.monotonic() - start,
                       'time_kind': stage['time_kind'], 'signals': interrupted, 'finished': timestamp()}
            if code == 0 and not interrupted:
                # Reject mutation of pinned inputs during execution as well.
                for path, digest in identity['inputs'].items():
                    require(sha(inside(root, path)) == digest, f'input changed during stage: {path}')
                receipt['sha256'] = output_hashes(stage, directory)
                receipt['status'] = 'pass'
        except Exception as error:
            receipt = {'status': 'fail', 'exit_code': process.returncode if process else None,
                       'wall_seconds': time.monotonic() - start, 'time_kind': stage['time_kind'], 'error': str(error)}
        finally:
            for signum, handler in old_handlers.items():
                signal.signal(signum, handler)
        save(directory / 'receipt.json', receipt)
        item['status'] = receipt['status']
        item['receipt_sha256'] = sha(directory / 'receipt.json')
        if item['status'] != 'pass':
            state['status'] = 'failed'
            checkpoint()
            raise ValueError(f"stage {stage['id']} failed; see {directory}")
        checkpoint()
    # Later stages must not silently alter a previously accepted stage's evidence.
    check_stages(run, recipe, state)
    state.pop('validation_error', None)
    state['status'] = 'verified'
    checkpoint()
    retain_seal(run)
    save(run / 'verified.json', {'status': 'pass', 'scope': recipe['claim'], 'identity': identity,
                                'state_sha256': sha(state_path), 'verified_at': timestamp(),
                                'warning': 'Declared audit scope only; not external peer review or novelty certification.'})


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('command', choices=('run', 'status'))
    parser.add_argument('--root', type=Path, default=ROOT)
    parser.add_argument('--recipe', type=Path, required=True)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--as-of', required=True, help='Review date YYYY-MM-DD, explicitly supplied by operator')
    args = parser.parse_args(argv)
    root = args.root.resolve()
    run = args.run_dir.absolute()
    try:
        require(run.resolve().is_relative_to(root / 'runs') and run.resolve() != root / 'runs', 'run directory must be a child of root/runs')
        require(not run.is_symlink(), 'run directory may not be a symlink')
        run.mkdir(parents=True, exist_ok=True)
        with (run / '.lock').open('a') as lock:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
            try:
                recipe, identity = prepare(root, args.recipe, args.record, args.as_of)
                if args.command == 'run':
                    execute(root, recipe, identity, run, args.record)
                else:
                    state = read(run / 'state.json')
                    require(state['identity'] == identity, 'campaign identity changed')
                    check_stages(run, recipe, state)
                    check_seal(run, recipe, state)
                    render(run, recipe, state)
                    print((run / 'STATUS.md').read_text(), end='')
            except (OSError, ValueError, KeyError, TypeError) as error:
                # Invalidate machine-readable state too, only while holding the lock.
                invalidate(run, str(error))
                raise
        return 0
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f'campaign: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    raise SystemExit(main())
