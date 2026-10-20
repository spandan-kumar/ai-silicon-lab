"""Run every nonquadratic fifth-plane class once with exact terminal captures."""
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path
import subprocess
import time

HERE = Path(__file__).resolve().parent
classes = json.loads((HERE / 'report.json').read_text())
control = json.loads((HERE / 'canonical-control.json').read_text())
assert control['complete'] and not control['bent_pair_escape']
assert (control['eligible_unordered_pairs'], control['quadratic_polar_cosets']) == (53776, 10036)
selected = [row for row in classes['orbits'] if row['seed_degree'] > 2]
assert len(selected) == 192
case_dir = HERE / 'cases'
case_dir.mkdir(exist_ok=False)


def run(row):
    index = row['index']
    output = case_dir / (str(index) + '.json')
    command = [str(HERE / 'scan'), *map(str, row['factor_masks']), str(output)]
    start = time.monotonic()
    process = subprocess.run(command, text=True, capture_output=True)
    elapsed = time.monotonic() - start
    for suffix, value in (('stdout.log', process.stdout), ('stderr.log', process.stderr)):
        with (case_dir / (str(index) + '.' + suffix)).open('x') as handle:
            handle.write(value)
    with (case_dir / (str(index) + '.command.json')).open('x') as handle:
        json.dump({'argv': command, 'exit_code': process.returncode, 'wall_seconds': elapsed}, handle, indent=2)
    assert process.returncode == 0, (index, process.stderr)
    result = json.loads(output.read_text())
    result.update(plane_orbit_index=index, plane_orbit_size=row['orbit_size'], seed_degree=row['seed_degree'])
    assert result['factor_masks'] == row['factor_masks']
    assert result['complete'] != result['bent_pair_escape']
    print(json.dumps({'class': index, 'complete': result['complete'],
                      'bent_pair_escape': result['bent_pair_escape']}), flush=True)
    return result


start = time.monotonic()
with ThreadPoolExecutor(max_workers=4) as pool:
    results = list(pool.map(run, selected))
escapes = [r for r in results if r['bent_pair_escape']]
summary = {'status': 'all192-seed-class-scans-terminal-independent-replay-pending',
    'classes_scanned': len(results), 'fully_obstructed_classes': len(results) - len(escapes),
    'classes_with_bent_pair_escape': len(escapes),
    'nonquadratic_operand_planes_represented': sum(r['plane_orbit_size'] for r in results),
    'all_class_command_exits_zero': True, 'cases': results,
    'independently_replayed_full_campaign': False,
    'Q_by_four_branch_excluded': False, 'unrestricted_eight_AND_excluded': False,
    'world_first_established': False, 'algorithm_seconds': time.monotonic() - start,
    'scope': 'Complete first-useful rank8-pair obstruction by specified prefix-space symmetry; '
        'any escaping class remains open, not a field or AES construction. '
        'External scalar-optimal normal form and quadratic-gate flattening require separate review.'}
with (HERE / 'campaign.json').open('x') as handle:
    json.dump(summary, handle, indent=2)
print(json.dumps({key: summary[key] for key in ('status', 'classes_scanned', 'fully_obstructed_classes',
    'classes_with_bent_pair_escape', 'nonquadratic_operand_planes_represented', 'algorithm_seconds')}), flush=True)
