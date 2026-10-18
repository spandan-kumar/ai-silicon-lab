"""Independently replay all GF16 six-AND output pairs from the retained summary."""
import itertools
import json
from pathlib import Path
import verify_norm_prefix as v


def span(rows):
    return tuple(sorted({v.combine(rows, mask) for mask in range(1 << len(rows))}))


def power2(value, j):
    for _ in range(j):
        value = v.multiply(value, value)
    return value


def dual(scale, j):
    return [sum((v.multiply(scale, power2(1 << bit, j)) >> row & 1) << bit
                for bit in range(4)) for row in range(4)]


def main():
    path = Path(__file__).resolve().parents[1] / 'reports/sbox_norm_pair_frontier_study.json'
    source = json.loads(path.read_text())['pair_frontier']
    planes = {span([left, right]) for left in range(1, 16) for right in range(left + 1, 16)}
    assert len(planes) == 35
    raw = [sum((point >> bit & 1) << point for point in range(256)) for bit in range(8)]
    field = [v.multiply(point & 15, point >> 4) for point in range(256)]
    targets = [sum((value >> bit & 1) << point for point, value in enumerate(field)) for bit in range(4)]
    seen = set()
    for circuit in source['derived_pair_upper_circuits']:
        plane = tuple(circuit['plane'])
        assert plane not in seen and span(circuit['basis']) == plane
        seen.add(plane)
        factors, decoder = circuit['factor_masks'], circuit['decoder_rows']
        assert len(factors) == 6 and all(0 < x < 256 and 0 < y < 256 for x, y in factors)
        products = [v.combine(raw, left) & v.combine(raw, right) for left, right in factors]
        assert [v.combine(products, row) for row in decoder] == [v.combine(targets, row) for row in circuit['basis']]
        for point in range(256):
            bits = [point >> bit & 1 for bit in range(8)]
            gates = [v.combine(bits, left) & v.combine(bits, right) for left, right in factors]
            assert [v.combine(gates, row) for row in decoder] == [(field[point] & row).bit_count() % 2 for row in circuit['basis']]
    assert seen == planes
    # Polar ranks independently establish the weight>=4 premise of the
    # parallel lower bound. This is not an unrestricted decoder argument.
    for mask in range(1, 16):
        form = v.anf(v.combine(targets, mask))
        rows = [sum(form[(1 << i) | (1 << j)] << j for j in range(8) if i != j) for i in range(8)]
        assert v.rank(rows) == 8
    counts = {}
    for width in (5, 6):
        codes = {span([left, right]) for left in range(1, 1 << width) for right in range(left + 1, 1 << width)}
        counts[width] = [len(codes), sum(min(value.bit_count() for value in code if value) >= 4 for code in codes)]
    assert counts == {5: [155, 0], 6: [651, 15]}
    actions = [dual(scale, j) for scale in range(1, 16) for j in range(4)]
    remaining = set(planes); orbits = []
    while remaining:
        plane = min(remaining)
        orbit = {tuple(sorted(v.combine(rows, value) for value in plane)) for rows in actions}
        assert orbit <= remaining
        remaining -= orbit; orbits.append(len(orbit))
    assert sorted(orbits) == [5, 30]
    print(json.dumps({'status': 'pass', 'verified_six_AND_pair_circuits': 35,
        'scalar_output_rows_verified': 8960, 'nonzero_target_polar_ranks': [8] * 15,
        'semilinear_plane_orbit_sizes': sorted(orbits), 'decoder_code_counts': counts,
        'parallel_pair_complexity': 6, 'unrestricted_pair_lower_bound_reproved': False,
        'full_GF16_eight_AND_candidate': False, 'world_first_established': False}, indent=2))


if __name__ == '__main__':
    main()
