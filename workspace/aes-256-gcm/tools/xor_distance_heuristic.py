"""Deterministic, bounded XOR synthesis using exact available-word distances.

This is a gate-count heuristic, not an optimal circuit synthesis algorithm.
For at most 17 independent formal inputs, distance[x] is the fewest currently
available wires whose XOR equals x. Adding vector v updates every distance by
min(distance[x], 1 + distance[x ^ v]); the old array is used on both sides.
Greedy pair selection minimizes the sum of remaining target word distances.
Ties maximize their squared sum, then use numeric vector and operand order.
New target wires receive their requested phase at no extra gate cost by using
XOR/XNOR as appropriate. Complements of source wires or conflicting requests
for both phases of one form still require an explicit gate.
"""

from __future__ import annotations

import time

import numpy as np


MAX_DIMENSION = 17
MAX_TARGETS = 64
MAX_XOR_GATES = 256
MAX_SECONDS = 60.0


def synthesize(emitter, sources, targets):
    """Emit XOR/XNOR gates and return wires for (formal-mask, phase) targets.

    Source wires are treated as independent formal variables even if their
    actual circuit functions are dependent. Every emitted identity therefore
    remains valid, without relying on don't-cares. A limit violation raises
    before returning a candidate; no truncated result is returned as valid.
    """
    sources, targets = list(sources), list(targets)
    dimension = len(sources)
    if not 1 <= dimension <= MAX_DIMENSION:
        raise ValueError(f"source dimension must be 1..{MAX_DIMENSION}")
    if len(targets) > MAX_TARGETS:
        raise ValueError(f"at most {MAX_TARGETS} targets are supported")
    size = 1 << dimension
    for mask, phase in targets:
        if not isinstance(mask, int) or not 0 <= mask < size or phase not in (0, 1):
            raise ValueError("target must have an in-range integer mask and binary phase")
    # Ignoring duplicate targets avoids overweighting fanout in the objective.
    target_masks = np.array(sorted({mask for mask, _ in targets if mask}), dtype=np.uint32)
    requested_phases = {}
    for mask, phase in targets:
        requested_phases.setdefault(mask, set()).add(phase)
    indices = np.arange(size, dtype=np.uint32)
    distance = np.fromiter((value.bit_count() for value in range(size)), dtype=np.int16)
    vectors = [1 << index for index in range(dimension)]
    wires = list(sources)
    available = dict(zip(vectors, wires))
    wire_phases = [0] * dimension
    started = time.monotonic()
    added = 0
    while any(int(mask) not in available for mask in target_masks):
        if added >= MAX_XOR_GATES or time.monotonic() - started > MAX_SECONDS:
            raise RuntimeError("bounded XOR synthesis exceeded its gate or runtime limit")
        pairs = {}
        for right in range(1, len(vectors)):
            for left in range(right):
                vector = vectors[left] ^ vectors[right]
                if vector and vector not in available:
                    pair = (left, right)
                    if vector not in pairs or pair < pairs[vector]:
                        pairs[vector] = pair
        # Only target entries are needed to score every proposed new wire.
        candidates = np.array(sorted(pairs), dtype=np.uint32)
        new_target_distances = np.minimum(
            distance[target_masks][None, :],
            1 + distance[candidates[:, None] ^ target_masks[None, :]],
        ).astype(np.int32)
        sums = new_target_distances.sum(axis=1)
        squares = (new_target_distances * new_target_distances).sum(axis=1)
        choice = int(np.lexsort((candidates, -squares, sums))[0])
        vector = int(candidates[choice])
        if int(sums[choice]) >= int(distance[target_masks].sum()):
            raise AssertionError("an unresolved target must have a distance-reducing pair")
        left, right = pairs[vector]
        phase = int(requested_phases.get(vector) == {1})
        operation = "XNOR" if phase ^ wire_phases[left] ^ wire_phases[right] else "XOR"
        wire = emitter.gate(operation, wires[left], wires[right])
        vectors.append(vector)
        wires.append(wire)
        wire_phases.append(phase)
        available[vector] = wire
        distance = np.minimum(distance, 1 + distance[indices ^ vector])
        added += 1
    outputs = []
    complemented = {}
    available_phases = dict(zip(vectors, wire_phases))
    for mask, phase in targets:
        wire = available[mask] if mask else emitter.constant_zero()
        if phase != available_phases.get(mask, 0):
            if mask not in complemented:
                complemented[mask] = emitter.gate("XNOR", wire, emitter.constant_zero())
            wire = complemented[mask]
        outputs.append(wire)
    return outputs
