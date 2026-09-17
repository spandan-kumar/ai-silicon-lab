#!/usr/bin/env python3
"""Exhaustively classify one operand-pair partition of XOR completion."""

from __future__ import annotations

import argparse
import hashlib
import itertools
import json
import re
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path


RESULT_RE = re.compile(r"^RESULT status=(sat|unsat|timeout)\b", re.MULTILINE)


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def parse_pair(text: str) -> tuple[int, int]:
    pieces = text.split(",")
    if len(pieces) != 2:
        raise argparse.ArgumentTypeError("expected LEFT,RIGHT")
    left, right = (int(piece) for piece in pieces)
    if left < 0 or right < 0 or left == right:
        raise argparse.ArgumentTypeError("operands must be distinct nonnegative integers")
    return min(left, right), max(left, right)


def parse_pin(text: str) -> tuple[int, int, int]:
    pieces = text.split(",")
    if len(pieces) != 3:
        raise argparse.ArgumentTypeError("expected STEP,LEFT,RIGHT")
    step, left, right = (int(piece) for piece in pieces)
    if step < 0 or left < 0 or right < 0 or left == right:
        raise argparse.ArgumentTypeError("pin values must be nonnegative and operands distinct")
    return step, min(left, right), max(left, right)


def restricted_sources(problem: Path, source_indices: str) -> tuple[int, str]:
    available = sum(
        line.startswith("SOURCE ") for line in problem.read_text().splitlines()
    )
    indices = (
        [int(piece) for piece in source_indices.split(",")]
        if source_indices
        else list(range(available))
    )
    if len(set(indices)) != len(indices) or any(
        index < 0 or index >= available for index in indices
    ):
        raise ValueError("source restriction has duplicate or out-of-range indices")
    return len(indices), ",".join(str(index) for index in indices)


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(json.dumps(value, indent=2) + "\n")
    temporary.replace(path)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--solver", type=Path, required=True)
    parser.add_argument("--problem", type=Path, required=True)
    parser.add_argument("--steps", type=int, required=True)
    parser.add_argument("--conflict-limit", type=int, required=True)
    parser.add_argument("--target-mode", default="none")
    parser.add_argument("--source-indices", default="")
    parser.add_argument("--last-operands", type=parse_pair)
    parser.add_argument("--pin", action="append", type=parse_pin, default=[])
    parser.add_argument("--enumerate-step", type=int, required=True)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument(
        "--pairs-from",
        type=Path,
        help="classify only timeout pairs from an earlier v1 report",
    )
    parser.add_argument(
        "--resume-from",
        type=Path,
        help="resume a partial v1 report by classifying its missing pairs",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    solver = args.solver.resolve()
    problem = args.problem.resolve()
    if args.steps <= 0 or args.conflict_limit <= 0:
        raise ValueError("steps and conflict limit must be positive")
    if not 0 <= args.enumerate_step < args.steps:
        raise ValueError("enumerated step is out of range")
    if args.enumerate_step == args.steps - 1 and args.last_operands:
        raise ValueError("cannot both fix and enumerate the final step")
    if args.enumerate_step != args.steps - 1 and not args.last_operands:
        raise ValueError("a final-step pair is required when enumerating another step")
    pinned_steps = [step for step, _, _ in args.pin]
    if len(set(pinned_steps)) != len(pinned_steps):
        raise ValueError("a step may be pinned only once")
    if args.enumerate_step in pinned_steps:
        raise ValueError("cannot both fix and enumerate the same step")
    if args.pairs_from and args.resume_from:
        raise ValueError("--pairs-from and --resume-from are mutually exclusive")

    source_count, effective_source_indices = restricted_sources(
        problem, args.source_indices
    )
    operand_count = source_count + args.enumerate_step
    all_pairs = list(itertools.combinations(range(operand_count), 2))
    prior = None
    if args.pairs_from or args.resume_from:
        prior_path = args.pairs_from or args.resume_from
        assert prior_path is not None
        prior = json.loads(prior_path.read_text())
        if prior.get("schema") != "xor-completion-branch-classification-v1":
            raise ValueError("pairs-from input has an unsupported schema")
        prior_pairs = [
            tuple(branch["enumerated_operands"])
            for branch in prior["branches"]
        ]
        if len(set(prior_pairs)) != len(prior_pairs) or any(
            pair not in all_pairs for pair in prior_pairs
        ):
            raise ValueError("prior report has duplicate or invalid operand pairs")
        if args.pairs_from:
            pairs = [
                tuple(branch["enumerated_operands"])
                for branch in prior["branches"]
                if branch["status"] == "timeout"
            ]
            if not pairs:
                raise ValueError("pairs-from input has no valid timeout pairs")
        else:
            prior_pair_set = set(prior_pairs)
            pairs = [pair for pair in all_pairs if pair not in prior_pair_set]
            if not pairs:
                raise ValueError("resume input has no missing operand pairs")
    else:
        pairs = all_pairs
    common = [
        str(solver),
        str(problem),
        str(args.steps),
        str(args.conflict_limit),
        args.target_mode,
        effective_source_indices,
    ]
    branches: list[dict[str, object]] = list(prior["branches"]) if args.resume_from else []
    started_at = datetime.now(timezone.utc).isoformat()
    study_start = time.monotonic()
    solver_digest = sha256(solver)
    problem_digest = sha256(problem)
    pair_selection = (
        {
            "kind": "timeouts_from_report",
            "path": str(args.pairs_from.resolve()),
            "sha256": sha256(args.pairs_from),
        }
        if args.pairs_from
        else (
            {
                "kind": "resume_missing_from_report",
                "path": str(args.resume_from.resolve()),
                "sha256": sha256(args.resume_from),
            }
            if args.resume_from
            else {"kind": "all_pairs"}
        )
    )

    def make_report(finished: bool) -> dict[str, object]:
        counts = {
            status: sum(branch["status"] == status for branch in branches)
            for status in ("sat", "unsat", "timeout", "error")
        }
        return {
            "schema": "xor-completion-branch-classification-v1",
            "started_at_utc": started_at,
            "finished_at_utc": (
                datetime.now(timezone.utc).isoformat() if finished else None
            ),
            "solver": str(solver),
            "solver_sha256": solver_digest,
            "problem": str(problem),
            "problem_sha256": problem_digest,
            "parameters": {
                "steps": args.steps,
                "conflict_limit": args.conflict_limit,
                "target_mode": args.target_mode,
                "source_indices": [
                    int(piece) for piece in effective_source_indices.split(",")
                ],
                "last_operands": (
                    list(args.last_operands) if args.last_operands else None
                ),
                "fixed_step_operands": [list(pin) for pin in args.pin],
                "enumerated_step": args.enumerate_step,
                "operand_count": operand_count,
                "theoretical_pair_count": len(all_pairs),
                "pair_selection": pair_selection,
            },
            "complete": (
                finished
                and len(branches) == (len(all_pairs) if args.resume_from else len(pairs))
                and counts["error"] == 0
            ),
            "counts": counts,
            "elapsed_seconds": round(time.monotonic() - study_start, 6),
            "branches": branches,
        }

    for ordinal, pair in enumerate(pairs):
        final_pair = pair if args.enumerate_step == args.steps - 1 else args.last_operands
        assert final_pair is not None
        pins = list(args.pin)
        if args.enumerate_step != args.steps - 1:
            pins.append((args.enumerate_step, pair[0], pair[1]))
        command = common + [f"{final_pair[0]},{final_pair[1]}"] + [
            f"{step},{left},{right}" for step, left, right in pins
        ]
        start = time.monotonic()
        process = subprocess.run(command, capture_output=True, text=True, check=False)
        elapsed = time.monotonic() - start
        match = RESULT_RE.search(process.stdout)
        status = match.group(1) if match else "error"
        if status == "sat" and process.returncode != 0:
            status = "error"
        if status in {"unsat", "timeout"} and process.returncode != 1:
            status = "error"
        branch = {
            "ordinal": len(branches),
            "enumerated_operands": list(pair),
            "status": status,
            "exit_code": process.returncode,
            "elapsed_seconds": round(elapsed, 6),
        }
        if status in {"sat", "error"}:
            branch["stdout"] = process.stdout.splitlines()
        if process.stderr:
            branch["stderr"] = process.stderr.splitlines()
        branches.append(branch)
        write_json(args.output, make_report(False))
        if not args.quiet:
            print(
                f"branch={ordinal + 1}/{len(pairs)} operands={pair[0]},{pair[1]} "
                f"status={status} elapsed_seconds={elapsed:.3f}",
                flush=True,
            )
        if status == "sat":
            break

    report = make_report(True)
    write_json(args.output, report)
    report_counts = report["counts"]
    assert isinstance(report_counts, dict)
    print(
        "RESULT "
        + " ".join(f"{key}={value}" for key, value in report_counts.items()),
        flush=True,
    )
    if report_counts["error"]:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
