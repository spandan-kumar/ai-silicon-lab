"""Small deterministic regressions for the experimental affine search tools."""

import unittest

import search_sbox_self_equivalence as orbit
import xor_distance_heuristic as distance


class SearchTests(unittest.TestCase):
    def test_affine_phases_and_shared_fanout(self):
        targets = [(3, 1), (7, 0), (7, 1), (0, 0), (0, 1), (1, 1)]
        emitter = orbit.Emitter()
        outputs = distance.synthesize(emitter, ["U0", "U1", "U2"], targets)
        values = orbit.symbolic(emitter.operations, ["U0", "U1", "U2"])
        self.assertEqual([values[name] for name in outputs], targets)
        repeat = orbit.Emitter()
        self.assertEqual(distance.synthesize(repeat, ["U0", "U1", "U2"], targets), outputs)
        self.assertEqual(repeat.operations, emitter.operations)

    def test_18_dimensional_formal_identity(self):
        sources = [f"p{i}" for i in range(18)]
        targets = [(1 | (1 << 17), 1)]
        emitter = orbit.Emitter()
        outputs = distance.synthesize(emitter, sources, targets)
        values = orbit.symbolic(emitter.operations, sources)
        self.assertEqual([values[name] for name in outputs], targets)
        self.assertEqual(len(emitter.operations), 1)

    def test_dimension_guard(self):
        with self.assertRaises(ValueError):
            distance.synthesize(orbit.Emitter(), [f"p{i}" for i in range(19)], [])

    def test_resource_guards(self):
        for attribute, forced in (("MAX_XOR_GATES", 0), ("MAX_SECONDS", -1.0)):
            previous = getattr(distance, attribute)
            try:
                setattr(distance, attribute, forced)
                with self.assertRaises(RuntimeError):
                    distance.synthesize(orbit.Emitter(), ["U0", "U1"], [(3, 0)])
            finally:
                setattr(distance, attribute, previous)

    def test_target_closure_bound(self):
        self.assertEqual(orbit.prefix_lower_bound([(3, 0)]), 1)
        self.assertEqual(orbit.prefix_lower_bound([(7, 0)]), 2)
        self.assertEqual(orbit.prefix_lower_bound([(3, 0), (7, 1)]), 2)

    def test_output_before_final_and_is_not_lost(self):
        tail = [("XOR", "S0", "a1", "a2")]
        boundary = orbit.tail_boundary(tail, ["S0", "S1"])
        self.assertEqual(boundary, ["S1", "a1", "a2"])
        values = orbit.symbolic(tail, boundary)
        self.assertEqual(values["S1"], (1, 0))
        self.assertEqual(values["S0"], (6, 0))

    def test_self_equivalence_nontrivial_cases(self):
        oracle = orbit.load_sbox()
        for a, k in ((1, 0), (8, 0), (135, 7), (255, 4)):
            before, after = orbit.transforms(a, k)
            orbit.affine_rows(before)
            orbit.affine_rows(after)
            self.assertEqual([after[oracle[before[x]]] for x in range(256)], list(oracle))

    def test_complement_absorption_respects_fixed_middle(self):
        operations = [("XOR", "middle", "U0", "U1"),
                      ("XOR", "zero", "U0", "U0"),
                      ("XNOR", "out", "middle", "zero")]
        self.assertEqual(orbit.simplify(operations, ["out"]),
                         [("XNOR", "out", "U0", "U1")])
        retained = orbit.simplify(operations, ["out"], protected={"middle"})
        self.assertEqual(retained, operations)
        self.assertEqual(orbit.symbolic(retained, ["U0", "U1"])["out"], (3, 1))


if __name__ == "__main__":
    unittest.main()
