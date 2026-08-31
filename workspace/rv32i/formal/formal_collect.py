#!/usr/bin/env python3
"""Collect riscv-formal results into a machine-readable summary.

riscv-formal writes one directory per check with a status file. This reads
them and reports what was proven, what failed, and -- the part that matters
most for honesty -- what never ran. A check that was not executed is reported
as such and never counted as a pass.

Bounded model checking proves that no counterexample exists within the depth
each check was configured for. That is a much stronger statement than a
passing test corpus, and it is still not an unbounded proof. The depth is
reported alongside the result so the claim can be read with its own limits
attached.
"""

from __future__ import annotations

import json
from pathlib import Path
import re
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[3]
CHECKS = ROOT / "temp" / "riscv-formal" / "cores" / "aisl_rv32i" / "checks"


# Properties that are false by design rather than by defect. Each entry needs a
# reason that can be checked against the source, and the check is still run and
# still reported -- it is excluded from the verdict, not from the output.
# Silently deleting a failing obligation and silently excusing one look the same
# in a summary; only the written reason distinguishes them.
INAPPLICABLE = {
    "liveness_ch0":
        "Liveness asserts that another instruction always eventually retires. "
        "This core has no trap handler and no mtvec: it halts permanently on "
        "ECALL, EBREAK, an illegal instruction, or a misaligned access. A "
        "solver that supplies an illegal instruction therefore reaches a state "
        "with no successor, which is the specified behaviour of a bare RV32I "
        "core with no privileged architecture. Implementing traps that resume "
        "would make this property applicable.",
}


def read_depth(sby_path: Path) -> int | None:
    try:
        text = sby_path.read_text(encoding="utf-8")
    except OSError:
        return None
    match = re.search(r"^depth\s+(\d+)", text, re.MULTILINE)
    return int(match.group(1)) if match else None


def collect(checks_dir: Path = CHECKS) -> dict[str, Any]:
    if not checks_dir.is_dir():
        return {"status": "unavailable",
                "reason": f"{checks_dir} absent; run workspace/rv32i/formal/run",
                "checks": 0}

    results: list[dict[str, Any]] = []
    for sby in sorted(checks_dir.glob("*.sby")):
        name = sby.stem
        status_file = checks_dir / name / "status"
        if status_file.is_file():
            raw = status_file.read_text(encoding="utf-8").strip().split()
            status = raw[0].lower() if raw else "unknown"
        else:
            status = "not-run"
        entry = {"check": name, "status": status, "depth": read_depth(sby)}
        if name in INAPPLICABLE:
            entry["inapplicable_reason"] = INAPPLICABLE[name]
        results.append(entry)

    applicable = [r for r in results if r["check"] not in INAPPLICABLE]
    passed = [r for r in applicable if r["status"] == "pass"]
    failed = [r for r in applicable if r["status"] == "fail"]
    other = [r for r in applicable if r["status"] not in ("pass", "fail")]

    # Group by what each family of checks establishes.
    families: dict[str, dict[str, int]] = {}
    for entry in results:
        family = "insn" if entry["check"].startswith("insn_") else \
            entry["check"].split("_")[0]
        bucket = families.setdefault(family, {"pass": 0, "fail": 0, "other": 0})
        key = entry["status"] if entry["status"] in ("pass", "fail") else "other"
        bucket[key] += 1

    return {
        "status": "pass" if failed == [] and other == [] and passed else
                  ("fail" if failed else "incomplete"),
        "checks": len(results),
        "applicable": len(applicable),
        "inapplicable": [
            {"check": r["check"], "status": r["status"],
             "reason": r.get("inapplicable_reason")}
            for r in results if r["check"] in INAPPLICABLE
        ],
        "passed": len(passed),
        "failed": len(failed),
        "not_run": len(other),
        "failed_checks": [r["check"] for r in failed],
        "not_run_checks": [r["check"] for r in other][:10],
        "families": families,
        "instructions_proven": sorted(
            r["check"][len("insn_"):].rsplit("_ch", 1)[0]
            for r in passed if r["check"].startswith("insn_")),
        "claim": "Bounded model checking: no counterexample exists within each "
                 "check's configured depth. Not an unbounded proof.",
        "results": results,
    }


if __name__ == "__main__":
    summary = collect()
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
    raise SystemExit(0 if summary["status"] == "pass" else 1)
