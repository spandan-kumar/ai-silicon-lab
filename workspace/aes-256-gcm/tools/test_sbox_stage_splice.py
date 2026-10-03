"""Deterministic controls for the fixed-interface lower-bound verifier."""

from itertools import combinations
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

import analyze_sbox_stage_splice as splice


class StageSpliceTests(unittest.TestCase):
    def test_span_coefficients_with_dependent_inputs(self):
        vectors = [0b0011, 0b0101, 0b0110, 0b1000]
        span = splice.Span(vectors)
        self.assertEqual(span.rank(), 3)
        for mask in range(16):
            value = splice.combine(vectors, mask)
            residual, coefficients = span.reduce(value)
            self.assertEqual(residual, 0)
            self.assertEqual(splice.combine(vectors, coefficients), value)

    def test_anf_every_monomial(self):
        for mask in range(256):
            truth = sum(((x & mask) == mask) << x for x in range(256))
            self.assertEqual(splice.anf(truth), 1 << mask)
            self.assertEqual(splice.anf(splice.anf(truth)), truth)

    def test_product_search_positive_and_negative(self):
        inputs = splice.INPUTS
        quadratic = [inputs[i] & inputs[j] for i, j in list(combinations(range(8), 2))[:9]]
        initial = [splice.ALL] + inputs + quadratic
        span = splice.Span(initial)
        self.assertEqual(span.rank(), 18)
        target = span.reduce(inputs[1] & inputs[7])[0]
        self.assertNotEqual(target, 0)
        positive = splice.first_product_search(initial, target)
        self.assertEqual(positive["status"], "satisfiable")
        product = int(positive["left_truth"], 16) & int(positive["right_truth"], 16)
        self.assertEqual(span.reduce(product)[0], target)
        # Initial functions have degree <=2, so their products cannot have
        # the degree-eight coefficient of this independently chosen target.
        negative = splice.first_product_search(initial, span.reduce(1 << 255)[0])
        self.assertEqual(negative["status"], "exhausted-no-product")
        self.assertEqual(negative["forms_checked"], 131071)

    def test_cli_guards_preserve_existing_output(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            output = folder / "result.json"
            output.write_text("existing evidence\n")
            script = str(Path(splice.__file__).resolve())
            command = [sys.executable, script, "--source-dir", str(folder), "--output", str(output)]
            result = subprocess.run(command, capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("output must be new", result.stderr)
            self.assertEqual(output.read_text(), "existing evidence\n")

    def test_cli_rejects_unpinned_source(self):
        with tempfile.TemporaryDirectory() as directory:
            folder = Path(directory)
            (folder / next(iter(splice.SOURCES))).write_text("not a pinned source\n")
            output = folder / "result.json"
            result = subprocess.run(
                [sys.executable, str(Path(splice.__file__).resolve()),
                 "--source-dir", str(folder), "--output", str(output)],
                capture_output=True, text=True)
            self.assertEqual(result.returncode, 2)
            self.assertIn("pinned source hash mismatch", result.stderr)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
