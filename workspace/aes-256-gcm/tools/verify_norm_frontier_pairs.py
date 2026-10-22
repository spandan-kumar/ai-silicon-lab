"""Independent symbolic one-product bent-pair necessary test for W5 states.

EXPERIMENTAL CHECKPOINT (2026-10-22): only built-in controls have run. No
inventory-state audit or full producer comparison is complete. --compare
expects a wrapped cases schema, not the C++ scanner's current raw JSONL.
No production-scanner imports: Boolean-ring monomial union, 18-variable row
equations, projected right kernels, and low-pivot matrix rank. This is an
algorithmic replay by the same research author, not external peer review.
Positive cases have actual one-AND witnesses replayed over all 256 inputs.
Negative cases exhaust all 8191 nonzero left forms. No field embedding is
assumed: passing is necessary, not sufficient, for a GF16 continuation.
"""
import argparse
from collections import Counter
from functools import lru_cache
import hashlib
import itertools
import json
from pathlib import Path
import random
import time


PAIRS = tuple(itertools.combinations(range(8), 2))
RAW = tuple(1 << (1 << i) for i in range(8))
AFFINE = 1 | sum(RAW)
HIGH = sum(1 << m for m in range(256) if m.bit_count() > 2)
NONLINEAR = ((1 << 256) - 1) ^ AFFINE
MONOMIAL_TRUTHS = tuple(sum((x & m == m) << x for x in range(256))
                        for m in range(256))


def support(value):
    while value:
        bit = value & -value
        yield bit.bit_length() - 1
        value ^= bit


def combine(values, selector):
    result = 0
    for i in support(selector):
        result ^= values[i]
    return result


def multiply(left, right):
    """Boolean-ring product: x_A x_B = x_(A union B)."""
    result = 0
    for i in support(left):
        for j in support(right):
            result ^= 1 << (i | j)
    return result


def truth(form):
    return combine(MONOMIAL_TRUTHS, form)


def low_rows(values):
    rows = {}
    for value in values:
        while value:
            p = (value & -value).bit_length() - 1
            if p not in rows:
                rows[p] = value
                break
            value ^= rows[p]
    return rows


def reduce(value, rows):
    for p in sorted(rows):
        if value >> p & 1:
            value ^= rows[p]
    return value


def joint_kernel(columns):
    """Construct equations by ANF monomial, then solve with free variables.

    This is row reduction of equations, not labelled production-column
    elimination. The final five variables are explicit old-wire corrections.
    """
    equations = {}
    for j, column in enumerate(columns):
        for monomial in support(column):
            equations[monomial] = equations.get(monomial, 0) ^ (1 << j)
    rows = low_rows(equations.values())
    kernel = []
    for free in range(len(columns)):
        if free in rows:
            continue
        vector = 1 << free
        for pivot in sorted(rows, reverse=True):
            if (rows[pivot] & vector).bit_count() & 1:
                vector ^= 1 << pivot
        assert combine(columns, vector) == 0
        kernel.append(vector)
    assert len(kernel) + len(rows) == len(columns)
    return kernel


def project_right(kernel, width):
    """Project the joint kernel and retain one cancellation witness per row."""
    mask = (1 << width) - 1
    rows = {}
    pure_old = []
    for vector in kernel:
        value = vector & mask
        while value:
            p = (value & -value).bit_length() - 1
            if p not in rows:
                rows[p] = vector
                break
            vector ^= rows[p]
            value = vector & mask
        else:
            assert vector & mask == 0
            pure_old.append(vector >> width)
    return list(rows.values()), pure_old


def polar(form):
    return sum(((form >> ((1 << a) | (1 << b))) & 1) << k
               for k, (a, b) in enumerate(PAIRS))


def unpolar(value):
    return sum(((value >> k) & 1) << ((1 << a) | (1 << b))
               for k, (a, b) in enumerate(PAIRS))


@lru_cache(maxsize=65536)
def matrix_rank(value):
    rows = [0] * 8
    for k, (a, b) in enumerate(PAIRS):
        if value >> k & 1:
            rows[a] |= 1 << b
            rows[b] |= 1 << a
    return len(low_rows(rows))


def matchings(vertices):
    if not vertices:
        yield ()
        return
    a, *rest = vertices
    for i, b in enumerate(rest):
        for tail in matchings(rest[:i] + rest[i + 1:]):
            yield ((a, b),) + tail


MATCHING_MASKS = tuple(sum(1 << PAIRS.index(pair) for pair in matching)
                       for matching in matchings(list(range(8))))


def pfaffian(value):
    return sum(value & mask == mask for mask in MATCHING_MASKS) & 1


def span(basis):
    values = [0]
    for value in basis:
        values += [old ^ value for old in values]
    return values


def witness_replay(forms, old_forms, left, right, cancel, q):
    left_anf = combine(forms, left)
    right_anf = combine(forms, right)
    product = multiply(left_anf, right_anf)
    candidate = product ^ old_forms[cancel]
    assert not candidate & HIGH
    value = polar(candidate)
    assert matrix_rank(value) == matrix_rank(value ^ q) == 8
    assert pfaffian(value) == pfaffian(value ^ q) == 1
    expected = truth(left_anf) & truth(right_anf)
    assert truth(product) == expected
    assert truth(candidate) == expected ^ truth(old_forms[cancel])
    # Compare direct point evaluation, not a second ANF transform.
    candidate_truth = truth(candidate)
    translated_truth = truth(candidate ^ unpolar(q))
    for x in range(256):
        direct_left = sum(x & m == m for m in support(left_anf)) & 1
        direct_right = sum(x & m == m for m in support(right_anf)) & 1
        direct_old = sum(x & m == m for m in support(old_forms[cancel])) & 1
        direct_t = direct_left * direct_right ^ direct_old
        assert (candidate_truth >> x & 1) == direct_t
        direct_q = sum(x & m == m for m in support(unpolar(q))) & 1
        assert (translated_truth >> x & 1) == direct_t ^ direct_q
    return {
        'left': left, 'right': right, 'old_cancel': cancel,
        'candidate_anf_hex': hex(candidate), 'candidate_polar': value,
        'marked_Q_polar': q, 'rank_t': 8, 'rank_t_plus_Q': 8,
        'additional_ANDs': 1, 'full_input_rows_checked': 256,
        'affine_output_correction_free': True,
    }


def audit(state, state_id=None, force_complete=False):
    """Return exact necessary-test verdicts and concrete positive witnesses."""
    start = time.monotonic()
    old = [int(value, 0) for value in state['nonlinear_rref_hex']]
    assert len(old) == 5 and len(low_rows(old)) == 5
    assert all(value & AFFINE == 0 for value in old)
    forms = list(RAW) + old
    assert len(low_rows(forms)) == 13
    old_forms = [combine(old, s) for s in range(32)]
    K_selectors = [s for s, form in enumerate(old_forms) if not form & HIGH]
    offsets = {s: polar(old_forms[s]) for s in K_selectors}
    assert len(set(offsets.values())) == len(offsets)
    Krows = low_rows(offsets.values())
    Kdim = len(Krows)
    assert len(offsets) == 1 << Kdim
    qs = state['marked_Q_polars']
    assert qs and len(qs) == len(set(qs))
    assert all(q in offsets.values() and matrix_rank(q) == 8 for q in qs)
    products = [[multiply(a, b) for b in forms] for a in forms]
    # Full basis product checks distinguish multiplication and bit ordering.
    ts = [truth(form) for form in forms]
    for i, j in itertools.product(range(13), repeat=2):
        assert truth(products[i][j]) == ts[i] & ts[j]
    witnesses = {}
    seen = set()
    histogram = Counter()
    pairs = 0
    lefts = 0
    previous = 0
    columns = [0] * 13
    stopped_early = False
    for left in range(1, 8192):
        for bit in support(previous ^ left):
            columns = [a ^ b for a, b in zip(columns, products[bit])]
        previous = left
        kernel = joint_kernel([column & HIGH for column in columns]
                              + [form & HIGH for form in old])
        right_basis, pure_old = project_right(kernel, 13)
        assert len(low_rows(pure_old)) == Kdim
        assert set(span(pure_old)) == set(K_selectors)
        histogram[len(right_basis)] += 1
        lefts += 1
        for joint in span(right_basis)[1:]:
            right, base_cancel = joint & 8191, joint >> 13
            assert right and base_cancel < 32
            if right < left:
                continue
            pairs += 1
            residue = combine(columns, right) ^ old_forms[base_cancel]
            assert not residue & HIGH
            packed = polar(residue)
            key = reduce(packed, Krows)
            if not key or key in seen:
                continue
            seen.add(key)
            for q in qs:
                if q in witnesses:
                    continue
                for extra, offset in offsets.items():
                    value = packed ^ offset
                    if matrix_rank(value) == matrix_rank(value ^ q) == 8:
                        witness = witness_replay(forms, old_forms, left, right,
                                                 base_cancel ^ extra, q)
                        assert reduce(witness['candidate_polar'], Krows) == key
                        witness['nonzero_polar_coset'] = key
                        witness['marked_Q_old_decoder'] = next(
                            s for s, offset in offsets.items() if offset == q)
                        witnesses[q] = witness
                        break
            if len(witnesses) == len(qs) and not force_complete:
                stopped_early = True
                break
        if len(witnesses) == len(qs) and not force_complete:
            break
    result = {
        'state_id': state_id, 'marked_Q_polars': qs,
        'pair_found': [q in witnesses for q in qs],
        'witnesses': [witnesses.get(q) for q in qs],
        'all_Qs_positive': len(witnesses) == len(qs),
        'complete_left_scan': lefts == 8191 and not stopped_early,
        'left_forms_checked': lefts,
        'eligible_unordered_pairs': pairs,
        'quadratic_nonzero_cosets_seen': len(seen),
        'sorted_nonzero_cosets_sha256': hashlib.sha256(json.dumps(
            sorted(seen), separators=(',', ':')).encode()).hexdigest(),
        'right_kernel_dimension_histogram': dict(sorted(histogram.items())),
        'K_dimension': Kdim, 'higher_degree_rank': 5 - Kdim,
        'basis_product_truth_rows_checked': 169 * 256,
        'witness_truth_rows_checked': 256 * len(witnesses),
        'algorithm_seconds': time.monotonic() - start,
    }
    assert result['all_Qs_positive'] or result['complete_left_scan']
    return result


def controls():
    start = time.monotonic()
    rng = random.Random(20261022)
    kernel_controls = 0
    for n in range(10):
        for _ in range(32):
            columns = [rng.randrange(1 << 14) for _ in range(n)]
            got = set(span(joint_kernel(columns)))
            expected = {s for s in range(1 << n) if not combine(columns, s)}
            assert got == expected
            kernel_controls += 1
    product_controls = 0
    for _ in range(128):
        a, b = (rng.getrandbits(256) for _ in range(2))
        assert truth(multiply(a, b)) == truth(a) & truth(b)
        product_controls += 1
    rank_controls = 0
    for value in [rng.getrandbits(28) for _ in range(2048)]:
        assert bool(pfaffian(value)) == (matrix_rank(value) == 8)
        assert polar(unpolar(value)) == value
        rank_controls += 1
    # Known six-parallel-product pair: the sixth product has one-AND cost
    # relative to W5, while neither this scalar nor its Q translate is old.
    a, b, c, d, e, f, g, h = RAW
    old = [multiply(a, b), multiply(c, d), multiply(e, f), multiply(g, h),
           multiply(a ^ c, f ^ h)]
    q = polar(combine(old, 15))
    state = {'nonlinear_rref_hex': list(map(hex, old)), 'marked_Q_polars': [q]}
    positive = audit(state, state_id='six_parallel_positive')
    assert positive['pair_found'] == [True]
    # Zero quotient is not a new direction, even if old polars contain a
    # nonsingular pair. This is a direct predicate control, not cost evidence.
    t = multiply(e ^ g, b ^ d) ^ old[4] ^ old[0] ^ old[2]
    assert matrix_rank(polar(t)) == matrix_rank(polar(t) ^ q) == 8
    rows = low_rows([polar(combine(old, s)) for s in range(32)] + [polar(t)])
    assert reduce(polar(t), rows) == reduce(polar(t) ^ q, rows) == 0
    return {
        'status': 'pass', 'joint_equation_bruteforce_controls': kernel_controls,
        'symbolic_product_full_truth_controls': product_controls,
        'Pfaffian_vs_rank_controls': rank_controls,
        'positive_one_AND_pair': positive,
        'zero_quotient_rejected_predicate_control': True,
        'algorithm_seconds': time.monotonic() - start,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path)
    parser.add_argument('--ids', type=int, nargs='+')
    parser.add_argument('--out', type=Path, required=True)
    parser.add_argument('--compare', type=Path)
    parser.add_argument('--controls', action='store_true')
    parser.add_argument('--force-complete', action='store_true')
    args = parser.parse_args()
    assert not args.out.exists()
    start = time.monotonic()
    result = {'status': 'pass', 'external_peer_review': False,
              'algorithm': 'monomial-union, joint row equations, projected right kernels, all K offsets, low-pivot rank',
              'scope': 'One-product bent-pair necessary test only; no field embedding or unrestricted eight-AND conclusion.',
              'source_sha256': hashlib.sha256(Path(__file__).read_bytes()).hexdigest()}
    if args.controls:
        result['controls'] = controls()
    if args.input is not None:
        raw = args.input.read_bytes()
        source = json.loads(raw)
        ids = list(range(len(source['groups']))) if args.ids is None else args.ids
        assert ids and len(ids) == len(set(ids))
        result['input_sha256'] = hashlib.sha256(raw).hexdigest()
        result['cases'] = []
        for i in ids:
            case = audit(source['groups'][i], i, args.force_complete)
            result['cases'].append(case)
            print(json.dumps(case), flush=True)
        result['full_input_checked'] = len(ids) == len(source['groups'])
        result['state_ids'] = ids
        if args.compare is not None:
            producer = json.loads(args.compare.read_bytes())
            producer_cases = producer['cases']
            by_id = {case['state_id']: case for case in producer_cases}
            for case in result['cases']:
                other = by_id[case['state_id']]
                assert case['marked_Q_polars'] == other['marked_Q_polars']
                assert case['pair_found'] == other['pair_found']
            result['producer_verdicts_agree'] = True
    assert args.controls or args.input is not None
    result['algorithm_seconds'] = time.monotonic() - start
    with args.out.open('x') as handle:
        json.dump(result, handle, indent=2)
        handle.write('\n')
    print(json.dumps({k: v for k, v in result.items() if k not in ('cases', 'controls')}), flush=True)


if __name__ == '__main__':
    main()
