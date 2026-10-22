"""Serialize the verified fixed-coordinate frontier, preserving every Q mark.

EXPERIMENTAL CHECKPOINT (2026-10-22): serialization has run, but the downstream
pair-frontier campaign and independent inventory comparison have not run.
Generated files are exclusive outputs. This is serialization, not a new
equivalence reduction or a field-continuation claim.
"""
import argparse
import hashlib
import json
from pathlib import Path


def save(path, data):
    with path.open('x') as handle:
        json.dump(data, handle, indent=2)
        handle.write('\n')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--input', required=True)
    parser.add_argument('--out', required=True)
    args = parser.parse_args()
    folder = Path(args.out)
    folder.mkdir(exist_ok=False, parents=True)
    raw = Path(args.input).read_bytes()
    source = json.loads(raw)
    assert source['summary']['status'] == 'pass'
    groups = source['groups']
    assert len(groups) == source['summary']['distinct_fixed_coordinate_W5_spaces']
    assert sum(len(g['marked_Q_polars']) for g in groups) == source['summary']['union_marked_scalar_choices']
    lines = []
    mapping = []
    for index, group in enumerate(groups):
        rows = group['nonlinear_rref_hex']
        marks = group['marked_Q_polars']
        assert len(rows) == 5 and 1 <= len(marks) <= 2 and len(set(marks)) == len(marks)
        code = group['first_source']['code']
        coset = group['first_source']['polar_coset']
        lines.append(' '.join(map(str, [index, code, coset, len(marks)])) + ' '
                     + ' '.join(rows) + ' ' + ' '.join(map(str, marks)) + '\n')
        mapping.append({'state_id': index, 'first_source': group['first_source'],
                        'marked_Q_polars': marks})
    encoded = ''.join(lines).encode()
    with (folder / 'frontier.tsv').open('xb') as handle:
        handle.write(encoded)
    save(folder / 'frontier-map.json', mapping)
    # Known quartic seed, not an arbitrary selected rank-eight scalar.
    negatives = [i for i, g in enumerate(groups) if g['first_source'] == {
        'code': 1586, 'polar_coset': 138420224} and g['marked_Q_polars'] == [138420225]]
    assert len(negatives) == 1
    negative = negatives[0]
    with (folder / 'negative-control.tsv').open('x') as handle:
        handle.write(lines[negative])
    # Four disjoint products plus p5=(x0+x2)(x5+x7). The sixth parallel
    # product p6=(x4+x6)(x1+x3) yields a bent pair after old-wire correction.
    rows = [1 << ((1 << (2*i)) | (1 << (2*i+1))) for i in range(4)]
    rows.append(sum(1 << ((1 << i) | (1 << j)) for i in (0, 2) for j in (5, 7)))
    with (folder / 'positive-control.tsv').open('x') as handle:
        handle.write(' '.join(map(str, [203728, 0, 0, 1])) + ' '
                     + ' '.join(map(hex, rows)) + ' 138420225\n')
    # First hundred and evenly spaced hundred are both retained separately.
    first = list(range(min(100, len(groups))))
    distributed = sorted({i*(len(groups)-1)//99 for i in range(100)})
    for name, indices in (('first100', first), ('distributed100', distributed)):
        with (folder / (name + '.tsv')).open('x') as handle:
            handle.writelines(lines[i] for i in indices)
        save(folder / (name + '-ids.json'), indices)
    result = {'status': 'pass', 'source_path': str(Path(args.input)),
              'source_sha256': hashlib.sha256(raw).hexdigest(),
              'frontier_tsv_sha256': hashlib.sha256(encoded).hexdigest(),
              'states': len(groups), 'Q_marks': sum(len(g['marked_Q_polars']) for g in groups),
              'negative_control_state_id': negative,
              'positive_control_source': 'verify_norm_q4.py actual six-parallel-AND pair',
              'pilot_sizes': [len(first), len(distributed)],
              'scope': 'Exact fixed-coordinate serialization. No input equivalence, exclusion, or novelty claim.'}
    save(folder / 'preparation.json', result)
    print(json.dumps(result, indent=2))


if __name__ == '__main__':
    main()
