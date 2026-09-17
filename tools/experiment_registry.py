#!/usr/bin/env python3
"""Validate and inspect the AI Silicon Lab experiment registry.

This tool intentionally uses only the Python standard library. It validates
the versioned experiment specifications and run-record examples without
touching the protected Doom evaluator or ground truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import stat
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENTS_DIR = ROOT / "experiments"
REGISTRY_PATH = EXPERIMENTS_DIR / "registry.json"
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
SHA256_RE = re.compile(r"^[0-9a-fA-F]{64}$")
EXPERIMENT_STATUSES = {
    "specified",
    "in-progress",
    "baseline-verified",
    "complete",
    "blocked",
    "retired",
}
RUN_STATUSES = {"draft", "running", "pass", "fail", "blocked", "reported"}
MEASUREMENT_STATUSES = {"measured", "reported", "estimated", "mixed", "unavailable"}
VALUE_SOURCES = {"measured", "reported", "estimated", "unavailable", "mixed"}
MODEL_IDENTITY_STATUSES = {"exact", "alias-only", "unknown"}
TOKEN_FIELDS = (
    "input_tokens", "cached_input_tokens", "cache_write_tokens",
    "output_tokens", "reasoning_tokens", "total_tokens",
)


class JsonLoadError(Exception):
    pass


def unique_object(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    obj: dict[str, Any] = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key {key!r}")
        obj[key] = value
    return obj


def finite_float(text: str) -> float:
    value = float(text)
    if not math.isfinite(value):
        raise ValueError(f"non-finite JSON number {text}")
    return value


def load_json(path: Path) -> Any:
    try:
        text = path.read_text(encoding="utf-8")
        return json.loads(text, object_pairs_hook=unique_object,
                          parse_float=finite_float, parse_constant=finite_float)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise JsonLoadError(f"{path}: cannot load JSON: {exc}") from exc


def path_issue(path: Path, message: str) -> str:
    try:
        display = path.relative_to(ROOT)
    except ValueError:
        display = path
    return f"{display}: {message}"


def require_object(value: Any, path: str, issues: list[str]) -> dict[str, Any] | None:
    if not isinstance(value, dict):
        issues.append(f"{path}: expected an object")
        return None
    return value


def require_string(obj: dict[str, Any], key: str, path: str, issues: list[str]) -> str | None:
    value = obj.get(key)
    if not isinstance(value, str) or not value.strip():
        issues.append(f"{path}.{key}: expected a non-empty string")
        return None
    return value


def check_enum(value: Any, choices: set[str], path: str, issues: list[str]) -> None:
    if not isinstance(value, str) or value not in choices:
        issues.append(f"{path}: expected one of {sorted(choices)}")


def check_measurement_source(section: dict[str, Any], fields: list[str] | tuple[str, ...],
                             path: str, issues: list[str]) -> None:
    check_enum(section.get("source"), VALUE_SOURCES, path + ".source", issues)
    if section.get("source") == "unavailable":
        require_string(section, "notes", path, issues)
        for key in fields:
            if section.get(key) is not None:
                issues.append(f"{path}.{key}: must be null when source is unavailable")


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def verify_evidence(record: dict[str, Any], path: Path, root: Path = ROOT) -> tuple[int, list[str]]:
    """Verify file-backed evidence against the selected checkout, never the caller's cwd."""
    issues: list[str] = []
    checked = 0
    file_entries = 0
    root = root.resolve()
    for index, item in enumerate(record["evidence"]):
        relative = item.get("path")
        if relative is None:
            continue  # Reports without an artifact remain explicitly unverified.
        file_entries += 1
        location = f"{path}.evidence[{index}]"
        expected = item.get("sha256")
        if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
            issues.append(f"{location}.sha256: file verification requires a SHA-256 digest")
            continue
        try:
            artifact = Path(relative)
            if artifact.is_absolute() or ".." in artifact.parts:
                raise ValueError("expected a repository-relative path without '..'")
            artifact = (root / artifact).resolve()
            try:
                artifact.relative_to(root)
            except ValueError:
                raise ValueError("artifact resolves outside the repository") from None
            if not stat.S_ISREG(artifact.stat().st_mode):
                raise ValueError("artifact is not a regular file")
            actual = sha256_file(artifact)
            checked += 1
            if actual.lower() != expected.lower():
                issues.append(f"{location}: SHA-256 mismatch for {relative!r}: expected {expected}, got {actual}")
        except (OSError, ValueError, RuntimeError) as exc:
            issues.append(f"{location}: cannot verify {relative!r}: {exc}")
    if not file_entries:
        issues.append(path_issue(path, "no file-backed evidence to verify"))
    return checked, issues


def check_slug(value: Any, path: str, issues: list[str]) -> None:
    if not isinstance(value, str) or not SLUG_RE.fullmatch(value):
        issues.append(f"{path}: expected a lowercase hyphenated identifier")


def check_unique_ids(items: Any, path: str, issues: list[str], key: str = "id") -> None:
    if not isinstance(items, list):
        issues.append(f"{path}: expected a list")
        return
    seen: set[str] = set()
    for index, item in enumerate(items):
        if not isinstance(item, dict):
            issues.append(f"{path}[{index}]: expected an object")
            continue
        value = item.get(key)
        if not isinstance(value, str) or not value.strip():
            issues.append(f"{path}[{index}].{key}: expected a non-empty string")
            continue
        if value in seen:
            issues.append(f"{path}: duplicate {key} {value!r}")
        seen.add(value)


def check_nonnegative(value: Any, path: str, issues: list[str], integer: bool = False) -> None:
    if value is None:
        return
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        issues.append(f"{path}: expected a non-negative number or null")
        return
    if isinstance(value, float) and not math.isfinite(value):
        issues.append(f"{path}: non-finite numbers are not allowed")
        return
    if value < 0:
        issues.append(f"{path}: cannot be negative")
    if integer and not isinstance(value, int):
        issues.append(f"{path}: expected an integer or null")


def validate_manifest(manifest: Any, path: Path) -> list[str]:
    issues: list[str] = []
    obj = require_object(manifest, str(path), issues)
    if obj is None:
        return issues

    if isinstance(obj.get("schema_version"), bool) or obj.get("schema_version") != 1:
        issues.append(path_issue(path, "schema_version must be 1"))
    experiment_id = obj.get("experiment_id")
    check_slug(experiment_id, path_issue(path, "experiment_id"), issues)
    for key in ("title", "domain", "objective"):
        require_string(obj, key, str(path), issues)
    check_enum(obj.get("status"), EXPERIMENT_STATUSES, f"{path}.status", issues)

    for key in ("scope", "design_space", "correctness"):
        if not isinstance(obj.get(key), dict):
            issues.append(path_issue(path, f"{key} must be an object"))
    design_space = obj.get("design_space")
    if isinstance(design_space, dict) and not isinstance(design_space.get("open"), bool):
        issues.append(path_issue(path, "design_space.open must be boolean"))

    workloads = obj.get("workloads")
    if not isinstance(workloads, list) or not workloads:
        issues.append(path_issue(path, "workloads must be a non-empty list"))
    else:
        check_unique_ids(workloads, str(path) + ".workloads", issues)
        for index, workload in enumerate(workloads):
            if not isinstance(workload, dict):
                continue
            workload_path = f"{path}.workloads[{index}]"
            for key in ("id", "role", "source"):
                require_string(workload, key, workload_path, issues)
            if "capture_frames" in workload:
                check_nonnegative(workload["capture_frames"], workload_path + ".capture_frames", issues, integer=True)

    for key in ("metrics", "gates", "phases"):
        items = obj.get(key)
        if not isinstance(items, list) or not items:
            issues.append(path_issue(path, f"{key} must be a non-empty list"))
        else:
            check_unique_ids(items, str(path) + f".{key}", issues)

    provenance = obj.get("provenance_requirements")
    if not isinstance(provenance, list) or not provenance or not all(isinstance(item, str) for item in provenance):
        issues.append(path_issue(path, "provenance_requirements must be a non-empty list of strings"))

    research = obj.get("research")
    if not isinstance(research, list) or not research:
        issues.append(path_issue(path, "research must be a non-empty list"))
    else:
        for index, reference in enumerate(research):
            if not isinstance(reference, dict):
                issues.append(path_issue(path, f"research[{index}] must be an object"))
                continue
            for key in ("title", "url", "fact"):
                require_string(reference, key, f"{path}.research[{index}]", issues)

    return issues


def validate_run_record(record: Any, path: Path, known_experiment_ids: set[str] | None = None) -> list[str]:
    issues: list[str] = []
    obj = require_object(record, str(path), issues)
    if obj is None:
        return issues

    if isinstance(obj.get("schema_version"), bool) or obj.get("schema_version") != 1:
        issues.append(path_issue(path, "schema_version must be 1"))
    if obj.get("record_type") != "experiment-run":
        issues.append(path_issue(path, "record_type must be 'experiment-run'"))
    require_string(obj, "run_id", str(path), issues)
    experiment_id = obj.get("experiment_id")
    check_slug(experiment_id, path_issue(path, "experiment_id"), issues)
    if known_experiment_ids is not None and isinstance(experiment_id, str) and experiment_id not in known_experiment_ids:
        issues.append(path_issue(path, f"experiment_id {experiment_id!r} is not in the registry"))
    if not isinstance(obj.get("experiment_revision"), (int, str)) or isinstance(obj.get("experiment_revision"), bool):
        issues.append(path_issue(path, "experiment_revision must be an integer or string"))
    elif isinstance(obj["experiment_revision"], str) and not obj["experiment_revision"].strip():
        issues.append(path_issue(path, "experiment_revision must not be blank"))
    check_enum(obj.get("status"), RUN_STATUSES, f"{path}.status", issues)
    check_enum(obj.get("measurement_status"), MEASUREMENT_STATUSES, f"{path}.measurement_status", issues)

    agent = obj.get("agent")
    if not isinstance(agent, dict):
        issues.append(path_issue(path, "agent must be an object"))
    else:
        model = agent.get("model")
        if not isinstance(model, dict):
            issues.append(path_issue(path, "agent.model must be an object"))
        else:
            for key in ("provider", "display_name", "canonical_id", "identity_status"):
                if key in model and model[key] is not None and not isinstance(model[key], str):
                    issues.append(path_issue(path, f"agent.model.{key} must be a string or null"))
            identity = model.get("identity_status")
            check_enum(identity, MODEL_IDENTITY_STATUSES, f"{path}.agent.model.identity_status", issues)
            if identity == "exact":
                require_string(model, "canonical_id", f"{path}.agent.model", issues)
            elif identity in ("alias-only", "unknown"):
                if "canonical_id" not in model or model["canonical_id"] is not None:
                    issues.append(path_issue(path, "agent.model.canonical_id must be null without an exact identity"))
                if identity == "alias-only":
                    require_string(model, "display_name", f"{path}.agent.model", issues)
        harness = agent.get("harness")
        if not isinstance(harness, dict):
            issues.append(path_issue(path, "agent.harness must be an object"))
        else:
            for key in ("name", "version"):
                if key in harness and harness[key] is not None and not isinstance(harness[key], str):
                    issues.append(path_issue(path, f"agent.harness.{key} must be a string or null"))
        reasoning = agent.get("reasoning")
        if not isinstance(reasoning, dict):
            issues.append(path_issue(path, "agent.reasoning must be an object"))
        else:
            for key in ("effort", "mode", "context"):
                if key in reasoning and reasoning[key] is not None and not isinstance(reasoning[key], str):
                    issues.append(path_issue(path, f"agent.reasoning.{key} must be a string or null"))

    usage = obj.get("usage")
    if not isinstance(usage, dict):
        issues.append(path_issue(path, "usage must be an object"))
    else:
        for key in TOKEN_FIELDS:
            if key not in usage:
                issues.append(path_issue(path, f"usage.{key} is required; use null when unavailable"))
            check_nonnegative(usage.get(key), f"{path}.usage.{key}", issues, integer=True)
        check_measurement_source(usage, TOKEN_FIELDS, f"{path}.usage", issues)

    for section_name in ("time", "cost"):
        section = obj.get(section_name)
        if not isinstance(section, dict):
            issues.append(path_issue(path, f"{section_name} must be an object"))
            continue
        numeric_fields = [key for key in section
                          if key.endswith("_seconds") or key.endswith("_hours") or key == "amount"]
        for key in numeric_fields:
            check_nonnegative(section[key], f"{path}.{section_name}.{key}", issues)
        check_measurement_source(section, numeric_fields, f"{path}.{section_name}", issues)

    for key in ("execution", "result"):
        if not isinstance(obj.get(key), dict):
            issues.append(path_issue(path, f"{key} must be an object"))
    evidence = obj.get("evidence")
    if not isinstance(evidence, list):
        issues.append(path_issue(path, "evidence must be a list"))
    else:
        for index, item in enumerate(evidence):
            if not isinstance(item, dict):
                issues.append(path_issue(path, f"evidence[{index}] must be an object"))
                continue
            require_string(item, "kind", f"{path}.evidence[{index}]", issues)
            require_string(item, "description", f"{path}.evidence[{index}]", issues)
            if item.get("path") is not None:
                require_string(item, "path", f"{path}.evidence[{index}]", issues)
            if item.get("sha256") is not None:
                digest = item["sha256"]
                if not isinstance(digest, str) or not SHA256_RE.fullmatch(digest):
                    issues.append(path_issue(path, f"evidence[{index}].sha256 must be a 64-digit hexadecimal digest or null"))
                if item.get("path") is None:
                    issues.append(path_issue(path, f"evidence[{index}].sha256 requires an artifact path"))

    return issues


def load_registry() -> tuple[dict[str, Any] | None, list[str]]:
    try:
        registry = load_json(REGISTRY_PATH)
    except JsonLoadError as exc:
        return None, [str(exc)]
    issues: list[str] = []
    obj = require_object(registry, str(REGISTRY_PATH), issues)
    if obj is None:
        return None, issues
    if isinstance(obj.get("schema_version"), bool) or obj.get("schema_version") != 1:
        issues.append(path_issue(REGISTRY_PATH, "schema_version must be 1"))
    entries = obj.get("experiments")
    if not isinstance(entries, list) or not entries:
        issues.append(path_issue(REGISTRY_PATH, "experiments must be a non-empty list"))
        return obj, issues
    seen: set[str] = set()
    for index, entry in enumerate(entries):
        entry_path = f"{REGISTRY_PATH}.experiments[{index}]"
        if not isinstance(entry, dict):
            issues.append(f"{entry_path}: expected an object")
            continue
        experiment_id = entry.get("experiment_id")
        check_slug(experiment_id, entry_path + ".experiment_id", issues)
        if isinstance(experiment_id, str):
            if experiment_id in seen:
                issues.append(f"{entry_path}: duplicate experiment_id {experiment_id!r}")
            seen.add(experiment_id)
        relative_path = entry.get("path")
        if not isinstance(relative_path, str) or not relative_path or Path(relative_path).is_absolute() or ".." in Path(relative_path).parts:
            issues.append(f"{entry_path}.path: expected a safe repository-relative path")
            continue
        manifest_path = EXPERIMENTS_DIR / relative_path
        if not manifest_path.is_file():
            issues.append(path_issue(manifest_path, "manifest listed by registry does not exist"))
            continue
        try:
            manifest = load_json(manifest_path)
        except JsonLoadError as exc:
            issues.append(str(exc))
            continue
        issues.extend(validate_manifest(manifest, manifest_path))
        if isinstance(manifest, dict) and manifest.get("experiment_id") != experiment_id:
            issues.append(path_issue(manifest_path, "experiment_id does not match registry entry"))
    return obj, issues


def registry_experiment_ids(registry: dict[str, Any] | None) -> set[str]:
    if not isinstance(registry, dict) or not isinstance(registry.get("experiments"), list):
        return set()
    return {
        entry["experiment_id"]
        for entry in registry["experiments"]
        if isinstance(entry, dict) and isinstance(entry.get("experiment_id"), str)
    }


def validate_saved_runs(registry: dict[str, Any] | None) -> list[str]:
    issues: list[str] = []
    known_ids = registry_experiment_ids(registry)
    paths = sorted((EXPERIMENTS_DIR / "examples").glob("*.json"))
    paths.extend(sorted(EXPERIMENTS_DIR.glob("*/records/**/*.json")))
    for path in paths:
        try:
            record = load_json(path)
        except JsonLoadError as exc:
            issues.append(str(exc))
            continue
        issues.extend(validate_run_record(record, path, known_ids))
    return issues


def print_result(ok: bool, issues: list[str], as_json: bool, artifacts_checked: int | None = None) -> int:
    if as_json:
        result: dict[str, Any] = {"ok": ok, "issues": issues}
        if artifacts_checked is not None:
            result["artifacts_checked"] = artifacts_checked
        print(json.dumps(result, indent=2, sort_keys=True))
    elif ok:
        print("experiment registry: pass")
        if artifacts_checked is not None:
            print(f"evidence files verified: {artifacts_checked}")
    else:
        print("experiment registry: fail", file=sys.stderr)
        for issue in issues:
            print(f"- {issue}", file=sys.stderr)
    return 0 if ok else 1


def command_check(as_json: bool) -> int:
    registry, issues = load_registry()
    issues.extend(validate_saved_runs(registry))
    return print_result(not issues, issues, as_json)


def command_list(as_json: bool) -> int:
    registry, issues = load_registry()
    if issues or registry is None:
        return print_result(False, issues or ["registry is unavailable"], as_json)
    rows = []
    for entry in registry["experiments"]:
        manifest = load_json(EXPERIMENTS_DIR / entry["path"])
        rows.append({
            "experiment_id": entry["experiment_id"],
            "status": manifest.get("status") if isinstance(manifest, dict) else None,
            "title": manifest.get("title") if isinstance(manifest, dict) else entry.get("title"),
            "path": entry["path"],
        })
    if as_json:
        print(json.dumps(rows, indent=2, sort_keys=True))
    else:
        for row in rows:
            print(f"{row['experiment_id']}\t{row['status']}\t{row['title']}\t{row['path']}")
    return 0


def command_show(experiment_id: str) -> int:
    registry, issues = load_registry()
    if issues or registry is None:
        return print_result(False, issues or ["registry is unavailable"], False)
    for entry in registry["experiments"]:
        if entry.get("experiment_id") == experiment_id:
            print((EXPERIMENTS_DIR / entry["path"]).read_text(encoding="utf-8"), end="")
            return 0
    print(f"unknown experiment: {experiment_id}", file=sys.stderr)
    return 2


def command_validate_run(path: Path, as_json: bool, verify_files: bool = False) -> int:
    registry, registry_issues = load_registry()
    issues = list(registry_issues)
    checked = 0 if verify_files else None
    try:
        record = load_json(path)
    except JsonLoadError as exc:
        issues.append(str(exc))
    else:
        issues.extend(validate_run_record(record, path, registry_experiment_ids(registry)))
        if verify_files and not issues:
            checked, evidence_issues = verify_evidence(record, path)
            issues.extend(evidence_issues)
    return print_result(not issues, issues, as_json, checked)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true", dest="as_json", help="emit machine-readable output")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("check", help="validate the registry, manifests, examples, and saved run records")
    subparsers.add_parser("list", help="list registered experiments")
    show_parser = subparsers.add_parser("show", help="print one experiment manifest")
    show_parser.add_argument("experiment_id")
    run_parser = subparsers.add_parser("validate-run", help="validate a run-record JSON file")
    run_parser.add_argument("path", type=Path)
    run_parser.add_argument("--verify-evidence", action="store_true", help="check evidence files and SHA-256 hashes in this checkout")
    args = parser.parse_args(argv)
    if args.command == "check":
        return command_check(args.as_json)
    if args.command == "list":
        return command_list(args.as_json)
    if args.command == "show":
        return command_show(args.experiment_id)
    if args.command == "validate-run":
        return command_validate_run(args.path, args.as_json, args.verify_evidence)
    parser.error("a command is required")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
