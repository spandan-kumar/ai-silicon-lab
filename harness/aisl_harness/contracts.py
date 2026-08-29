#!/usr/bin/env python3
"""The experiment plugin contract.

`lab/evaluate` is a Doom-specific judge and stays that way. This module states
the same shape in an experiment-agnostic form so a new experiment can supply its
own reference, candidate, and workloads without weakening a trusted benchmark.

The separation that matters is structural, not advisory: the harness calls
`reference()` and `execute()` with different contexts. The candidate context
carries no oracle path, so a candidate cannot read expected results even by
accident, and the comparison happens in the harness after the candidate exits.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class Workload:
    """One deterministic stimulus with a declared comparison method."""

    id: str
    role: str
    comparator: str
    description: str = ""
    # Free-form, plugin-interpreted stimulus parameters. Recorded verbatim in
    # the verification report so a run can be regenerated from it.
    parameters: dict[str, Any] = field(default_factory=dict)
    # Determinism requirement: how many independent candidate executions must
    # produce byte-identical output. 1 disables the repeat check.
    repeat: int = 1
    timeout_seconds: float | None = None


@dataclass
class BuildResult:
    """What a build produced, with hashes so the artifact identity is pinned."""

    ok: bool
    commands: list[dict[str, Any]] = field(default_factory=list)
    artifacts: dict[str, str] = field(default_factory=dict)
    tools: list[dict[str, Any]] = field(default_factory=list)
    notes: str = ""


@dataclass
class ReferenceOutput:
    """Independent expected results for one workload.

    `directory` holds the produced artifacts. `digest` pins them. `metadata`
    records the reference identity — source revision, vector corpus, and the
    fact that it is independent of the candidate.
    """

    directory: Path
    digest: str
    metadata: dict[str, Any] = field(default_factory=dict)
    commands: list[dict[str, Any]] = field(default_factory=list)


@dataclass
class CandidateOutput:
    """What the design under test produced for one workload."""

    directory: Path
    digest: str
    ok: bool
    commands: list[dict[str, Any]] = field(default_factory=list)
    # Candidate self-reported values. Recorded, never trusted as measurements.
    reported: dict[str, Any] = field(default_factory=dict)
    # Values the harness measured about the run itself.
    measured: dict[str, Any] = field(default_factory=dict)


@dataclass
class Comparison:
    """The verdict for one workload, always with the evidence behind it."""

    ok: bool
    comparator: str
    checked: int = 0
    mismatches: list[dict[str, Any]] = field(default_factory=list)
    details: dict[str, Any] = field(default_factory=dict)


@dataclass
class Context:
    """Paths and settings handed to a plugin for one operation.

    `oracle_dir` is populated only for reference generation. It is `None` for
    every candidate execution; that absence is the enforced trust boundary.
    """

    experiment_id: str
    workload: Workload | None
    work_dir: Path
    output_dir: Path
    oracle_dir: Path | None = None
    env: dict[str, str] = field(default_factory=dict)
    settings: dict[str, Any] = field(default_factory=dict)

    def candidate_view(self) -> "Context":
        """A copy with no oracle access, for handing to the design under test."""
        return Context(
            experiment_id=self.experiment_id,
            workload=self.workload,
            work_dir=self.work_dir,
            output_dir=self.output_dir,
            oracle_dir=None,
            env=dict(self.env),
            settings=dict(self.settings),
        )


class ExperimentPlugin:
    """Base class an experiment implements to join the autonomous loop.

    Every method may raise; the harness records the failure as evidence rather
    than converting it into a skip. A plugin that cannot measure something
    returns `None` for that value and says why in its metadata.
    """

    experiment_id: str = ""

    def describe(self) -> dict[str, Any]:
        """Identity of this candidate: design, tools, sources, revisions."""
        raise NotImplementedError

    def workloads(self) -> list[Workload]:
        """The deterministic stimuli this plugin can run."""
        raise NotImplementedError

    def build(self, context: Context) -> BuildResult:
        """Build the candidate. Returns ok=False with commands on failure."""
        raise NotImplementedError

    def reference(self, context: Context) -> ReferenceOutput:
        """Produce independent expected results for `context.workload`."""
        raise NotImplementedError

    def execute(self, context: Context) -> CandidateOutput:
        """Run the design under test. `context.oracle_dir` is always None."""
        raise NotImplementedError

    # Optional hooks. The default implementations report "not provided" rather
    # than silently passing, so a gate that depends on them stays unevaluated.

    def lint(self, context: Context) -> dict[str, Any] | None:
        return None

    def synthesize(self, context: Context) -> dict[str, Any] | None:
        return None

    def policy_checks(self, context: Context) -> list[dict[str, Any]]:
        """Experiment-specific forbidden-shortcut checks."""
        return []
