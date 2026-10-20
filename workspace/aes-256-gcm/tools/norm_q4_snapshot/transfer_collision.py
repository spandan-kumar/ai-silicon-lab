"""Small exact diagonal-product collision test; no SAT or production imports."""
import itertools
import json
from pathlib import Path
import time

HERE = Path(__file__).resolve().parent
N = 6
RAW = [sum(((point >> bit) & 1) << point for point in range(1 << N)) for bit in range(N)]
PAIRS = list(itertools.combinations(range(N), 2))
DIAGONALS = [(0, 1), (2, 3), (4, 5)]
CROSS = [pair for pair in PAIRS if pair not in DIAGONALS]
AFFINE_MONOMIALS = [0] + [1 << bit for bit in range(N)]
QUADRATIC_MASK = sum(1 << ((1 << i) | (1 << j)) for i, j in PAIRS)
HIGH_MASK = ((1 << (1 << N)) - 1) ^ QUADRATIC_MASK ^ sum(1 << mask for mask in AFFINE_MONOMIALS)
STAGE_MASKS = [sum(1 << point for point in range(1 << N) if not (point >> bit & 1)) for bit in range(N)]


def combine(values, selector):
    result = 0
    for index, value in enumerate(values):
        if selector >> index & 1:
            result ^= value
    return result


def anf(truth):
    for bit, mask in enumerate(STAGE_MASKS):
        truth ^= (truth & mask) << (1 << bit)
    return truth


def residue(polynomial):
    return sum(((polynomial >> ((1 << i) | (1 << j))) & 1) << index
               for index, (i, j) in enumerate(CROSS))


def rank(rows):
    pivots = {}
    for row in rows:
        while row:
            lead = row.bit_length() - 1
            if lead not in pivots:
                pivots[lead] = row
                break
            row ^= pivots[lead]
    return len(pivots)


def polar_rank(polynomial, width=N):
    rows = [0] * width
    for i, j in itertools.combinations(range(width), 2):
        if polynomial >> ((1 << i) | (1 << j)) & 1:
            rows[i] ^= 1 << j
            rows[j] ^= 1 << i
    return rank(rows)


start = time.monotonic()
low = [(1 << (1 << N)) - 1] + RAW + [RAW[i] & RAW[j] for i, j in DIAGONALS]
wires = [combine(low, selector) for selector in range(1 << len(low))]
allowed = {0}
for left in range(1, 1 << N):
    for right in range(left + 1, 1 << N):
        if left != right:
            product = combine(RAW, left) & combine(RAW, right)
            allowed.add(residue(anf(product)))
assert len(wires) == len(set(wires)) == 1024
buckets = {}
checked = 0
candidate = None
for left in range(len(wires)):
    for right in range(left, len(wires)):
        polynomial = anf(wires[left] & wires[right])
        high = polynomial & HIGH_MASK
        checked += 1
        if not high:
            continue
        shadow = residue(polynomial)
        previous = buckets.setdefault(high, {})
        if shadow not in previous:
            for old_shadow, (old_left, old_right, old_polynomial) in previous.items():
                if shadow ^ old_shadow not in allowed:
                    q = old_polynomial ^ polynomial
                    ranks = [polar_rank(q ^ sum((selector >> index & 1) << ((1 << i) | (1 << j))
                                                for index, (i, j) in enumerate(DIAGONALS)))
                             for selector in range(8)]
                    assert min(ranks) >= 4 and not (q & HIGH_MASK)
                    candidate = {'U_V_A_B_low_basis_masks': [old_left, old_right, left, right],
                        'h_ANF_hex': hex(old_polynomial), 'q_ANF_hex': hex(q),
                        'U_V_A_B_ANF_hex': [hex(anf(wires[index])) for index in (old_left, old_right, left, right)],
                        'all8_corrected_polar_ranks': ranks,
                        'interpretation': 'After three diagonal ANDs, h=U*V and g=A*B give q=h+g; '
                            'q has no rank-at-most-two correction by diagonal products.'}
                    break
            previous[shadow] = (left, right, polynomial)
        if candidate:
            break
    if candidate:
        break
report = {'status': 'counterexample-found' if candidate else 'complete-no-low-low-collision-counterexample',
    'input_bits': N, 'low_basis': ['1', 'x0', 'x1', 'x2', 'x3', 'x4', 'x5', 'x0*x1', 'x2*x3', 'x4*x5'],
    'low_wire_count': len(wires), 'unordered_products_checked': checked,
    'all_unordered_products': len(wires) * (len(wires) + 1) // 2,
    'rank_at_most_two_polar_residue_count': len(allowed), 'high_buckets_seen': len(buckets),
    'candidate': candidate, 'algorithm_seconds': time.monotonic() - start,
    'scope': 'Only collisions of two low-low products over the three-pair diagonal precursor. '
             'Not a complete high-using next-gate classification or global rank-one flattening theorem.',
    'world_first_established': False}
with (HERE / 'report.json').open('x') as handle:
    json.dump(report, handle, indent=2)
print(json.dumps(report))
