#!/usr/bin/env python3
"""Retain targeted RTL, repeatability, mapping, and mapped-netlist evidence."""

from __future__ import annotations

import argparse
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import time
import traceback

from run_asic_synthesis import CONSTRAINTS, DEFAULT_LIBERTY
from run_synthesis import ALL_CONFIGURATIONS
from verify_mapped_netlist import HARNESS_DEFINES


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> str:
    return str(path.relative_to(REPOSITORY))


def write_json(path: Path, value: object) -> None:
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n")


def git(*arguments: str) -> str:
    return subprocess.run(
        ["git", *arguments], cwd=REPOSITORY, check=True, capture_output=True, text=True
    ).stdout.strip()


def run_command(
    directory: Path, phase: str, argv: list[str], commands: list[dict],
    architecture: str | None = None,
) -> dict:
    stdout_path = directory / f"{phase}.stdout.log"
    stderr_path = directory / f"{phase}.stderr.log"
    began = time.monotonic()
    with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
        try:
            exit_code = subprocess.run(argv, cwd=ROOT, stdout=stdout, stderr=stderr).returncode
        except OSError as error:
            stderr.write(f"{error}\n".encode())
            exit_code = 127
    entry = {
        "architecture": architecture,
        "phase": phase,
        "argv": argv,
        "cwd": relative(ROOT),
        "exit_code": exit_code,
        "elapsed_seconds": round(time.monotonic() - began, 6),
        "stdout": relative(stdout_path),
        "stderr": relative(stderr_path),
        "stdout_sha256": sha256(stdout_path),
        "stderr_sha256": sha256(stderr_path),
    }
    commands.append(entry)
    write_json(directory / "commands.json", commands)
    print(
        f"{architecture or 'evaluator'} {phase}: "
        f"{'PASS' if exit_code == 0 else 'FAIL'} "
        f"elapsed_seconds={entry['elapsed_seconds']:.3f}", flush=True,
    )
    if exit_code != 0:
        raise RuntimeError(f"{phase} exited {exit_code}; see {relative(stderr_path)}")
    return entry


def evaluate_architecture(name: str, build_root: Path, run_root: Path) -> dict:
    config = ALL_CONFIGURATIONS[name]
    stem = str(config["stem"])
    build = build_root / stem
    evidence = run_root / stem
    build.mkdir()
    evidence.mkdir()
    commands: list[dict] = []
    result = {"architecture": name, "arch_parameter": config["arch"], "status": "fail"}
    try:
        with tempfile.TemporaryDirectory(prefix="aisl-exploration-", dir="/tmp") as temporary:
            temp = Path(temporary)
            for filename in ("gcm_harness.cpp", "gcm_vectors.h"):
                shutil.copy2(ROOT / "tests" / filename, temp / filename)
            define = HARNESS_DEFINES[name]
            cflags = f"-D{define} -O3" if define else "-O3"
            run_command(evidence, "rtl-build", [
                "verilator", "--cc", "--exe", "--build", "--sv", "-Wall", "-Irtl",
                "--Mdir", str(temp / "obj"), "--top-module", "aes_gcm_core",
                f"-GARCH={config['arch']}", "-CFLAGS", cflags,
                "-MAKEFLAGS", "OPT_FAST=-O3 OPT_GLOBAL=-O3",
                *config["sources"], str(temp / "gcm_harness.cpp"),
            ], commands, name)
            binary = build / "Vaes_gcm_core"
            shutil.copy2(temp / "obj" / "Vaes_gcm_core", binary)
        result["rtl_binary_sha256"] = sha256(binary)
        expected = re.compile(
            rf"^GCM RTL: PASS architecture={re.escape(name)} corpus_operations=1038(?:\s|$)",
            re.MULTILINE,
        )
        for repeat in (1, 2):
            run_command(evidence, f"rtl-run-{repeat}", [str(binary)], commands, name)
            output = evidence / f"rtl-run-{repeat}.stdout.log"
            if not expected.search(output.read_text()):
                raise RuntimeError(f"RTL run {repeat} lacks the complete corpus PASS result")
        first_output = (evidence / "rtl-run-1.stdout.log").read_bytes()
        if first_output != (evidence / "rtl-run-2.stdout.log").read_bytes():
            raise RuntimeError("RTL repeated stdout is not byte-identical")
        result["rtl_repeatability"] = {
            "status": "pass", "runs": 2, "comparison": "byte-identical-stdout",
            "corpus_operations_per_run": 1038,
            "stdout_sha256": hashlib.sha256(first_output).hexdigest(),
        }
        for phase, script in (
            ("generic-synthesis", "run_synthesis.py"),
            ("asic-synthesis", "run_asic_synthesis.py"),
        ):
            run_command(evidence, phase, [
                sys.executable, str(ROOT / "tools" / script),
                "--architecture", name, "--output-dir", str(build / phase),
            ], commands, name)
            result[phase] = json.loads((build / phase / "summary.json").read_text())
        run_command(evidence, "gate-compile-and-test", [
            sys.executable, str(ROOT / "tools" / "verify_mapped_netlist.py"),
            "--architecture", name, "--synthesis-dir", str(build / "asic-synthesis"),
            "--output-dir", str(build / "gate-verification"),
        ], commands, name)
        gate_summary = json.loads((build / "gate-verification" / "summary.json").read_text())
        gate_output = (build / "gate-verification" / f"gcm-{stem}.txt").read_bytes()
        if gate_summary["status"] != "pass" or gate_output != first_output:
            raise RuntimeError("mapped-netlist stdout does not match RTL stdout byte-for-byte")
        result["mapped_netlist_verification"] = gate_summary
        result["rtl_matches_mapped_stdout"] = True
        result["status"] = "pass"
    except Exception as error:
        result["error"] = str(error)
        (evidence / "failure.log").write_text(traceback.format_exc())
        print(f"{name}: FAIL {error}", flush=True)
    finally:
        # Retain partial flow output too: failed synthesis is useful evidence.
        for phase in ("generic-synthesis", "asic-synthesis", "gate-verification"):
            if (build / phase).exists():
                shutil.copytree(build / phase, evidence / phase)
        result["commands"] = commands
        write_json(evidence / "result.json", result)
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-id", required=True)
    parser.add_argument("--architecture", action="append", choices=ALL_CONFIGURATIONS, required=True)
    parser.add_argument("--allow-dirty", action="store_true")
    parser.add_argument("--jobs", type=int, default=1, help="concurrent architectures (default: 1)")
    args = parser.parse_args()
    if not re.fullmatch(r"[a-z0-9][a-z0-9._-]*", args.run_id):
        parser.error("run ID must use lowercase letters, digits, dot, underscore, or dash")
    if args.jobs < 1:
        parser.error("--jobs must be positive")
    selected = list(dict.fromkeys(args.architecture))
    jobs = min(args.jobs, len(selected), os.cpu_count() or 1)
    dirty_before = bool(git("status", "--porcelain", "--untracked-files=normal"))
    if dirty_before and not args.allow_dirty:
        raise SystemExit("refusing exploration evaluation from a dirty worktree; commit or use --allow-dirty")
    candidate_commit = git("rev-parse", "HEAD")
    run_root = REPOSITORY / "runs" / args.run_id
    build_root = ROOT / "build" / "exploration" / args.run_id
    for directory in (run_root, build_root):
        if directory.exists():
            raise SystemExit(f"refusing to overwrite existing evidence: {directory}")

    sources = {
        REPOSITORY / "experiments" / "aes-256-gcm" / "experiment.json",
        REPOSITORY / "experiments" / "aes-256-gcm" / "profile.json",
        REPOSITORY / "tools" / "experiment", REPOSITORY / "tools" / "experiment_registry.py",
        ROOT / "tests" / "gcm_harness.cpp", ROOT / "tests" / "gcm_vectors.h",
        ROOT / "rtl" / "aes_functions.svh", CONSTRAINTS, DEFAULT_LIBERTY,
        ROOT / "vectors" / "nist_subset.json", ROOT / "vectors" / "generated.json",
        ROOT / "reference" / "aes_gcm.py",
        ROOT / "third_party" / "nangate45" / "SOURCE.md",
        *(ROOT / "tools" / filename for filename in (
            "evaluate_exploration.py", "run_synthesis.py", "run_asic_synthesis.py",
            "verify_mapped_netlist.py", "fetch_nangate45.py", "generate_harness_vectors.py",
        )),
        *(ROOT / filename for name in selected for filename in ALL_CONFIGURATIONS[name]["sources"]),
    }
    instructions = REPOSITORY / "AGENTS.md"
    if instructions.exists():
        sources.add(instructions)
    # Take source fingerprints before any compilation or synthesis begins.
    source_hashes = {relative(path): sha256(path) for path in sorted(sources)}
    run_root.mkdir(parents=True)
    build_root.mkdir(parents=True)
    for path in sorted(sources):
        snapshot = run_root / "sources" / relative(path)
        snapshot.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(path, snapshot)
        if sha256(snapshot) != source_hashes[relative(path)]:
            raise SystemExit(f"source changed during snapshot: {path}")
    write_json(run_root / "source-sha256-before.json", source_hashes)
    started_at = dt.datetime.now(dt.timezone.utc)
    began = time.monotonic()
    commands: list[dict] = []
    versions: dict[str, str | None] = {}
    preflight_error = None
    for name, argv in (
        ("verilator", ["verilator", "--version"]), ("yosys", ["yosys", "-V"]),
        ("python", [sys.executable, "--version"]), ("compiler", ["c++", "--version"]),
    ):
        try:
            entry = run_command(run_root, f"version-{name}", argv, commands)
            output = (REPOSITORY / entry["stdout"]).read_text().strip()
            output = output or (REPOSITORY / entry["stderr"]).read_text().strip()
            versions[name] = output.splitlines()[0] if output else None
        except RuntimeError as error:
            versions[name] = None
            preflight_error = str(error)
    results = []
    if preflight_error is None:
        with ThreadPoolExecutor(max_workers=jobs) as executor:
            results = list(executor.map(
                lambda name: evaluate_architecture(name, build_root, run_root), selected
            ))
    for result in results:
        commands.extend(result["commands"])
    source_hashes_after = {
        relative(path): sha256(path) if path.exists() else None for path in sorted(sources)
    }
    unchanged = source_hashes_after == source_hashes
    commit_after = git("rev-parse", "HEAD")
    clean_after = not bool(git("status", "--porcelain", "--untracked-files=normal"))
    status = "pass" if (
        preflight_error is None and len(results) == len(selected)
        and all(result["status"] == "pass" for result in results)
        and unchanged and commit_after == candidate_commit
    ) else "fail"
    write_json(run_root / "source-sha256-after.json", source_hashes_after)
    write_json(run_root / "commands.json", commands)

    def phase_seconds(*phases: str) -> float | None:
        values = [item["elapsed_seconds"] for item in commands if item["phase"] in phases]
        return round(sum(values), 6) if values else None

    record = {
        "schema_version": 1, "record_type": "experiment-run", "run_id": args.run_id,
        "experiment_id": "aes-256-gcm", "experiment_revision": 1,
        "status": status, "measurement_status": "mixed",
        "agent": {
            "model": {"provider": "OpenAI", "display_name": "Codex", "canonical_id": None, "identity_status": "unknown"},
            "harness": {"name": "evaluate_exploration.py", "version": "1", "environment": "local"},
            "reasoning": {"effort": None, "mode": None, "context": None},
            "goal_sha256": None,
            "instruction_hashes": [{"path": "AGENTS.md", "sha256": source_hashes["AGENTS.md"]}] if instructions.exists() else [],
            "subagents": None,
            "notes": "The evaluator cannot observe model identity, agent harness version, reasoning settings, public goal, subagent relationships, or token telemetry; these remain unavailable.",
        },
        "usage": {**dict.fromkeys(("input_tokens", "cached_input_tokens", "cache_write_tokens", "output_tokens", "reasoning_tokens", "total_tokens")), "source": "unavailable"},
        "time": {
            "started_at": started_at.isoformat(), "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
            "agent_wall_seconds": None, "human_seconds": None, "hardware_seconds": None,
            "evaluator_wall_seconds": round(time.monotonic() - began, 6),
            "build_seconds": phase_seconds("rtl-build"),
            "simulation_seconds": phase_seconds("rtl-run-1", "rtl-run-2"),
            "synthesis_seconds": phase_seconds("generic-synthesis", "asic-synthesis"),
            "gate_compile_and_test_seconds": phase_seconds("gate-compile-and-test"),
            "source": "mixed",
            "notes": "Command durations use a monotonic clock and sum across architectures (which may overlap). Gate verification combines cell-model generation, compilation, and simulation; its duration is excluded from build/simulation/synthesis totals because the child tool does not expose their separate durations. Agent, human, and hardware time are unavailable.",
        },
        "cost": {"amount": None, "currency": "USD", "source": "unavailable", "rate_date": None},
        "execution": {
            "candidate_commit": candidate_commit, "candidate_commit_after": commit_after,
            "candidate_profile": "experiments/aes-256-gcm/profile.json",
            "harness_run_ids": [args.run_id], "lab_run_ids": [], "benchmark_id": "aes-256-gcm-64-v1",
            "architectures": selected, "jobs": jobs, "tool_versions": versions,
            "source_sha256": source_hashes, "source_sha256_after": source_hashes_after,
            "sources_unchanged": unchanged, "clean_before": not dirty_before, "clean_after": clean_after,
            "allow_dirty": args.allow_dirty, "commands": commands,
            "artifact_paths": [],
        },
        "result": {
            "status": "targeted-exploration-pass" if status == "pass" else "failed",
            "claim_level": "measured-targeted-local-evaluator",
            "reproducible": status == "pass" and not dirty_before and clean_after,
            "architectures": {result["architecture"]: result for result in results},
            "preflight_error": preflight_error,
            "physical_target": "NangateOpenCellLibrary 45 nm typical, 1.1 V, 25 C (standard-cell synthesis only)",
            "timing_status": "prelayout-estimate", "power": None, "routed_timing": None,
            "notes": "Selected RTL corpus and repeatability checks, generic and named-library synthesis, and mapped-netlist corpus agreement only. This runner does not replace the complete experiment evaluator or prove physical timing, security, novelty, or certification.",
        },
        "evidence": [{"kind": "targeted-exploration", "path": relative(run_root / "commands.json"), "description": "Commands, exit codes, durations, output hashes, before/after source fingerprints, source snapshots, and retained flow outputs."}],
    }
    run_path = run_root / "run.json"
    write_json(run_path, record)
    try:
        run_command(run_root, "validate-run", [
            str(REPOSITORY / "tools" / "experiment"), "validate-run", str(run_path),
        ], commands)
    except RuntimeError as error:
        record["status"] = "fail"
        record["result"].update(status="failed", reproducible=False, validation_error=str(error))
    artifact_hashes = {
        relative(path): sha256(path) for path in sorted(run_root.rglob("*"))
        if path.is_file() and path != run_path
    }
    write_json(run_root / "artifact-sha256.json", artifact_hashes)
    record["execution"]["artifact_paths"] = [*artifact_hashes, relative(run_root / "artifact-sha256.json")]
    write_json(run_path, record)
    print(f"exploration: {record['status'].upper()} run={args.run_id} record={run_path}", flush=True)
    return 0 if record["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
