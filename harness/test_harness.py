#!/usr/bin/env python3
"""Self-tests for the autonomous harness.

The laboratory's rule is that a mechanism is not trusted because it looks
right. These tests assert the properties the harness actually depends on, and
in particular the ones whose failure would be silent: that an unevaluated gate
never becomes a pass, that a candidate cannot reach the oracle, and that an
empty or skipped comparison fails instead of reporting success.

Run with:

    python3 -m unittest discover -s harness -p 'test_*.py'
"""

from __future__ import annotations

import json
from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from aisl_harness import comparators, gates, loop, plugins, verify
from aisl_harness.contracts import (
    BuildResult,
    CandidateOutput,
    Context,
    ExperimentPlugin,
    ReferenceOutput,
    Workload,
)
from aisl_harness.core import HarnessError, sha256_tree


class TrustBoundaryTest(unittest.TestCase):
    def test_candidate_view_drops_oracle_access(self):
        context = Context(
            experiment_id="x",
            workload=Workload("w", "role", "exact-bytes"),
            work_dir=Path("/tmp"),
            output_dir=Path("/tmp"),
            oracle_dir=Path("/tmp/oracle"),
        )
        self.assertIsNotNone(context.oracle_dir)
        self.assertIsNone(context.candidate_view().oracle_dir)

    def test_candidate_view_is_a_copy(self):
        context = Context("x", None, Path("/tmp"), Path("/tmp"), oracle_dir=Path("/o"))
        view = context.candidate_view()
        view.settings["injected"] = True
        self.assertNotIn("injected", context.settings)


class ComparatorTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp())
        self.reference = self.tmp / "reference"
        self.candidate = self.tmp / "candidate"
        self.reference.mkdir()
        self.candidate.mkdir()

    def test_empty_reference_fails_rather_than_passes(self):
        (self.candidate / "a.bin").write_bytes(b"anything")
        result = comparators.compare_exact_bytes(self.reference, self.candidate, {})
        self.assertFalse(result.ok, "a comparison with nothing to compare must fail")

    def test_identical_bytes_pass(self):
        (self.reference / "a.bin").write_bytes(b"payload")
        (self.candidate / "a.bin").write_bytes(b"payload")
        self.assertTrue(comparators.compare_exact_bytes(self.reference, self.candidate, {}).ok)

    def test_missing_candidate_artifact_fails(self):
        (self.reference / "a.bin").write_bytes(b"payload")
        result = comparators.compare_exact_bytes(self.reference, self.candidate, {})
        self.assertFalse(result.ok)
        self.assertEqual(result.mismatches[0]["reason"], "missing from candidate output")

    def _write_vectors(self, directory: Path, vectors: list[dict]):
        (directory / "vectors.json").write_text(json.dumps({"vectors": vectors}))

    def test_vectors_matched_by_id_not_position(self):
        self._write_vectors(self.reference, [{"id": "a", "v": 1}, {"id": "b", "v": 2}])
        self._write_vectors(self.candidate, [{"id": "b", "v": 2}, {"id": "a", "v": 1}])
        self.assertTrue(comparators.compare_vectors(self.reference, self.candidate, {}).ok)

    def test_vectors_detect_dropped_case(self):
        self._write_vectors(self.reference, [{"id": "a", "v": 1}, {"id": "b", "v": 2}])
        self._write_vectors(self.candidate, [{"id": "a", "v": 1}])
        result = comparators.compare_vectors(self.reference, self.candidate, {})
        self.assertFalse(result.ok)
        self.assertEqual(result.mismatches[0]["vector"], "b")

    def test_vectors_detect_duplicate_case(self):
        self._write_vectors(self.reference, [{"id": "a", "v": 1}])
        self._write_vectors(self.candidate, [{"id": "a", "v": 1}, {"id": "a", "v": 1}])
        result = comparators.compare_vectors(self.reference, self.candidate, {})
        self.assertFalse(result.ok)

    def test_vectors_detect_field_difference(self):
        self._write_vectors(self.reference, [{"id": "a", "tag": "aa"}])
        self._write_vectors(self.candidate, [{"id": "a", "tag": "ab"}])
        self.assertFalse(comparators.compare_vectors(self.reference, self.candidate, {}).ok)

    def test_missing_vector_file_raises_rather_than_skipping(self):
        self._write_vectors(self.reference, [{"id": "a", "v": 1}])
        with self.assertRaises(HarnessError):
            comparators.compare_vectors(self.reference, self.candidate, {})

    def test_determinism_detects_differing_repeats(self):
        first = self.tmp / "run0"
        second = self.tmp / "run1"
        first.mkdir()
        second.mkdir()
        (first / "out").write_bytes(b"same")
        (second / "out").write_bytes(b"different")
        self.assertFalse(comparators.compare_repeats([first, second]).ok)

    def test_determinism_accepts_identical_repeats(self):
        first = self.tmp / "run0"
        second = self.tmp / "run1"
        first.mkdir()
        second.mkdir()
        (first / "out").write_bytes(b"same")
        (second / "out").write_bytes(b"same")
        self.assertTrue(comparators.compare_repeats([first, second]).ok)

    def test_single_execution_reports_determinism_untested(self):
        only = self.tmp / "run0"
        only.mkdir()
        result = comparators.compare_repeats([only])
        self.assertTrue(result.ok)
        self.assertIn("not exercised", result.details["note"])


SPECIFICATION = {
    "experiment_id": "fake",
    "gates": [
        {
            "id": "g-all-mapped",
            "criteria": ["criterion one", "criterion two"],
        },
        {
            "id": "g-partly-mapped",
            "criteria": ["criterion one", "criterion unmapped"],
        },
    ],
    "phases": [
        {"id": "p1", "order": 1, "exit_criteria": []},
        {"id": "p2", "order": 2, "exit_criteria": []},
    ],
}

MANIFEST = {
    "gates": {
        "g-all-mapped": {
            "criteria": [
                {"criterion": "criterion one", "checks": ["suite:a"]},
                {"criterion": "criterion two", "checks": ["suite:b"]},
            ]
        },
        "g-partly-mapped": {
            "criteria": [
                {"criterion": "criterion one", "checks": ["suite:a"]},
                {"criterion": "criterion unmapped", "checks": []},
            ]
        },
    },
    "phase_gates": {"p1": ["g-all-mapped"], "p2": ["g-partly-mapped"]},
}


class GateTest(unittest.TestCase):
    def setUp(self):
        self._original = gates.load_specification
        gates.load_specification = lambda experiment_id: SPECIFICATION

    def tearDown(self):
        gates.load_specification = self._original

    def _evaluate(self, checks):
        report = {"run_id": "r", "checks": checks}
        return gates.evaluate("fake", MANIFEST, report)

    def test_all_checks_passing_passes_the_gate(self):
        evaluation = self._evaluate(
            [{"id": "suite:a", "status": "pass"}, {"id": "suite:b", "status": "pass"}]
        )
        gate = next(g for g in evaluation["gates"] if g["gate_id"] == "g-all-mapped")
        self.assertEqual(gate["status"], "pass")

    def test_one_failing_check_fails_the_gate(self):
        evaluation = self._evaluate(
            [{"id": "suite:a", "status": "pass"}, {"id": "suite:b", "status": "fail"}]
        )
        gate = next(g for g in evaluation["gates"] if g["gate_id"] == "g-all-mapped")
        self.assertEqual(gate["status"], "fail")

    def test_unmapped_criterion_leaves_gate_unevaluated_not_passed(self):
        evaluation = self._evaluate([{"id": "suite:a", "status": "pass"}])
        gate = next(g for g in evaluation["gates"] if g["gate_id"] == "g-partly-mapped")
        self.assertEqual(gate["status"], "unevaluated")
        self.assertNotEqual(gate["status"], "pass")

    def test_check_that_never_ran_leaves_gate_unevaluated(self):
        evaluation = self._evaluate([{"id": "suite:a", "status": "pass"}])
        gate = next(g for g in evaluation["gates"] if g["gate_id"] == "g-all-mapped")
        self.assertEqual(gate["status"], "unevaluated")
        criterion = next(c for c in gate["criteria"] if c["criterion"] == "criterion two")
        self.assertEqual(criterion["checks"]["suite:b"], "not-run")

    def test_unevaluated_check_does_not_pass_a_criterion(self):
        evaluation = self._evaluate(
            [{"id": "suite:a", "status": "pass"}, {"id": "suite:b", "status": "unevaluated"}]
        )
        gate = next(g for g in evaluation["gates"] if g["gate_id"] == "g-all-mapped")
        self.assertEqual(gate["status"], "unevaluated")

    def test_phase_status_follows_its_gates(self):
        evaluation = self._evaluate(
            [{"id": "suite:a", "status": "pass"}, {"id": "suite:b", "status": "pass"}]
        )
        phases = gates.phase_status("fake", MANIFEST, evaluation)
        self.assertEqual(phases[0]["status"], "pass")
        self.assertEqual(phases[1]["status"], "unevaluated")


class ApprovalTest(unittest.TestCase):
    def test_changed_evidence_invalidates_an_approval(self):
        state = {
            "approvals": [
                {"phase_id": "p1", "report_digest": "old", "active": True},
                {"phase_id": "p2", "report_digest": "new", "active": True},
            ]
        }
        for approval in state["approvals"]:
            if approval["report_digest"] != "new":
                approval["active"] = False
        self.assertEqual(loop.approved_phases(state), {"p2"})

    def test_report_digest_ignores_timing_but_tracks_checks(self):
        base = {"candidate": {"a": 1}, "checks": [{"id": "x", "status": "pass"}],
                "git": {"commit": "abc"}}
        slower = dict(base, wall_seconds=99.0)
        changed = dict(base, checks=[{"id": "x", "status": "fail"}])
        self.assertEqual(loop.report_digest(base), loop.report_digest(slower))
        self.assertNotEqual(loop.report_digest(base), loop.report_digest(changed))


class StubPlugin(ExperimentPlugin):
    experiment_id = "stub"

    def describe(self):
        return {"design": "stub"}

    def workloads(self):
        return [Workload("known", "role", "vectors")]

    def build(self, context):
        return BuildResult(ok=True)

    def reference(self, context):
        return ReferenceOutput(directory=context.output_dir, digest="")

    def execute(self, context):
        return CandidateOutput(directory=context.output_dir, digest="", ok=True)


class WiringTest(unittest.TestCase):
    def test_suite_naming_an_unknown_workload_is_an_error(self):
        manifest = {"suites": [{"workload": "does-not-exist"}]}
        with self.assertRaises(HarnessError):
            plugins.suite_workloads(manifest, StubPlugin())

    def test_declared_suite_resolves_to_the_plugin_workload(self):
        manifest = {"suites": [{"workload": "known"}]}
        selected = plugins.suite_workloads(manifest, StubPlugin())
        self.assertEqual([w.id for w in selected], ["known"])


class StimulusIdentityTest(unittest.TestCase):
    """A cached oracle must not survive a change to the stimulus behind it."""

    def test_default_identity_is_none_not_a_fake_digest(self):
        # None means "cannot tell", which the runner records honestly. A plugin
        # that invented a constant digest would claim a freshness it cannot
        # verify, which is worse than admitting the gap.
        self.assertIsNone(StubPlugin().stimulus_identity(Workload("known", "r", "vectors")))

    def test_identity_tracks_the_stimulus(self):
        class Fingerprinted(StubPlugin):
            payload = "a"

            def stimulus_identity(self, workload):
                return self.payload

        plugin = Fingerprinted()
        first = plugin.stimulus_identity(Workload("known", "r", "vectors"))
        plugin.payload = "b"
        second = plugin.stimulus_identity(Workload("known", "r", "vectors"))
        self.assertNotEqual(first, second)


class ProtectedRootTest(unittest.TestCase):
    def test_harness_refuses_to_write_into_protected_roots(self):
        from aisl_harness.core import ROOT, assert_not_protected

        for protected in ("lab", "ground_truth"):
            with self.assertRaises(HarnessError):
                assert_not_protected(ROOT / protected / "anything")

    def test_workspace_paths_are_allowed(self):
        from aisl_harness.core import ROOT, assert_not_protected

        assert_not_protected(ROOT / "workspace" / "anything")


if __name__ == "__main__":
    unittest.main()
