#!/usr/bin/env python3
"""Gate evaluation.

`experiment.json` states gate criteria in prose, because a criterion is a
commitment to a human reader. `harness.json` maps each criterion to the check
IDs that would demonstrate it. This module joins the two against a verification
report.

The mapping is deliberately incapable of manufacturing a pass. A criterion with
no mapped checks, or whose checks did not run, is `unevaluated`. An unevaluated
criterion makes its gate unevaluated, never passed. Only a criterion whose every
mapped check actually passed can pass.
"""

from __future__ import annotations

from typing import Any

from .core import ROOT, HarnessError, read_json


PASS = "pass"
FAIL = "fail"
UNEVALUATED = "unevaluated"


def load_specification(experiment_id: str) -> dict[str, Any]:
    path = ROOT / "experiments" / experiment_id / "experiment.json"
    if not path.is_file():
        raise HarnessError(f"experiment {experiment_id!r} has no experiment.json")
    return read_json(path)


def _criterion_text(criterion: Any) -> str:
    if isinstance(criterion, str):
        return criterion
    if isinstance(criterion, dict) and isinstance(criterion.get("text"), str):
        return criterion["text"]
    raise HarnessError(f"unsupported gate criterion shape: {criterion!r}")


def _mapping(manifest: dict[str, Any], gate_id: str) -> dict[str, list[str]]:
    """criterion text -> mapped check IDs, from harness.json."""
    gates = manifest.get("gates")
    if not isinstance(gates, dict):
        raise HarnessError("harness.json: gates must be an object")
    entry = gates.get(gate_id)
    if entry is None:
        return {}
    criteria = entry.get("criteria") if isinstance(entry, dict) else None
    if not isinstance(criteria, list):
        raise HarnessError(f"harness.json: gates.{gate_id}.criteria must be a list")
    mapping: dict[str, list[str]] = {}
    for index, item in enumerate(criteria):
        if not isinstance(item, dict):
            raise HarnessError(f"harness.json: gates.{gate_id}.criteria[{index}] must be an object")
        text = item.get("criterion")
        checks = item.get("checks", [])
        if not isinstance(text, str) or not isinstance(checks, list):
            raise HarnessError(
                f"harness.json: gates.{gate_id}.criteria[{index}] needs "
                f"a string 'criterion' and a list 'checks'"
            )
        mapping[text] = [str(check) for check in checks]
    return mapping


def evaluate(
    experiment_id: str, manifest: dict[str, Any], report: dict[str, Any]
) -> dict[str, Any]:
    specification = load_specification(experiment_id)
    results = {check["id"]: check["status"] for check in report.get("checks", [])}

    gates: list[dict[str, Any]] = []
    for gate in specification.get("gates", []):
        gate_id = gate.get("id")
        mapping = _mapping(manifest, gate_id)
        criteria: list[dict[str, Any]] = []
        for raw in gate.get("criteria", []):
            text = _criterion_text(raw)
            check_ids = mapping.get(text, [])
            observed = {check_id: results.get(check_id, "not-run") for check_id in check_ids}
            if not check_ids:
                status = UNEVALUATED
                reason = "no checks are mapped to this criterion"
            elif any(value == FAIL for value in observed.values()):
                status = FAIL
                reason = "a mapped check failed"
            elif all(value == PASS for value in observed.values()):
                status = PASS
                reason = "every mapped check passed"
            else:
                status = UNEVALUATED
                reason = "a mapped check did not produce a result"
            criteria.append(
                {
                    "criterion": text,
                    "status": status,
                    "reason": reason,
                    "checks": observed,
                }
            )

        statuses = [item["status"] for item in criteria]
        if not criteria:
            gate_status = UNEVALUATED
        elif FAIL in statuses:
            gate_status = FAIL
        elif UNEVALUATED in statuses:
            gate_status = UNEVALUATED
        else:
            gate_status = PASS
        gates.append(
            {
                "gate_id": gate_id,
                "status": gate_status,
                "criteria": criteria,
                "summary": {
                    "pass": statuses.count(PASS),
                    "fail": statuses.count(FAIL),
                    "unevaluated": statuses.count(UNEVALUATED),
                },
            }
        )

    return {
        "experiment_id": experiment_id,
        "run_id": report.get("run_id"),
        "gates": gates,
        "passed": [g["gate_id"] for g in gates if g["status"] == PASS],
        "failed": [g["gate_id"] for g in gates if g["status"] == FAIL],
        "unevaluated": [g["gate_id"] for g in gates if g["status"] == UNEVALUATED],
    }


def phase_status(
    experiment_id: str, manifest: dict[str, Any], evaluation: dict[str, Any]
) -> list[dict[str, Any]]:
    """Map experiment phases onto gate results via harness.json `phase_gates`."""
    specification = load_specification(experiment_id)
    phase_gates = manifest.get("phase_gates", {})
    by_gate = {gate["gate_id"]: gate["status"] for gate in evaluation["gates"]}
    phases: list[dict[str, Any]] = []
    for phase in sorted(specification.get("phases", []), key=lambda p: p.get("order", 0)):
        gate_ids = phase_gates.get(phase.get("id"), [])
        statuses = [by_gate.get(gate_id, "not-run") for gate_id in gate_ids]
        if not gate_ids:
            status = UNEVALUATED
        elif FAIL in statuses:
            status = FAIL
        elif all(value == PASS for value in statuses):
            status = PASS
        else:
            status = UNEVALUATED
        phases.append(
            {
                "phase_id": phase.get("id"),
                "order": phase.get("order"),
                "status": status,
                "gates": dict(zip(gate_ids, statuses)),
                "exit_criteria": phase.get("exit_criteria", []),
            }
        )
    return phases
