#!/usr/bin/env python3
"""The experiment-agnostic verification runner.

One pass produces a `verification-report.json` that later stages consume: the
gate evaluator reads its check results, and the provenance recorder reads its
measurements and artifact hashes. Nothing downstream re-derives a verdict.
"""

from __future__ import annotations

from pathlib import Path
import shutil
from typing import Any

from . import comparators, plugins
from .contracts import CandidateOutput, Comparison, Context, ExperimentPlugin, Workload
from .core import (
    HarnessError,
    ROOT,
    STATE_ROOT,
    assert_not_protected,
    git_state,
    relative,
    sha256_tree,
    time_monotonic,
    utc_now,
    write_json,
)


def _prepare(directory: Path) -> Path:
    assert_not_protected(directory)
    if directory.exists():
        shutil.rmtree(directory)
    directory.mkdir(parents=True)
    return directory


def _check(check_id: str, ok: bool | None, detail: dict[str, Any]) -> dict[str, Any]:
    """A single named check.

    `ok=None` means unevaluated. It is never coerced to a pass; a gate that
    depends on an unevaluated check stays unevaluated too.
    """
    return {
        "id": check_id,
        "status": "unevaluated" if ok is None else ("pass" if ok else "fail"),
        "detail": detail,
    }


def _comparison_dict(comparison: Comparison) -> dict[str, Any]:
    return {
        "ok": comparison.ok,
        "comparator": comparison.comparator,
        "checked": comparison.checked,
        "mismatches": comparison.mismatches,
        "details": comparison.details,
    }


def _oracle_cache(experiment_id: str, workload: Workload) -> Path:
    return STATE_ROOT / experiment_id / "oracles" / workload.id


def run_workload(
    plugin: ExperimentPlugin,
    workload: Workload,
    suite: dict[str, Any],
    run_root: Path,
    refresh_oracle: bool,
) -> dict[str, Any]:
    workload_root = _prepare(run_root / "workloads" / workload.id)
    checks: list[dict[str, Any]] = []
    started = time_monotonic()

    # --- Reference side. Only this side is allowed to see the oracle. --------
    oracle_dir = _oracle_cache(plugin.experiment_id, workload)
    reference_meta: dict[str, Any] = {}
    reference_commands: list[dict[str, Any]] = []

    # A cached oracle is only usable while the stimulus behind it is unchanged.
    # Without this the runner compares new candidate output against an old
    # reference: it manufactured four failures the first time the RV32I stimulus
    # grew, and the same mechanism could just as easily hide a real divergence.
    fingerprint = plugin.stimulus_identity(workload)
    marker = oracle_dir / ".stimulus-identity"
    stale = False
    if fingerprint is not None and oracle_dir.is_dir():
        previous = marker.read_text(encoding="utf-8").strip() if marker.is_file() else None
        stale = previous != fingerprint

    cached = (oracle_dir.is_dir() and any(oracle_dir.iterdir())
              and not refresh_oracle and not stale)
    if cached:
        reference_meta = {"cached": True, "directory": relative(oracle_dir),
                          "staleness_detectable": fingerprint is not None}
    else:
        _prepare(oracle_dir)
        context = Context(
            experiment_id=plugin.experiment_id,
            workload=workload,
            work_dir=workload_root / "reference-work",
            output_dir=oracle_dir,
            oracle_dir=oracle_dir,
            settings=suite.get("settings", {}),
        )
        context.work_dir.mkdir(parents=True, exist_ok=True)
        reference = plugin.reference(context)
        reference_meta = {"cached": False, "regenerated_because":
                          "stimulus changed" if stale else
                          ("requested" if refresh_oracle else "no cached oracle"),
                          "staleness_detectable": fingerprint is not None,
                          **reference.metadata}
        reference_commands = reference.commands
        if fingerprint is not None:
            marker.write_text(fingerprint + "\n", encoding="utf-8")
    reference_digest = sha256_tree(oracle_dir)
    reference_meta["digest"] = reference_digest
    reference_meta["directory"] = relative(oracle_dir)
    reference_files = sum(1 for path in oracle_dir.rglob("*") if path.is_file())
    checks.append(
        _check(
            f"reference:{workload.id}",
            reference_files > 0,
            {"artifacts": reference_files, "digest": reference_digest},
        )
    )

    # --- Candidate side. No oracle path is reachable from this context. ------
    executions: list[CandidateOutput] = []
    execution_dirs: list[Path] = []
    repeats = max(1, workload.repeat)
    for attempt in range(repeats):
        output_dir = _prepare(workload_root / f"execution-{attempt}")
        context = Context(
            experiment_id=plugin.experiment_id,
            workload=workload,
            work_dir=workload_root / f"execution-work-{attempt}",
            output_dir=output_dir,
            oracle_dir=oracle_dir,
            settings=suite.get("settings", {}),
        ).candidate_view()
        if context.oracle_dir is not None:  # structural invariant, asserted at runtime
            raise HarnessError("internal error: candidate context retained oracle access")
        context.work_dir.mkdir(parents=True, exist_ok=True)
        executions.append(plugin.execute(context))
        execution_dirs.append(output_dir)

    ran_ok = all(execution.ok for execution in executions)
    checks.append(
        _check(
            f"execute:{workload.id}",
            ran_ok,
            {
                "executions": len(executions),
                "failed": [i for i, e in enumerate(executions) if not e.ok],
            },
        )
    )

    determinism = comparators.compare_repeats(execution_dirs)
    if repeats > 1:
        checks.append(
            _check(f"determinism:{workload.id}", determinism.ok, determinism.details)
        )

    # --- Comparison happens only after the candidate has exited. ------------
    comparison = comparators.get(workload.comparator)(
        oracle_dir, execution_dirs[0], suite.get("comparator_options", {})
    )
    checks.append(
        _check(
            f"suite:{workload.id}",
            comparison.ok and ran_ok,
            {"comparator": comparison.comparator, **comparison.details},
        )
    )

    return {
        "workload_id": workload.id,
        "role": workload.role,
        "comparator": workload.comparator,
        "parameters": workload.parameters,
        "repeat": repeats,
        "ok": comparison.ok and ran_ok and determinism.ok and reference_files > 0,
        "reference": reference_meta,
        "reference_commands": reference_commands,
        "candidate": {
            "digest": sha256_tree(execution_dirs[0]),
            "ok": ran_ok,
            "reported": executions[0].reported,
            "measured": executions[0].measured,
            "commands": executions[0].commands,
        },
        "comparison": _comparison_dict(comparison),
        "determinism": _comparison_dict(determinism),
        "checks": checks,
        "wall_seconds": round(time_monotonic() - started, 6),
        "output_directory": relative(workload_root),
    }


def run(
    experiment_id: str,
    *,
    run_id: str | None = None,
    only: list[str] | None = None,
    refresh_oracle: bool = False,
    skip_build: bool = False,
) -> dict[str, Any]:
    manifest = plugins.load_manifest(experiment_id)
    plugin = plugins.load_plugin(experiment_id, manifest)
    plugins.suite_workloads(manifest, plugin)  # validates the wiring before any work

    run_id = run_id or f"verify-{utc_now().replace(':', '').replace('-', '')}"
    run_root = _prepare(STATE_ROOT / experiment_id / "runs" / run_id)
    started = time_monotonic()

    report: dict[str, Any] = {
        "schema_version": 1,
        "report_type": "verification",
        "experiment_id": experiment_id,
        "run_id": run_id,
        "created_utc": utc_now(),
        "git": git_state(),
        "candidate": plugin.describe(),
        "checks": [],
        "workloads": [],
    }

    # --- Build -------------------------------------------------------------
    if skip_build:
        report["build"] = {"skipped": True}
        report["checks"].append(_check("build", None, {"reason": "build skipped by request"}))
    else:
        build_context = Context(
            experiment_id=experiment_id,
            workload=None,
            work_dir=run_root / "build",
            output_dir=run_root / "build",
            settings=manifest.get("settings", {}),
        )
        build_context.work_dir.mkdir(parents=True, exist_ok=True)
        build = plugin.build(build_context)
        report["build"] = {
            "ok": build.ok,
            "artifacts": build.artifacts,
            "tools": build.tools,
            "commands": build.commands,
            "notes": build.notes,
        }
        report["checks"].append(_check("build", build.ok, {"artifacts": len(build.artifacts)}))
        if not build.ok:
            report["ok"] = False
            report["wall_seconds"] = round(time_monotonic() - started, 6)
            write_json(run_root / "verification-report.json", report)
            report["report_path"] = relative(run_root / "verification-report.json")
            return report

    # --- Optional lint and synthesis hooks ---------------------------------
    for name, hook in (("lint", plugin.lint), ("synthesize", plugin.synthesize)):
        context = Context(
            experiment_id=experiment_id,
            workload=None,
            work_dir=run_root / name,
            output_dir=run_root / name,
            settings=manifest.get("settings", {}),
        )
        context.work_dir.mkdir(parents=True, exist_ok=True)
        outcome = hook(context)
        if outcome is None:
            report["checks"].append(
                _check(f"tool:{name}", None, {"reason": "plugin provides no result"})
            )
        else:
            report[name] = outcome
            report["checks"].append(_check(f"tool:{name}", bool(outcome.get("ok")), outcome))

    # --- Workloads ---------------------------------------------------------
    selected = {suite["workload"]: suite for suite in manifest["suites"]}
    for workload in plugin.workloads():
        if workload.id not in selected:
            continue
        if only and workload.id not in only:
            continue
        result = run_workload(
            plugin, workload, selected[workload.id], run_root, refresh_oracle
        )
        report["workloads"].append(result)
        report["checks"].extend(result["checks"])

    # --- Policy checks -----------------------------------------------------
    policy_context = Context(
        experiment_id=experiment_id,
        workload=None,
        work_dir=run_root / "policy",
        output_dir=run_root / "policy",
        settings=manifest.get("settings", {}),
    )
    policy_context.work_dir.mkdir(parents=True, exist_ok=True)
    for policy in plugin.policy_checks(policy_context):
        report["checks"].append(
            _check(
                f"policy:{policy['id']}",
                policy.get("ok"),
                {k: v for k, v in policy.items() if k not in ("id", "ok")},
            )
        )

    statuses = [check["status"] for check in report["checks"]]
    report["ok"] = "fail" not in statuses
    report["summary"] = {
        "pass": statuses.count("pass"),
        "fail": statuses.count("fail"),
        "unevaluated": statuses.count("unevaluated"),
        "workloads": len(report["workloads"]),
    }
    report["wall_seconds"] = round(time_monotonic() - started, 6)
    report_path = run_root / "verification-report.json"
    write_json(report_path, report)
    report["report_path"] = relative(report_path)
    return report
