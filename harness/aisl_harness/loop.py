#!/usr/bin/env python3
"""The phase-gated autonomous research loop.

The agent works freely inside a phase. At a phase boundary the loop stops and
states what it measured, which gates that satisfies, and what remains
unevaluated. Advancing past a boundary requires an explicit approval that is
recorded with the evidence it was granted against.

Two properties make the stop meaningful:

* A phase can only be *offered* for approval when its gates actually passed.
  Approving a phase whose gates failed or went unevaluated requires an explicit
  override that is recorded as such in the state file.
* Approval is bound to the run ID and report digest it was granted for. Later
  changes to the candidate invalidate it, so a stale approval cannot carry a
  new design past a gate it never faced.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from . import gates, plugins, provenance, verify
from .core import (
    ROOT,
    STATE_ROOT,
    HarnessError,
    read_json,
    relative,
    sha256_bytes,
    utc_now,
    write_json,
)


def state_path(experiment_id: str) -> Path:
    return STATE_ROOT / experiment_id / "loop-state.json"


def load_state(experiment_id: str) -> dict[str, Any]:
    path = state_path(experiment_id)
    if not path.is_file():
        return {
            "schema_version": 1,
            "experiment_id": experiment_id,
            "created_utc": utc_now(),
            "approvals": [],
            "history": [],
            "last_run_id": None,
        }
    return read_json(path)


def save_state(experiment_id: str, state: dict[str, Any]) -> Path:
    state["updated_utc"] = utc_now()
    path = state_path(experiment_id)
    write_json(path, state)
    return path


def report_digest(report: dict[str, Any]) -> str:
    """Identity of the evidence an approval was granted against."""
    import json

    material = {
        "candidate": report.get("candidate"),
        "checks": report.get("checks"),
        "git": report.get("git", {}).get("commit"),
    }
    return sha256_bytes(json.dumps(material, sort_keys=True).encode("utf-8"))


def approved_phases(state: dict[str, Any]) -> set[str]:
    return {
        approval["phase_id"]
        for approval in state.get("approvals", [])
        if approval.get("active", True)
    }


def current_phase(phases: list[dict[str, Any]], state: dict[str, Any]) -> dict[str, Any] | None:
    """The first phase that has not been approved."""
    approved = approved_phases(state)
    for phase in phases:
        if phase["phase_id"] not in approved:
            return phase
    return None


def step(
    experiment_id: str,
    *,
    only: list[str] | None = None,
    refresh_oracle: bool = False,
    skip_build: bool = False,
    emit_record: bool = True,
) -> dict[str, Any]:
    """Run one iteration: verify, evaluate gates, record, then stop at the boundary."""
    manifest = plugins.load_manifest(experiment_id)
    state = load_state(experiment_id)

    report = verify.run(
        experiment_id,
        only=only,
        refresh_oracle=refresh_oracle,
        skip_build=skip_build,
    )
    evaluation = gates.evaluate(experiment_id, manifest, report)
    phases = gates.phase_status(experiment_id, manifest, evaluation)
    phase = current_phase(phases, state)

    record_path: str | None = None
    if emit_record:
        record = provenance.build_record(experiment_id, report, evaluation)
        target = provenance.emit(record)
        validation = provenance.validate(target)
        record_path = relative(target)
        if validation.get("exit_code") != 0:
            raise HarnessError(
                "emitted run record failed the repository validator:\n"
                + (validation.get("stdout") or "")
                + (validation.get("stderr") or "")
            )

    digest = report_digest(report)
    # An approval granted against different evidence no longer applies.
    for approval in state.get("approvals", []):
        if approval.get("report_digest") != digest:
            approval["active"] = False
            approval.setdefault("invalidated_utc", utc_now())
            approval.setdefault("invalidated_reason", "candidate evidence changed")

    phase = current_phase(phases, state)
    blocked_on = None
    if phase is not None:
        if phase["status"] == "pass":
            blocked_on = "awaiting approval"
        elif phase["status"] == "fail":
            blocked_on = "gate failure"
        else:
            blocked_on = "unevaluated gate criteria"

    entry = {
        "utc": utc_now(),
        "run_id": report.get("run_id"),
        "report_digest": digest,
        "verification_ok": report.get("ok"),
        "summary": report.get("summary"),
        "gates": {gate["gate_id"]: gate["status"] for gate in evaluation["gates"]},
        "phase": phase["phase_id"] if phase else None,
        "phase_status": phase["status"] if phase else "all-phases-approved",
        "record_path": record_path,
    }
    state["history"].append(entry)
    state["last_run_id"] = report.get("run_id")
    state["last_report_digest"] = digest
    state["last_report_path"] = report.get("report_path")
    save_state(experiment_id, state)

    return {
        "experiment_id": experiment_id,
        "run_id": report.get("run_id"),
        "report": report,
        "evaluation": evaluation,
        "phases": phases,
        "phase": phase,
        "blocked_on": blocked_on,
        "record_path": record_path,
        "report_digest": digest,
        "state_path": relative(state_path(experiment_id)),
    }


def approve(
    experiment_id: str,
    phase_id: str,
    *,
    approver: str,
    note: str = "",
    override: bool = False,
) -> dict[str, Any]:
    """Record human approval to cross a phase boundary."""
    manifest = plugins.load_manifest(experiment_id)
    state = load_state(experiment_id)
    if not state.get("last_run_id"):
        raise HarnessError("no verification run to approve; run `harness/aisl loop step` first")

    report_path = ROOT / state["last_report_path"]
    report = read_json(report_path)
    evaluation = gates.evaluate(experiment_id, manifest, report)
    phases = gates.phase_status(experiment_id, manifest, evaluation)
    match = next((phase for phase in phases if phase["phase_id"] == phase_id), None)
    if match is None:
        known = ", ".join(phase["phase_id"] for phase in phases)
        raise HarnessError(f"unknown phase {phase_id!r}; known phases: {known}")

    if match["status"] != "pass" and not override:
        raise HarnessError(
            f"phase {phase_id!r} is {match['status']}, not passed. "
            f"Gates: {match['gates']}. Re-run the loop, or pass --override to record "
            f"a deliberate approval over unmet evidence."
        )

    approval = {
        "phase_id": phase_id,
        "approved_utc": utc_now(),
        "approver": approver,
        "note": note,
        "run_id": state["last_run_id"],
        "report_digest": state.get("last_report_digest"),
        "phase_status_at_approval": match["status"],
        "gates_at_approval": match["gates"],
        "override": bool(override),
        "active": True,
    }
    state["approvals"] = [
        existing for existing in state.get("approvals", []) if existing["phase_id"] != phase_id
    ]
    state["approvals"].append(approval)
    save_state(experiment_id, state)
    return approval


def status(experiment_id: str) -> dict[str, Any]:
    manifest = plugins.load_manifest(experiment_id)
    state = load_state(experiment_id)
    if not state.get("last_report_path"):
        return {
            "experiment_id": experiment_id,
            "phases": [],
            "state": state,
            "note": "no verification run yet",
        }
    report = read_json(ROOT / state["last_report_path"])
    evaluation = gates.evaluate(experiment_id, manifest, report)
    phases = gates.phase_status(experiment_id, manifest, evaluation)
    return {
        "experiment_id": experiment_id,
        "last_run_id": state.get("last_run_id"),
        "evaluation": evaluation,
        "phases": phases,
        "approvals": state.get("approvals", []),
        "phase": current_phase(phases, state),
        "state": state,
    }
