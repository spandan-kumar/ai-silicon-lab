"""Replay scalar quadratic counterexamples without a solver or run archive."""
import json


def rank(columns):
    pivots = {}
    for value in columns:
        while value:
            bit = value.bit_length() - 1
            if bit not in pivots:
                pivots[bit] = value
                break
            value ^= pivots[bit]
    return len(pivots)


def combine(values, mask):
    result = 0
    for bit, value in enumerate(values):
        if mask >> bit & 1:
            result ^= value
    return result


def anf(truth):
    coefficients = [truth >> point & 1 for point in range(256)]
    for bit in range(8):
        for point in range(256):
            if point >> bit & 1:
                coefficients[point] ^= coefficients[point ^ (1 << bit)]
    return coefficients


def multiply(left, right):
    result = 0
    while right:
        if right & 1:
            result ^= left
        right >>= 1
        left <<= 1
        if left & 16:
            left ^= 0x13
    return result


def replay(label, factors, expected, expected_high_rank):
    values = [sum((point >> bit & 1) << point for point in range(256))
              for bit in range(8)]
    for index, (left, right) in enumerate(factors):
        assert left < 1 << (8 + index) and right < 1 << (8 + index)
        values.append(combine(values, left) & combine(values, right))
    output = combine(values[8:], 31)
    assert output == expected
    forms = list(map(anf, values[8:]))
    high = [sum(value << point for point, value in enumerate(form)
                if point.bit_count() > 2) for form in forms]
    target_anf = anf(output)
    assert all(not value for point, value in enumerate(target_anf)
               if point.bit_count() > 2)
    polar = [sum(target_anf[(1 << i) | (1 << j)] << j
                 for j in range(8) if i != j) for i in range(8)]
    assert rank(polar) == 8 and rank(high) == expected_high_rank
    assert rank(values) - rank(values[:8]) == 5
    return {"label": label, "factor_masks": factors, "output_mask": 7936,
            "verified_inputs": 256, "target_polar_rank": rank(polar),
            "high_degree_projection_rank": rank(high),
            "gate_degrees": [max(point.bit_count() for point, value in enumerate(form)
                                 if value) for form in forms],
            "quadratic_gate_selectors": [mask for mask in range(32)
                                         if not combine(high, mask)]}, values


def main():
    raw = [sum((point >> bit & 1) << point for point in range(256)) for bit in range(8)]
    target = (raw[0] & raw[1]) ^ (raw[2] & raw[3]) ^ (raw[4] & raw[5]) ^ (raw[6] & raw[7])
    rank_two, _ = replay("generic-rank-two", [[1, 2], [8, 260], [32, 272], [40, 256], [64, 128]], target, 2)
    rank_three, _ = replay("generic-rank-three", [[1, 2], [8, 260], [32, 272], [128, 320], [168, 256]], target, 3)
    products = [multiply(point & 15, point >> 4) for point in range(256)]
    targets = [sum((value >> bit & 1) << point for point, value in enumerate(products)) for bit in range(4)]
    exact, values = replay("GF16-output-bit-zero", [[1, 16], [128, 258], [64, 260], [32, 264], [224, 256]], targets[0], 3)
    intersection = [mask for mask in range(1, 16)
                    if rank([*values, combine(targets, mask)]) == rank(values)]
    assert exact["quadratic_gate_selectors"] == [0, 1, 30, 31] and intersection == [1]
    print(json.dumps({"status": "pass", "circuits": [rank_two, rank_three, exact],
                      "GF16_target_combinations_in_prefix": intersection,
                      "complete_GF16_multiplier": False, "world_first_established": False}, indent=2))


if __name__ == "__main__":
    main()
