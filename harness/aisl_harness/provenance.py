#!/usr/bin/env python3
"""Run-record emission.

The repository's provenance rule is that experiment, agent, and implementation
identities stay separate, and that every number carries how it was obtained.
This module builds records mechanically from a verification report so the
measured half is never retyped by hand, and leaves the agent half explicitly
`null` with a source note unless a caller supplies real telemetry.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from .core import (
    ROOT,
    HarnessError,
    read_json,
    relative,
    run,
    tool_version,
    utc_now,
    write_json,
)


RECORD_ROOT = ROOT / "results" / "run-records"

# Agent identity the harness can state about itself without guessing. Anything
# the runtime does not expose stays null with a source note rather than
# becoming an invented measurement.
AGENT_ENV = {
    "provider": "AISL_AGENT_PROVIDER",
    "display_name": "AISL_AGENT_DISPLAY_NAME",
    "canonical_id": "AISL_AGENT_CANONICAL_ID",
    "harness_name": "AISL_AGENT_HARNESS",
    "harness_version": "AISL_AGENT_HARNESS_VERSION",
    "reasoning_effort": "AISL_AGENT_REASONING_EFFORT",
    "reasoning_mode": "AISL_AGENT_REASONING_MODE",
}


def _env(key: str) -> str | None:
    value = os.environ.get(AGENT_ENV[key])
    return value.strip() or None if value else None


def _agent_block() -> dict[str, Any]:
    canonical = _env("canonical_id")
    display = _env("display_name")
    if canonical:
        identity_status = "exact"
    elif display:
        identity_status = "alias-only"
    else:
        identity_status = "unknown"
    return {
        "model": {
            "provider": _env("provider"),
            "display_name": display,
            "canonical_id": canonical,
            "identity_status": identity_status,
        },
        "harness": {
            "name": _env("harness_name"),
            "version": _env("harness_version"),
            "environment": "ai-silicon-lab harness",
        },
        "reasoning": {
            "effort": _env("reasoning_effort"),
            "mode": _env("reasoning_mode"),
            "context": None,
        },
        "goal_sha256": None,
        "instruction_hashes": instruction_hashes(),
        "subagents": [],
    }


def instruction_hashes() -> list[dict[str, Any]]:
    """Hash the public instruction files, never their private counterparts."""
    from .core import sha256_file

    hashes = []
    for name in ("AGENTS.md", "LAB.md", "EVALUATION.md"):
        path = ROOT / name
        if path.is_file():
            hashes.append({"path": name, "sha256": sha256_file(path)})
    return hashes


def experiment_revision(experiment_id: str) -> Any:
    path = ROOT / "experiments" / experiment_id / "experiment.json"
    if not path.is_file():
        raise HarnessError(f"experiment {experiment_id!r} has no experiment.json")
    specification = read_json(path)
    return specification.get("revision", specification.get("schema_version", 1))


def _measured_time(report: dict[str, Any]) -> dict[str, Any]:
    build = report.get("build", {})
    build_seconds = sum(
        command.get("wall_seconds", 0.0)
        for command in build.get("commands", [])
        if isinstance(command, dict)
    ) or None
    simulation_seconds = sum(
        workload.get("wall_seconds", 0.0) for workload in report.get("workloads", [])
    ) or None
    return {
        "started_at": report.get("created_utc"),
        "finished_at": utc_now(),
        # Agent wall time is a different measurement from execution time and is
        # only present when the runtime reports it.
        "agent_wall_seconds": None,
        "build_seconds": round(build_seconds, 6) if build_seconds else None,
        "simulation_seconds": round(simulation_seconds, 6) if simulation_seconds else None,
        "hardware_seconds": None,
        "human_seconds": None,
        "source": "measured",
        "notes": (
            "build_seconds and simulation_seconds are measured by the harness. "
            "agent_wall_seconds, hardware_seconds, and human_seconds are unavailable "
            "from this runtime and are null rather than zero."
        ),
    }


def _tool_versions(report: dict[str, Any], extra: list[str]) -> dict[str, Any]:
    names = {"python3", "git"}
    names.update(extra)
    for tool in report.get("build", {}).get("tools", []):
        if isinstance(tool, dict) and isinstance(tool.get("name"), str):
            names.add(tool["name"])
    return {name: tool_version(name).get("version") for name in sorted(names)}


def build_record(
    experiment_id: str,
    report: dict[str, Any],
    evaluation: dict[str, Any],
    *,
    run_id: str | None = None,
    result_status: str | None = None,
    notes: str = "",
) -> dict[str, Any]:
    git = report.get("git", {})
    gate_status = {gate["gate_id"]: gate["status"] for gate in evaluation.get("gates", [])}

    if report.get("ok") is True:
        status = "pass"
    elif report.get("ok") is False:
        status = "fail"
    else:
        status = "draft"

    evidence: list[dict[str, Any]] = [
        {
            "kind": "verification-report",
            "path": report.get("report_path"),
            "description": (
                f"Harness verification report with {report.get('summary', {}).get('pass', 0)} passing, "
                f"{report.get('summary', {}).get('fail', 0)} failing, and "
                f"{report.get('summary', {}).get('unevaluated', 0)} unevaluated checks."
            ),
        }
    ]
    for workload in report.get("workloads", []):
        evidence.append(
            {
                "kind": "workload-comparison",
                "path": workload.get("output_directory"),
                "description": (
                    f"{workload['workload_id']}: {workload['comparison']['comparator']} comparison "
                    f"over {workload['comparison']['checked']} items, "
                    f"result {'pass' if workload['ok'] else 'fail'}."
                ),
            }
        )
    evidence.append(
        {
            "kind": "gate-evaluation",
            "path": None,
            "description": (
                "Gate status: "
                + ", ".join(f"{k}={v}" for k, v in gate_status.items())
                + ". Unevaluated gates are not passes."
            ),
        }
    )

    return {
        "schema_version": 1,
        "record_type": "experiment-run",
        "run_id": run_id or report.get("run_id"),
        "experiment_id": experiment_id,
        "experiment_revision": experiment_revision(experiment_id),
        "status": status,
        "measurement_status": "mixed",
        "agent": _agent_block(),
        "usage": {
            "input_tokens": None,
            "cached_input_tokens": None,
            "cache_write_tokens": None,
            "output_tokens": None,
            "reasoning_tokens": None,
            "total_tokens": None,
            "source": "unavailable",
            "precision": None,
            "notes": (
                "This harness does not receive model token telemetry. Supply it from "
                "the agent runtime rather than inferring it from wall time."
            ),
        },
        "time": _measured_time(report),
        "cost": {
            "amount": None,
            "currency": "USD",
            "source": "unavailable",
            "rate_date": None,
            "notes": "No pinned rate source; cost is not inferred from token counts.",
        },
        "execution": {
            "candidate_commit": git.get("commit"),
            "worktree_clean": git.get("clean"),
            "harness_run_ids": [report.get("run_id")],
            "lab_run_ids": [],
            "tool_versions": _tool_versions(report, []),
            "artifact_paths": [
                path for path in [report.get("report_path")] if isinstance(path, str)
            ],
            "candidate": report.get("candidate", {}),
        },
        "result": {
            "status": result_status or ("verification-pass" if status == "pass" else status),
            "claim_level": "harness-measured",
            "gates": gate_status,
            "unevaluated_gates": evaluation.get("unevaluated", []),
            "notes": notes
            or (
                "Measured by the AI Silicon Lab harness. Gate results marked unevaluated "
                "have no supporting checks and must not be read as passes."
            ),
        },
        "evidence": evidence,
    }


def emit(record: dict[str, Any], path: Path | None = None) -> Path:
    target = path or (RECORD_ROOT / f"{record['run_id']}.json")
    write_json(target, record)
    return target


def validate(path: Path) -> dict[str, Any]:
    """Validate against the repository's own dependency-free validator."""
    return run(["./tools/experiment", "validate-run", relative(path)], timeout=120)
