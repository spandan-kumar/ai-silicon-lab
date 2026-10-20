"""Independent block-type orbit enumeration and target-orientation controls.

No production import or solver. Local affine input maps are constructed both
from literal two-bit substitutions and from the four proposed generators.
The global orbit count is obtained from multisets and orbit cardinalities,
not by traversing the 2,794,155-plane graph.
"""
from collections import Counter
import itertools
import json
import math
from pathlib import Path

HERE = Path(__file__).resolve().parent


def combine(rows, mask):
    value = 0
    for bit, row in enumerate(rows):
        if mask >> bit & 1:
            value ^= row
    return value


def compose(outer, inner):
    return tuple(combine(outer, value) for value in inner)


def rank(rows):
    pivots = {}
    for row in rows:
        while row:
            bit = row.bit_length() - 1
            if bit in pivots:
                row ^= pivots[bit]
            else:
                pivots[bit] = row
                break
    return len(pivots)


def anf(truth, n):
    values = [(truth >> point) & 1 for point in range(1 << n)]
    for bit in range(n):
        for point in range(1 << n):
            if point >> bit & 1:
                values[point] ^= values[point ^ (1 << bit)]
    return sum(value << point for point, value in enumerate(values))


def local_group():
    generators = [(2, 1, 4), (3, 2, 6), (1, 2, 6), (1, 2, 5)]
    generated = {(1, 2, 4)}
    frontier = [(1, 2, 4)]
    while frontier:
        old = frontier.pop()
        for generator in generators:
            new = compose(generator, old)
            if new not in generated:
                generated.add(new)
                frontier.append(new)
    literal = set()
    for left, right in itertools.permutations(range(1, 4), 2):
        for c, d in itertools.product(range(2), repeat=2):
            truth = [0, 0, 0]
            for point in range(4):
                a = (left & point).bit_count() % 2 ^ c
                b = (right & point).bit_count() % 2 ^ d
                for index, value in enumerate([a, b, a & b]):
                    truth[index] |= value << point
            images = []
            for value in truth:
                form = anf(value, 2)
                images.append(((form >> 1) & 1) | (((form >> 2) & 1) << 1) |
                              (((form >> 3) & 1) << 2))
            literal.add(tuple(images))
    assert generated == literal and len(generated) == 24
    assert all(rank(mapping) == 3 for mapping in generated)
    return sorted(generated), generators


def global_masks(types, local_representatives):
    left, right = 0, 0
    for block, kind in enumerate(types):
        pair = local_representatives[kind]
        for index, local in enumerate(pair):
            mask = (((local & 1) << (2 * block)) | (((local >> 1) & 1) << (2 * block + 1)) |
                    (((local >> 2) & 1) << (8 + block)))
            if index == 0:
                left ^= mask
            else:
                right ^= mask
    return left, right


def field(x, y):
    out = 0
    for _ in range(4):
        if y & 1:
            out ^= x
        x <<= 1
        if x & 16:
            x ^= 19
        y >>= 1
    return out


def polar(form):
    return sum(((form >> ((1 << i) | (1 << j))) & 1) << bit
               for bit, (i, j) in enumerate(itertools.combinations(range(8), 2)))


def main():
    group, generators = local_group()
    canonical = {}
    for pair in itertools.product(range(8), repeat=2):
        canonical[pair] = min((combine(g, pair[0]), combine(g, pair[1])) for g in group)
    local_representatives = sorted(set(canonical.values()))
    type_index = {pair: index for index, pair in enumerate(local_representatives)}
    local_type = {pair: type_index[representative] for pair, representative in canonical.items()}
    sizes = Counter(local_type.values())
    assert len(local_representatives) == 11
    assert sum(sizes.values()) == 64
    basis_changes = [((a, b), (c, d)) for a, b, c, d in itertools.product(range(2), repeat=4)
                     if a * d ^ b * c]
    assert len(basis_changes) == 6
    type_actions = []
    for (a, b), (c, d) in basis_changes:
        action = []
        for left, right in local_representatives:
            action.append(local_type[((a * left) ^ (b * right), (c * left) ^ (d * right))])
        type_actions.append(action)
        for pair, kind in local_type.items():
            left, right = pair
            assert action[kind] == local_type[((a * left) ^ (b * right), (c * left) ^ (d * right))]
    raw = [sum(((point >> bit) & 1) << point for point in range(256)) for bit in range(8)]
    products = [raw[2 * i] & raw[2 * i + 1] for i in range(4)]
    V0 = raw + products
    assert rank(V0) == 12
    high_mask = sum(1 << mask for mask in range(256) if mask.bit_count() > 2)
    orbits = {}
    multiset_count = 0
    independent_multisets = 0
    for types in itertools.combinations_with_replacement(range(11), 4):
        multiset_count += 1
        left, right = global_masks(types, local_representatives)
        if not left or not right or left == right:
            continue
        independent_multisets += 1
        images = {tuple(sorted(action[kind] for kind in types)) for action in type_actions}
        key = min(images)
        if key in orbits:
            continue
        ordered_count = 0
        for member in images:
            multiplicities = Counter(member)
            count = math.factorial(4)
            for multiplicity in multiplicities.values():
                count //= math.factorial(multiplicity)
            for kind in member:
                count *= sizes[kind]
            ordered_count += count
        assert ordered_count % 6 == 0
        left, right = global_masks(key, local_representatives)
        p = combine(V0, left) & combine(V0, right)
        form = anf(p, 8)
        degree = max((mask.bit_count() for mask in range(256) if form >> mask & 1), default=0)
        category = ('nonquadratic' if form & high_mask else
                    'quadratic-new' if rank(V0 + [p]) == 13 else 'old-space')
        nonzero = sorted([left, right, left ^ right])
        orbits[key] = {'block_type_multiset': list(key), 'plane_factor_masks': nonzero[:2],
                       'orbit_plane_count': ordered_count // 6,
                       'operand_basis_multiset_orbit_size': len(images),
                       'product_degree': degree, 'category': category}
    assert multiset_count == 1001
    assert sum(row['orbit_plane_count'] for row in orbits.values()) == 2794155
    # Canonical Q does not freeze the remaining target orientation. Start with
    # GF16 in coordinates making bit0=sum a_i*b_i, then shear a0->a0+b0.
    T0 = [0] * 4
    T1 = [0] * 4
    for point in range(256):
        a0, b0, a1, b1, a2, b2, a3, b3 = [(point >> bit) & 1 for bit in range(8)]
        def output(a0):
            x = a0 | (a1 << 1) | (a2 << 2) | (a3 << 3)
            y = b0 | (b3 << 1) | (b2 << 2) | (b1 << 3)
            return field(x, y)
        first, second = output(a0), output(a0 ^ b0)
        for bit in range(4):
            T0[bit] |= ((first >> bit) & 1) << point
            T1[bit] |= ((second >> bit) & 1) << point
    Q = combine(products, 15)
    assert T0[0] == Q
    assert T1[0] == Q ^ raw[1]
    P0 = sorted({polar(anf(combine(T0, mask), 8)) for mask in range(16)})
    P1 = sorted({polar(anf(combine(T1, mask), 8)) for mask in range(16)})
    assert P0 != P1
    assert polar(anf(Q, 8)) in P0 and polar(anf(Q, 8)) in P1
    report = {'status': 'pass', 'local_AGL2_order': len(group),
              'local_generators_images_a_b_p': generators,
              'global_group_order': 24 ** 4 * math.factorial(4),
              'local_ordered_pair_types': [{'representative': list(pair), 'size': sizes[index]}
                                           for index, pair in enumerate(local_representatives)],
              'local_type_GL2_actions': type_actions,
              'four_block_multisets': multiset_count,
              'independent_four_block_multisets': independent_multisets,
              'independent_plane_orbits': len(orbits),
              'orbit_category_counts': dict(Counter(row['category'] for row in orbits.values())),
              'plane_category_counts': {category: sum(row['orbit_plane_count'] for row in orbits.values()
                                                       if row['category'] == category)
                                        for category in {row['category'] for row in orbits.values()}},
              'total_independent_planes': sum(row['orbit_plane_count'] for row in orbits.values()),
              'orbits': [orbits[key] for key in sorted(orbits)],
              'target_orientation_negative_control': {'same_canonical_Q_mod_affine': True,
                                                      'same_K0_preserved': True,
                                                      'target_polar_spaces_equal': False,
                                                      'target_polar_intersection_nonzero_size': len(set(P0) & set(P1)) - 1},
              'no_bent_pair_inventory_executed': True, 'Q_by_four_branch_excluded': False,
              'new_solver_runs': 0, 'world_first_established': False}
    with (HERE / 'orbit-controls-report.json').open('x') as handle:
        json.dump(report, handle, indent=2)
        handle.write('\n')
    print(json.dumps({key: report[key] for key in ['status', 'local_AGL2_order', 'global_group_order',
          'independent_plane_orbits', 'orbit_category_counts', 'plane_category_counts',
          'total_independent_planes', 'target_orientation_negative_control']}))


if __name__ == '__main__':
    main()
    # Independently identify every C++ representative by its block-type orbit.
    cpp = json.loads((HERE / 'report.json').read_text())
    own = json.loads((HERE / 'orbit-controls-report.json').read_text())
    group, _ = local_group()
    representatives = [tuple(row['representative']) for row in own['local_ordered_pair_types']]
    indices = {row: i for i, row in enumerate(representatives)}
    types = {pair: indices[min((combine(g, pair[0]), combine(g, pair[1])) for g in group)]
             for pair in itertools.product(range(8), repeat=2)}
    expected = {tuple(row['block_type_multiset']): row for row in own['orbits']}
    seen = set()
    for row in cpp['orbits']:
        left, right = row['factor_masks']
        local_types = []
        for block in range(4):
            pair = tuple(((value >> (2 * block)) & 3) | (((value >> (8 + block)) & 1) << 2)
                         for value in (left, right))
            local_types.append(types[pair])
        key = min(tuple(sorted(action[kind] for kind in local_types))
                  for action in own['local_type_GL2_actions'])
        assert key not in seen
        seen.add(key)
        check = expected[key]
        assert row['orbit_size'] == check['orbit_plane_count']
        assert max(0, row['seed_degree']) == check['product_degree']
    assert seen == set(expected) and len(seen) == cpp['plane_orbits'] == 216
    with (HERE / 'comparison.json').open('x') as handle:
        json.dump({'status':'pass', 'CXX_orbits_independently_identified':len(seen),
                   'total_planes':own['total_independent_planes'],
                   'category_counts':own['orbit_category_counts'],
                   'plane_category_counts':own['plane_category_counts'],
                   'target_orientation_negative_control':own['target_orientation_negative_control'],
                   'original_failed_script_preserved':True,
                   'scope':'Plane orbits and prefix normal form only; no field exclusion.'},handle,indent=2)
