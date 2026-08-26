#!/usr/bin/env python3
"""Trusted, file-oriented evaluator for AI Silicon Lab."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import shlex
import subprocess
import sys
import time
import uuid
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
GROUND_TRUTH = ROOT / "ground_truth"
BENCHMARK_PATH = GROUND_TRUTH / "benchmark" / "benchmark.json"
TRUST_MANIFEST_PATH = GROUND_TRUTH / "trusted-manifest.json"
REFERENCE_BINARY = GROUND_TRUTH / "reference" / "bin" / "doomgeneric-headless"


def timestamp() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def repo_relative(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT.resolve()))
    except ValueError:
        return str(path)


def under(path: Path, parent: Path) -> bool:
    try:
        path.resolve().relative_to(parent.resolve())
        return True
    except ValueError:
        return False


def git_run(args: list[str], timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=ROOT,
        capture_output=True,
        text=True,
        timeout=timeout,
        check=False,
    )


def git_snapshot() -> dict[str, Any]:
    result: dict[str, Any] = {"available": False, "head": None, "branch": None, "status": []}
    try:
        head = git_run(["rev-parse", "HEAD"])
        branch = git_run(["branch", "--show-current"])
        status = git_run(["status", "--short"])
    except (OSError, subprocess.SubprocessError) as exc:
        result["error"] = str(exc)
        return result

    if head.returncode == 0:
        result["available"] = True
        result["head"] = head.stdout.strip()
    if branch.returncode == 0:
        result["branch"] = branch.stdout.strip() or None
    if status.returncode == 0:
        result["status"] = status.stdout.splitlines()
    result["dirty"] = bool(result["status"])
    return result


def capture_git_diff(path: Path) -> dict[str, Any]:
    try:
        with path.open("wb") as handle:
            completed = subprocess.run(
                ["git", "diff", "--binary", "--no-ext-diff"],
                cwd=ROOT,
                stdout=handle,
                stderr=subprocess.PIPE,
                check=False,
            )
        return {
            "available": completed.returncode == 0,
            "path": repo_relative(path),
            "sha256": sha256_file(path),
            "stderr": completed.stderr.decode("utf-8", errors="replace"),
        }
    except (OSError, subprocess.SubprocessError) as exc:
        return {"available": False, "path": repo_relative(path), "error": str(exc)}


def verify_trusted_files() -> dict[str, Any]:
    if not TRUST_MANIFEST_PATH.is_file():
        return {"ok": False, "errors": ["trusted manifest is missing"], "checked": 0}
    try:
        manifest = read_json(TRUST_MANIFEST_PATH)
        files = manifest["files"]
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        return {"ok": False, "errors": [f"cannot read trusted manifest: {exc}"], "checked": 0}

    errors: list[str] = []
    checked = 0
    for relative, expected in sorted(files.items()):
        path = ROOT / relative
        if not path.is_file():
            errors.append(f"missing trusted file: {relative}")
            continue
        checked += 1
        try:
            actual = sha256_file(path)
        except OSError as exc:
            errors.append(f"cannot hash {relative}: {exc}")
            continue
        if actual != expected:
            errors.append(f"trusted hash mismatch: {relative}")
    return {"ok": not errors, "errors": errors, "checked": checked}


def command_form(command: Any) -> tuple[list[str], str]:
    if isinstance(command, str):
        if not command.strip():
            raise ValueError("command string is empty")
        return ["/bin/sh", "-c", command], command
    if isinstance(command, list) and command and all(isinstance(item, str) for item in command):
        return list(command), shlex.join(command)
    raise ValueError("command must be a non-empty string or argv array")


def command_audit(command: Any) -> dict[str, Any]:
    try:
        _, display = command_form(command)
    except ValueError as exc:
        return {"ok": False, "blocked": [], "error": str(exc)}

    blocked_tokens = [
        "ground_truth/reference",
        "ground_truth/evaluator",
        "ground_truth/trusted-manifest",
        "reference_frames.bin",
        ".aisl/reference-build",
        "lab/evaluate",
        "lab/reference",
    ]
    blocked = [token for token in blocked_tokens if token in display]
    return {"ok": not blocked, "blocked": blocked, "command": display}


def execute_command(
    label: str,
    command: Any,
    env: dict[str, str],
    run_dir: Path,
    timeout_seconds: float,
    records: list[dict[str, Any]],
) -> dict[str, Any]:
    stdout_path = run_dir / ("stdout.log" if label == "run" else f"{label}.stdout.log")
    stderr_path = run_dir / ("stderr.log" if label == "run" else f"{label}.stderr.log")
    started_at = timestamp()
    started = time.monotonic()
    try:
        argv, display = command_form(command)
        with stdout_path.open("wb") as stdout, stderr_path.open("wb") as stderr:
            process = subprocess.Popen(
                argv,
                cwd=ROOT,
                env=env,
                stdout=stdout,
                stderr=stderr,
                start_new_session=True,
            )
            timed_out = False
            try:
                returncode = process.wait(timeout=timeout_seconds)
            except subprocess.TimeoutExpired:
                timed_out = True
                process.kill()
                returncode = process.wait()
        error = None
    except (OSError, ValueError, subprocess.SubprocessError) as exc:
        display = str(command)
        returncode = None
        timed_out = False
        error = str(exc)
        stdout_path.touch()
        stderr_path.write_text(error + "\n", encoding="utf-8")

    record = {
        "label": label,
        "command": display,
        "started_at": started_at,
        "finished_at": timestamp(),
        "elapsed_seconds": round(time.monotonic() - started, 6),
        "returncode": returncode,
        "timed_out": timed_out,
        "stdout": repo_relative(stdout_path),
        "stderr": repo_relative(stderr_path),
    }
    if error is not None:
        record["error"] = error
    records.append(record)
    return record


def make_execution_env(run_dir: Path, input_file: Path, benchmark: dict[str, Any]) -> dict[str, str]:
    run_home = run_dir / "home"
    run_tmp = run_dir / "tmp"
    run_home.mkdir(parents=True, exist_ok=True)
    run_tmp.mkdir(parents=True, exist_ok=True)
    video = benchmark["video"]
    execution = benchmark["execution"]
    path = os.environ.get("PATH", "/usr/bin:/bin")
    return {
        "PATH": path,
        "HOME": str(run_home),
        "TMPDIR": str(run_tmp),
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
        "XDG_CONFIG_HOME": str(run_home / ".config"),
        "AISL_INPUT_FILE": str(input_file),
        "AISL_FRAME_DIR": str(run_dir / "frames"),
        "AISL_RESULT_FILE": str(run_dir / "artifacts" / "candidate-report.json"),
        "AISL_FRAME_WIDTH": str(video["width"]),
        "AISL_FRAME_HEIGHT": str(video["height"]),
        "AISL_FRAME_FORMAT": str(video["format"]),
        "AISL_FRAME_COUNT": str(execution["capture_frames"]),
        "AISL_FRAME_WARMUP": str(execution["warmup_frames"]),
        "AISL_RUN_ID": run_dir.name,
    }


def validate_benchmark(benchmark: dict[str, Any]) -> list[str]:
    errors: list[str] = []
    try:
        video = benchmark["video"]
        execution = benchmark["execution"]
        expected_bytes = int(video["width"]) * int(video["height"]) * 3
        if int(video["frame_bytes"]) != expected_bytes:
            errors.append("benchmark frame_bytes does not match RGB888 dimensions")
        oracle = ROOT / benchmark["oracle_file"]
        expected_archive_bytes = int(execution["capture_frames"]) * int(video["frame_bytes"])
        if not oracle.is_file():
            errors.append("benchmark oracle archive is missing")
        elif oracle.stat().st_size != expected_archive_bytes:
            errors.append("benchmark oracle archive has the wrong size")
        input_file = ROOT / benchmark["input_file"]
        if not input_file.is_file():
            errors.append("benchmark input file is missing")
    except (KeyError, TypeError, ValueError, OSError) as exc:
        errors.append(f"invalid benchmark definition: {exc}")
    return errors


def compare_frames(
    benchmark: dict[str, Any],
    frame_dir: Path,
) -> dict[str, Any]:
    video = benchmark["video"]
    execution = benchmark["execution"]
    frame_bytes = int(video["frame_bytes"])
    frame_count = int(execution["capture_frames"])
    pixels = int(video["width"]) * int(video["height"])
    expected_names = {f"frame-{index:06d}.rgb" for index in range(frame_count)}
    actual_paths = {path.name: path for path in frame_dir.glob("*.rgb")}
    missing = sorted(expected_names - actual_paths.keys())
    extra = sorted(actual_paths.keys() - expected_names)
    mismatches: list[dict[str, Any]] = []
    max_mean_error = 0.0
    max_bad_pixel_fraction = 0.0
    valid_frames = 0

    oracle_path = ROOT / benchmark["oracle_file"]
    try:
        with oracle_path.open("rb") as oracle:
            for index in range(frame_count):
                name = f"frame-{index:06d}.rgb"
                expected = oracle.read(frame_bytes)
                actual_path = actual_paths.get(name)
                if actual_path is None:
                    continue
                if actual_path.stat().st_size != frame_bytes:
                    mismatches.append(
                        {"frame": index, "reason": "wrong_size", "bytes": actual_path.stat().st_size}
                    )
                    continue
                actual = actual_path.read_bytes()
                valid_frames += 1
                if actual == expected:
                    continue
                difference_sum = sum(abs(left - right) for left, right in zip(actual, expected))
                mean_error = difference_sum / len(actual)
                bad_pixels = sum(
                    actual[offset : offset + 3] != expected[offset : offset + 3]
                    for offset in range(0, frame_bytes, 3)
                )
                bad_fraction = bad_pixels / pixels
                max_mean_error = max(max_mean_error, mean_error)
                max_bad_pixel_fraction = max(max_bad_pixel_fraction, bad_fraction)
                if len(mismatches) < 10:
                    mismatches.append(
                        {
                            "frame": index,
                            "reason": "pixel_mismatch",
                            "mean_abs_error": mean_error,
                            "bad_pixel_fraction": bad_fraction,
                            "sha256": hashlib.sha256(actual).hexdigest(),
                        }
                    )
    except OSError as exc:
        return {
            "correct": False,
            "frames_expected": frame_count,
            "frames_received": len(actual_paths),
            "missing": missing,
            "extra": extra,
            "mismatches": [{"reason": f"oracle_error: {exc}"}],
            "max_mean_abs_error": None,
            "max_bad_pixel_fraction": None,
        }

    correct = not missing and not extra and valid_frames == frame_count and not mismatches
    return {
        "correct": correct,
        "frames_expected": frame_count,
        "frames_received": len(actual_paths),
        "missing": missing,
        "extra": extra,
        "mismatches": mismatches,
        "max_mean_abs_error": max_mean_error if valid_frames else None,
        "max_bad_pixel_fraction": max_bad_pixel_fraction if valid_frames else None,
    }


def read_candidate_report(path: Path, stdout_path: Path) -> tuple[dict[str, Any] | None, list[str], str]:
    errors: list[str] = []
    report: dict[str, Any] | None = None
    if not path.is_file():
        errors.append("candidate result JSON is missing")
    else:
        try:
            value = read_json(path)
            if not isinstance(value, dict):
                errors.append("candidate result JSON is not an object")
            else:
                report = value
        except (OSError, json.JSONDecodeError) as exc:
            errors.append(f"candidate result JSON is invalid: {exc}")
    try:
        stdout = stdout_path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        stdout = ""
    return report, errors, stdout


def numeric(value: Any) -> int | float | None:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if isinstance(value, float) and not math.isfinite(value):
        return None
    return value


def hardware_report(report: dict[str, Any] | None) -> dict[str, Any]:
    keys = ("lut", "ff", "bram", "dsp", "io", "area", "fmax_mhz", "power_mw")
    values = {key: None for key in keys}
    supplied = report.get("hardware") if isinstance(report, dict) else None
    if isinstance(supplied, dict):
        for key in keys:
            values[key] = numeric(supplied.get(key))
        source = "candidate-reported-untrusted"
    else:
        source = "not-reported"
    values["availability"] = "reported" if source != "not-reported" else "unavailable"
    values["source"] = source
    return values


def candidate_from_args(args: argparse.Namespace, benchmark: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
    if args.self_test:
        if args.self_test == "known-good":
            if not REFERENCE_BINARY.is_file() or not os.access(REFERENCE_BINARY, os.X_OK):
                return None, ["trusted reference binary is unavailable for self-test"]
            asset = ROOT / benchmark["asset"]
            command = [str(REFERENCE_BINARY), "-iwad", str(asset), *benchmark["reference_args"]]
            return {
                "name": "self-test-known-good-reference",
                "manifest": None,
                "build": None,
                "run": command,
                "self_test": "known-good",
            }, []
        broken = GROUND_TRUTH / "self_test" / "broken_candidate.py"
        return {
            "name": "self-test-intentionally-broken",
            "manifest": None,
            "build": None,
            "run": [sys.executable, str(broken)],
            "self_test": "broken",
        }, []

    candidate_path = Path(args.candidate)
    if not candidate_path.is_absolute():
        candidate_path = ROOT / candidate_path
    if not under(candidate_path, ROOT / "workspace"):
        return None, ["normal candidate manifest must be inside workspace/"]
    if not candidate_path.is_file():
        return None, [f"candidate manifest is missing: {repo_relative(candidate_path)}"]
    try:
        manifest = read_json(candidate_path)
        if not isinstance(manifest, dict):
            raise ValueError("manifest is not an object")
        name = manifest.get("name")
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name must be a non-empty string")
        run = manifest.get("run")
        command_form(run)
        build = manifest.get("build")
        if build is not None:
            command_form(build)
    except (OSError, json.JSONDecodeError, ValueError, TypeError) as exc:
        return None, [f"invalid candidate manifest: {exc}"]
    return {
        "name": name,
        "manifest": candidate_path,
        "manifest_data": manifest,
        "build": build,
        "run": run,
        "self_test": None,
    }, []


def unique(items: list[str]) -> list[str]:
    return list(dict.fromkeys(items))


def evaluate(args: argparse.Namespace) -> tuple[dict[str, Any], int]:
    run_id = args.run_id or (dt.datetime.now(dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ") + "-" + uuid.uuid4().hex[:8])
    if not run_id.replace("-", "").replace("_", "").replace(".", "").isalnum():
        raise ValueError("run ID may contain only letters, digits, '.', '_' and '-'")
    run_dir = ROOT / "runs" / run_id
    if run_dir.exists():
        raise ValueError(f"run directory already exists: {run_id}")
    (run_dir / "artifacts").mkdir(parents=True)
    (run_dir / "frames").mkdir()
    (run_dir / "waveforms").mkdir()

    commands: list[dict[str, Any]] = []
    git_before = git_snapshot()
    trust_before = verify_trusted_files()
    errors: list[str] = list(trust_before["errors"])

    try:
        benchmark = read_json(BENCHMARK_PATH)
        if not isinstance(benchmark, dict):
            raise ValueError("benchmark is not an object")
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        benchmark = {}
        errors.append(f"cannot load benchmark: {exc}")
    errors.extend(validate_benchmark(benchmark) if benchmark else [])

    input_source = ROOT / benchmark.get("input_file", "ground_truth/benchmark/input.events")
    input_copy = run_dir / "inputs.events"
    if input_source.is_file():
        shutil.copyfile(input_source, input_copy)
        input_before = sha256_file(input_copy)
    else:
        input_copy.write_text("", encoding="utf-8")
        input_before = None

    candidate, candidate_errors = candidate_from_args(args, benchmark)
    errors.extend(candidate_errors)
    candidate_manifest_hash_before = None
    if candidate and candidate.get("manifest"):
        manifest_path = candidate["manifest"]
        shutil.copyfile(manifest_path, run_dir / "artifacts" / "candidate-manifest.json")
        candidate_manifest_hash_before = sha256_file(manifest_path)
    elif candidate:
        write_json(run_dir / "artifacts" / "candidate-manifest.json", {
            "schema_version": 1,
            "name": candidate["name"],
            "build": candidate["build"],
            "run": candidate["run"],
            "self_test": candidate["self_test"],
        })

    if benchmark:
        write_json(run_dir / "artifacts" / "benchmark.json", benchmark)
    metadata = {
        "schema_version": 1,
        "run_id": run_id,
        "started_at": timestamp(),
        "benchmark_id": benchmark.get("id"),
        "candidate": candidate["name"] if candidate else None,
        "self_test": args.self_test,
        "git_before": git_before,
        "input_sha256": input_before,
    }
    write_json(run_dir / "metadata.json", metadata)

    build_record: dict[str, Any]
    run_record: dict[str, Any] | None = None
    audit: dict[str, Any] = {"ok": True, "commands": []}
    if candidate:
        for label in ("build", "run"):
            command = candidate.get(label)
            if command is not None:
                check = command_audit(command) if not args.self_test else {"ok": True, "blocked": [], "command": command_form(command)[1]}
                audit["commands"].append({"label": label, **check})
                if not check["ok"]:
                    audit["ok"] = False
                    errors.append(f"candidate command audit blocked {label}: {', '.join(check['blocked'])}")
    if not audit["ok"]:
        build_record = {"status": "blocked", "requested": candidate is not None and candidate.get("build") is not None}
    elif candidate is None:
        build_record = {"status": "not_run", "requested": False}
    else:
        build_command = candidate.get("build")
        if build_command is None:
            build_record = {"status": "not_requested", "requested": False}
        else:
            env = make_execution_env(run_dir, input_copy, benchmark)
            build_record = execute_command(
                "build", build_command, env, run_dir,
                float(benchmark.get("execution", {}).get("timeout_seconds", 300)), commands,
            )
            build_record["status"] = "pass" if build_record["returncode"] == 0 and not build_record["timed_out"] else "fail"
            if build_record["status"] != "pass":
                errors.append("candidate build failed")

        build_ok = build_record["status"] in ("pass", "not_requested")
        if build_ok:
            env = make_execution_env(run_dir, input_copy, benchmark)
            run_record = execute_command(
                "run", candidate["run"], env, run_dir,
                float(benchmark.get("execution", {}).get("timeout_seconds", 300)), commands,
            )
        else:
            errors.append("candidate run skipped because build failed")

    write_json(run_dir / "commands.json", commands)
    trust_after = verify_trusted_files()
    errors.extend(trust_after["errors"])
    if not trust_after["ok"]:
        errors.append("ground-truth integrity verification failed")

    input_after = sha256_file(input_copy) if input_copy.is_file() else None
    input_unchanged = input_before is not None and input_after == input_before
    if not input_unchanged:
        errors.append("candidate modified or failed to receive the canonical input copy")

    candidate_manifest_changed = False
    if candidate and candidate.get("manifest") and candidate_manifest_hash_before:
        candidate_manifest_changed = sha256_file(candidate["manifest"]) != candidate_manifest_hash_before
        if candidate_manifest_changed:
            errors.append("candidate manifest changed during evaluation")

    report_path = run_dir / "artifacts" / "candidate-report.json"
    stdout_path = run_dir / "stdout.log"
    report, report_errors, stdout = read_candidate_report(report_path, stdout_path)
    errors.extend(report_errors if run_record is not None else [])
    marker_booted = "AISL_BOOTED" in stdout
    marker_doom_started = "AISL_DOOM_STARTED" in stdout
    report_booted = report is not None and report.get("booted") is True
    report_doom_started = report is not None and report.get("doom_started") is True
    booted = marker_booted and report_booted
    doom_started = marker_doom_started and report_doom_started
    if run_record is not None and not booted:
        errors.append("candidate did not satisfy boot protocol")
    if run_record is not None and not doom_started:
        errors.append("candidate did not satisfy DOOM-start protocol")

    comparison = compare_frames(benchmark, run_dir / "frames") if benchmark and not validate_benchmark(benchmark) else {
        "correct": False,
        "frames_expected": benchmark.get("execution", {}).get("capture_frames"),
        "frames_received": 0,
        "missing": [],
        "extra": [],
        "mismatches": [{"reason": "benchmark_invalid"}],
        "max_mean_abs_error": None,
        "max_bad_pixel_fraction": None,
    }
    write_json(run_dir / "artifacts" / "frame-comparison.json", comparison)
    if run_record is not None and not comparison["correct"]:
        errors.append("frame comparison failed")

    process_ok = run_record is not None and run_record.get("returncode") == 0 and not run_record.get("timed_out")
    if run_record is not None and not process_ok:
        errors.append("candidate process failed or timed out")
    integrity_ok = bool(trust_before["ok"] and trust_after["ok"])
    if not integrity_ok:
        errors.append("trusted state was not intact for the complete run")

    elapsed = run_record.get("elapsed_seconds") if run_record else None
    frames_received = comparison.get("frames_received") or 0
    reported = {}
    for key in ("cycles", "tics", "fps"):
        value = numeric(report.get(key)) if report else None
        reported[key] = value
    performance = {
        "frames": frames_received,
        "cycles": reported["cycles"],
        "tics": reported["tics"],
        "fps": reported["fps"],
        "wall_seconds": elapsed,
        "wall_fps": round(frames_received / elapsed, 6) if elapsed and elapsed > 0 else None,
        "reported_values_are_trusted": False,
    }
    git_diff = capture_git_diff(run_dir / "artifacts" / "git-diff.patch")
    git_after = git_snapshot()
    reproducible = bool(git_before.get("head") and git_after.get("head") and not git_before.get("dirty") and not git_after.get("dirty"))
    if not reproducible:
        errors.append("source state is not a clean committed Git revision")

    result = {
        "schema_version": 1,
        "status": "pass" if not errors and candidate is not None and process_ok else "fail",
        "run_id": run_id,
        "validation_mode": "self-test" if args.self_test else "candidate",
        "candidate": {
            "name": candidate["name"] if candidate else None,
            "manifest": repo_relative(candidate["manifest"]) if candidate and candidate.get("manifest") else None,
            "command_audit": audit,
            "build": build_record,
            "run": run_record,
            "manifest_changed": candidate_manifest_changed,
        },
        "benchmark": {
            "id": benchmark.get("id"),
            "input_sha256": input_before,
            "input_unchanged": input_unchanged,
            "width": benchmark.get("video", {}).get("width"),
            "height": benchmark.get("video", {}).get("height"),
            "format": benchmark.get("video", {}).get("format"),
            "warmup_frames": benchmark.get("execution", {}).get("warmup_frames"),
            "capture_frames": benchmark.get("execution", {}).get("capture_frames"),
        },
        "functional": {
            "built": build_record.get("status") in ("pass", "not_requested"),
            "booted": booted,
            "doom_started": doom_started,
            "correct": bool(comparison["correct"] and process_ok and booted and doom_started and input_unchanged and integrity_ok),
            "frame_error": comparison.get("max_mean_abs_error"),
            "bad_pixel_fraction": comparison.get("max_bad_pixel_fraction"),
            "frames_received": frames_received,
        },
        "performance": performance,
        "hardware": hardware_report(report),
        "integrity": {
            "before": trust_before,
            "after": trust_after,
            "ok": integrity_ok,
        },
        "git": {
            "before": git_before,
            "after": git_after,
            "diff": git_diff,
            "reproducible": reproducible,
        },
        "artifacts": {
            "run_dir": repo_relative(run_dir),
            "frames_dir": repo_relative(run_dir / "frames"),
            "waveforms_dir": repo_relative(run_dir / "waveforms"),
        },
        "failure_reasons": unique(errors),
        "finished_at": timestamp(),
    }
    write_json(run_dir / "git-info.json", result["git"])
    write_json(run_dir / "metrics.json", result)
    return result, 0 if result["status"] == "pass" else 1


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Evaluate an AI Silicon Lab candidate")
    parser.add_argument("--candidate", default="workspace/candidate.json", help="candidate manifest inside workspace/")
    parser.add_argument("--run-id", help="explicit run identifier")
    parser.add_argument("--self-test", choices=("known-good", "broken"), help="validate the lab fixture")
    parser.add_argument("--json-only", action="store_true", help="emit only the final JSON result")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    try:
        result, code = evaluate(args)
    except Exception as exc:  # The command must fail honestly and remain machine-readable.
        result = {
            "schema_version": 1,
            "status": "fail",
            "error": f"evaluator exception: {exc}",
            "finished_at": timestamp(),
        }
        code = 1
    print(json.dumps(result, sort_keys=True))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
