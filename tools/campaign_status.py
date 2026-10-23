#!/usr/bin/env python3
"""Generate a compact experiment checkpoint only after revalidating a campaign."""
import argparse
import json
from pathlib import Path
import subprocess
import sys

from campaign import sha, timestamp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--recipe', type=Path, required=True)
    parser.add_argument('--record', type=Path, required=True)
    parser.add_argument('--run-dir', type=Path, required=True)
    parser.add_argument('--as-of', required=True)
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--run', action='store_true', help='Run/resume the campaign before regenerating status')
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    command = [sys.executable, str(root / 'tools/campaign.py'), 'run' if args.run else 'status', '--recipe', str(args.recipe),
               '--record', str(args.record), '--run-dir', str(args.run_dir), '--as-of', args.as_of]
    check = subprocess.run(command, capture_output=True, text=True)
    state_path = args.run_dir / 'state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {'status': 'not-started'}
    recipe = json.loads(args.recipe.read_text())
    verified = check.returncode == 0 and state['status'] == 'verified'
    lines = ['# GF(16) research — current evidence checkpoint', '', f'Generated: {timestamp()}',
             f'Workflow: **{"verified scoped audit" if verified else "pending / invalid"}**',
             'Experiment: in progress; global unrestricted complexity and novelty remain unresolved.',
             'AES baseline: complete separately. Publication of this checkpoint: not performed by this tool.', '']
    if verified:
        audit = recipe['stages'][-1]
        directory = args.run_dir / state['stages'][audit['id']]['directory']
        output = directory / audit['outputs'][0]['path']
        result = json.loads(output.read_text())
        lines += [f"- Final comparison: {result['states']:,} states / {result['marked_Q_choices']:,} scalar marks.",
                  f"- Mark verdicts: {json.dumps(result['Q_statuses'], sort_keys=True)}.",
                  f"- Exact coverage, per-case kernel/counter comparison, and preserved actual shard exits checked.",
                  f"- Eligible pairs: {result['eligible_unordered_pairs']:,}; nonzero cosets: {result['nonzero_cosets']:,}.",
                  f"- Audit SHA-256: `{sha(output)}`.",
                  '- Numerical scope: r4=8 proper-quartic fixed-coordinate frontier only; conditional branch exclusion uses the reviewed reductions in the linked proof.', '']
    else:
        lines += ['No verified scientific result is promoted by this checkpoint.', '',
                  f'Validation diagnostic: {check.stderr.strip() or state["status"]}', '']
    lines += ['Remaining: r4=6 with r3=4/5 and r4=7; full dependency-tree reconciliation, a complete solution, and novelty review.',
              'No improved complete AES circuit, global eight-AND exclusion, physical PPA, or external peer review is claimed.', '',
              '[Contract](experiment.json) · [Plan and open branches](PLAN.md) · [Prior-art comparison](RESEARCH.md) · '
              '[Reviewed proof](../aes-256-gcm/GF16_QUARTIC_PREFIX_FRONTIER.md)', '',
              f'Run: `{args.run_dir.as_posix()}`', f'State SHA-256: `{sha(state_path) if state_path.exists() else "unavailable"}`',
              f'Recipe SHA-256: `{sha(args.recipe)}`',
              'This is a generated checkpoint, not a live process monitor. Revalidate before reusing it.', '']
    args.out.write_text('\n'.join(lines))
    print(args.out)
    return 0 if verified else 1


if __name__ == '__main__':
    raise SystemExit(main())
