#!/usr/bin/env python3
"""Command-line entry point for the autonomous research harness."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Any

from . import environment, gates, loop, plugins, provenance, verify
from .core import ROOT, HarnessError, read_json, relative


PASS_MARK = "[PASS]"
FAIL_MARK = "[FAIL]"
OPEN_MARK = "[ ?? ]"


def mark(status: str) -> str:
    return {"pass": PASS_MARK, "fail": FAIL_MARK}.get(status, OPEN_MARK)


def emit(value: Any, as_json: bool) -> None:
    if as_json:
        json.dump(value, sys.stdout, indent=2, sort_keys=True)
        sys.stdout.write("\n")


def cmd_experiments(args: argparse.Namespace) -> int:
    wired = plugins.available()
    registry = read_json(ROOT / "experiments" / "registry.json")
    rows = []
    for entry in registry.get("experiments", []):
        experiment_id = entry.get("experiment_id")
        rows.append(
            {
                "experiment_id": experiment_id,
                "status": entry.get("status"),
                "title": entry.get("title"),
                "harness_wired": experiment_id in wired,
            }
        )
    if args.json:
        emit(rows, True)
        return 0
    for row in rows:
        wiring = "wired" if row["harness_wired"] else "not-wired"
        print(f"{row['experiment_id']}\t{row['status']}\t{wiring}\t{row['title']}")
    return 0


def cmd_env(args: argparse.Namespace) -> int:
    result = environment.check(args.experiment)
    if args.json:
        emit(result, True)
        return 0 if result["ok"] else 1
    scope = args.experiment or "laboratory defaults"
    print(f"Toolchain for {scope}")
    for tool in result["tools"]:
        required = tool["name"] in result["required"]
        if tool["available"]:
            print(f"{PASS_MARK} {tool['name']}: {tool['version']}")
        elif required:
            print(f"{FAIL_MARK} {tool['name']}: required, unavailable")
        else:
            print(f"{OPEN_MARK} {tool['name']}: optional, unavailable")
    if result["hints"]:
        print("\nInstall hints:")
        for name, hint in sorted(result["hints"].items()):
            print(f"  {name}: {hint}")
    if args.record:
        print(f"\nrecorded: {environment.record(args.experiment)}")
    return 0 if result["ok"] else 1


def _print_report(report: dict[str, Any]) -> None:
    print(f"experiment: {report['experiment_id']}  run: {report['run_id']}")
    build = report.get("build", {})
    if build.get("skipped"):
        print(f"{OPEN_MARK} build: skipped by request")
    for check in report.get("checks", []):
        detail = check.get("detail", {})
        summary = ", ".join(
            f"{key}={value}"
            for key, value in detail.items()
            if isinstance(value, (str, int, float, bool)) and key != "reason"
        )
        reason = detail.get("reason")
        text = summary or reason or ""
        print(f"{mark(check['status'])} {check['id']}{': ' + text if text else ''}")
    summary = report.get("summary", {})
    print(
        f"\n{summary.get('pass', 0)} passed, {summary.get('fail', 0)} failed, "
        f"{summary.get('unevaluated', 0)} unevaluated"
    )
    if report.get("report_path"):
        print(f"report: {report['report_path']}")


def cmd_verify(args: argparse.Namespace) -> int:
    report = verify.run(
        args.experiment,
        run_id=args.run_id,
        only=args.only,
        refresh_oracle=args.refresh_oracle,
        skip_build=args.skip_build,
    )
    if args.json:
        emit(report, True)
    else:
        _print_report(report)
    return 0 if report.get("ok") else 1


def _print_gates(evaluation: dict[str, Any], phases: list[dict[str, Any]]) -> None:
    print("Gates")
    for gate in evaluation["gates"]:
        print(f"{mark(gate['status'])} {gate['gate_id']}")
        for criterion in gate["criteria"]:
            print(f"    {mark(criterion['status'])} {criterion['criterion']}")
            if criterion["status"] != "pass":
                print(f"        {criterion['reason']}")
                for check_id, state in criterion["checks"].items():
                    print(f"        - {check_id}: {state}")
    print("\nPhases")
    for phase in phases:
        print(f"{mark(phase['status'])} {phase['order']}. {phase['phase_id']}")


def cmd_gate(args: argparse.Namespace) -> int:
    manifest = plugins.load_manifest(args.experiment)
    state = loop.load_state(args.experiment)
    if args.report:
        report = read_json(Path(args.report))
    elif state.get("last_report_path"):
        report = read_json(ROOT / state["last_report_path"])
    else:
        raise HarnessError("no verification report available; run `verify` first")
    evaluation = gates.evaluate(args.experiment, manifest, report)
    phases = gates.phase_status(args.experiment, manifest, evaluation)
    if args.json:
        emit({"evaluation": evaluation, "phases": phases}, True)
    else:
        _print_gates(evaluation, phases)
    return 0 if not evaluation["failed"] else 1


def cmd_record(args: argparse.Namespace) -> int:
    manifest = plugins.load_manifest(args.experiment)
    state = loop.load_state(args.experiment)
    path = Path(args.report) if args.report else ROOT / (state.get("last_report_path") or "")
    if not path.is_file():
        raise HarnessError("no verification report available; run `verify` first")
    report = read_json(path)
    report.setdefault("report_path", relative(path))
    evaluation = gates.evaluate(args.experiment, manifest, report)
    record = provenance.build_record(args.experiment, report, evaluation, run_id=args.run_id)
    target = provenance.emit(record)
    validation = provenance.validate(target)
    ok = validation.get("exit_code") == 0
    if args.json:
        emit({"record_path": relative(target), "validated": ok, "validation": validation}, True)
    else:
        print(f"{mark('pass' if ok else 'fail')} run record: {relative(target)}")
        print((validation.get("stdout") or "").strip())
        if not ok:
            print((validation.get("stderr") or "").strip())
    return 0 if ok else 1


def cmd_loop(args: argparse.Namespace) -> int:
    if args.loop_command == "status":
        result = loop.status(args.experiment)
        if args.json:
            emit(result, True)
            return 0
        if result.get("note"):
            print(f"{OPEN_MARK} {args.experiment}: {result['note']}")
            return 0
        _print_gates(result["evaluation"], result["phases"])
        print("\nApprovals")
        for approval in result["approvals"]:
            state = "active" if approval.get("active", True) else "invalidated"
            flag = " (override)" if approval.get("override") else ""
            print(f"  {approval['phase_id']}: {state}{flag} by {approval['approver']}")
        phase = result.get("phase")
        print(f"\ncurrent phase: {phase['phase_id'] if phase else 'all phases approved'}")
        return 0

    if args.loop_command == "step":
        result = loop.step(
            args.experiment,
            only=args.only,
            refresh_oracle=args.refresh_oracle,
            skip_build=args.skip_build,
        )
        if args.json:
            emit(
                {
                    key: value
                    for key, value in result.items()
                    if key != "report"
                },
                True,
            )
            return 0 if result["report"].get("ok") else 1
        _print_report(result["report"])
        print()
        _print_gates(result["evaluation"], result["phases"])
        phase = result.get("phase")
        print()
        if phase is None:
            print("all phases approved; nothing is blocking")
        else:
            print(f"stopped at phase boundary: {phase['phase_id']} ({phase['status']})")
            print(f"blocked on: {result['blocked_on']}")
            if phase["status"] == "pass":
                print(
                    f"approve with: ./harness/aisl loop approve {args.experiment} "
                    f"{phase['phase_id']} --approver NAME"
                )
        if result.get("record_path"):
            print(f"run record: {result['record_path']}")
        return 0 if result["report"].get("ok") else 1

    if args.loop_command == "approve":
        approval = loop.approve(
            args.experiment,
            args.phase,
            approver=args.approver,
            note=args.note,
            override=args.override,
        )
        if args.json:
            emit(approval, True)
        else:
            print(f"{PASS_MARK} approved {approval['phase_id']} by {approval['approver']}")
            if approval["override"]:
                print(
                    f"{FAIL_MARK} recorded as an override over "
                    f"{approval['phase_status_at_approval']} evidence"
                )
        return 0

    raise HarnessError(f"unknown loop command {args.loop_command!r}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="harness/aisl",
        description="Autonomous hardware design, simulation, and verification harness.",
    )
    parser.add_argument("--json", action="store_true", help="machine-readable output")
    sub = parser.add_subparsers(dest="command", required=True)

    experiments = sub.add_parser("experiments", help="list experiments and harness wiring")
    experiments.set_defaults(func=cmd_experiments)

    env = sub.add_parser("env", help="check the toolchain an experiment declares")
    env.add_argument("experiment", nargs="?")
    env.add_argument("--record", action="store_true", help="write an environment snapshot")
    env.set_defaults(func=cmd_env)

    verify_cmd = sub.add_parser("verify", help="run an experiment's verification suites")
    verify_cmd.add_argument("experiment")
    verify_cmd.add_argument("--run-id")
    verify_cmd.add_argument("--only", nargs="*", help="limit to these workload IDs")
    verify_cmd.add_argument("--refresh-oracle", action="store_true")
    verify_cmd.add_argument("--skip-build", action="store_true")
    verify_cmd.set_defaults(func=cmd_verify)

    gate = sub.add_parser("gate", help="evaluate gates against a verification report")
    gate.add_argument("experiment")
    gate.add_argument("--report", help="path to a verification-report.json")
    gate.set_defaults(func=cmd_gate)

    record = sub.add_parser("record", help="emit and validate a provenance run record")
    record.add_argument("experiment")
    record.add_argument("--report")
    record.add_argument("--run-id")
    record.set_defaults(func=cmd_record)

    loop_cmd = sub.add_parser("loop", help="the phase-gated autonomous loop")
    loop_sub = loop_cmd.add_subparsers(dest="loop_command", required=True)

    loop_status = loop_sub.add_parser("status", help="where the experiment stands")
    loop_status.add_argument("experiment")

    loop_step = loop_sub.add_parser("step", help="verify, evaluate, record, stop at the boundary")
    loop_step.add_argument("experiment")
    loop_step.add_argument("--only", nargs="*")
    loop_step.add_argument("--refresh-oracle", action="store_true")
    loop_step.add_argument("--skip-build", action="store_true")

    loop_approve = loop_sub.add_parser("approve", help="record approval to cross a boundary")
    loop_approve.add_argument("experiment")
    loop_approve.add_argument("phase")
    loop_approve.add_argument("--approver", required=True)
    loop_approve.add_argument("--note", default="")
    loop_approve.add_argument(
        "--override",
        action="store_true",
        help="approve despite failed or unevaluated gates; recorded as an override",
    )
    loop_cmd.set_defaults(func=cmd_loop)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.func(args)
    except HarnessError as exc:
        print(f"{FAIL_MARK} {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
