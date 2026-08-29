#!/usr/bin/env python3
"""Comparison methods available to any experiment.

A comparator never sees the candidate process. It runs after the candidate has
exited, over files on disk, so a candidate cannot influence its own verdict.
Every comparator reports what it checked, not only whether it passed: a
comparator that checked zero items fails rather than reporting success.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from .core import HarnessError, read_json, relative, sha256_file
from .contracts import Comparison


MAX_REPORTED_MISMATCHES = 16


def _file_map(root: Path) -> dict[str, Path]:
    return {
        path.relative_to(root).as_posix(): path
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def _first_difference(expected: bytes, actual: bytes) -> dict[str, Any]:
    limit = min(len(expected), len(actual))
    offset = next((i for i in range(limit) if expected[i] != actual[i]), limit)
    differing = sum(1 for i in range(limit) if expected[i] != actual[i])
    differing += abs(len(expected) - len(actual))
    return {
        "first_differing_offset": offset,
        "differing_bytes": differing,
        "expected_length": len(expected),
        "actual_length": len(actual),
        "expected_byte": expected[offset] if offset < len(expected) else None,
        "actual_byte": actual[offset] if offset < len(actual) else None,
    }


def compare_exact_bytes(reference: Path, candidate: Path, options: dict[str, Any]) -> Comparison:
    """Every reference file must exist in the candidate output, byte-identical.

    This is the generalisation of the Doom frame oracle: the shape of the data
    is irrelevant, only exact equality of every produced artifact.
    """
    expected_files = _file_map(reference)
    actual_files = _file_map(candidate)
    if not expected_files:
        return Comparison(
            ok=False,
            comparator="exact-bytes",
            details={"error": f"reference {relative(reference)} contains no files"},
        )

    mismatches: list[dict[str, Any]] = []
    checked = 0
    total_differing = 0
    for name, expected_path in expected_files.items():
        actual_path = actual_files.get(name)
        if actual_path is None:
            mismatches.append({"artifact": name, "reason": "missing from candidate output"})
            continue
        checked += 1
        expected_bytes = expected_path.read_bytes()
        actual_bytes = actual_path.read_bytes()
        if expected_bytes == actual_bytes:
            continue
        detail = _first_difference(expected_bytes, actual_bytes)
        total_differing += detail["differing_bytes"]
        if len(mismatches) < MAX_REPORTED_MISMATCHES:
            mismatches.append({"artifact": name, "reason": "byte mismatch", **detail})
        else:
            mismatches.append({"artifact": name, "reason": "byte mismatch"})

    extra = sorted(set(actual_files) - set(expected_files))
    if extra and not options.get("allow_extra_artifacts", True):
        for name in extra[:MAX_REPORTED_MISMATCHES]:
            mismatches.append({"artifact": name, "reason": "unexpected extra artifact"})

    return Comparison(
        ok=not mismatches and checked == len(expected_files),
        comparator="exact-bytes",
        checked=checked,
        mismatches=mismatches[:MAX_REPORTED_MISMATCHES],
        details={
            "reference_artifacts": len(expected_files),
            "candidate_artifacts": len(actual_files),
            "mismatched_artifacts": len(mismatches),
            "total_differing_bytes": total_differing,
            "extra_artifacts": len(extra),
        },
    )


def _load_vectors(path: Path, side: str) -> list[dict[str, Any]]:
    if not path.is_file():
        raise HarnessError(f"{side} vector file {relative(path)} is missing")
    payload = read_json(path)
    if isinstance(payload, dict):
        payload = payload.get("vectors")
    if not isinstance(payload, list) or not payload:
        raise HarnessError(f"{side} vector file {relative(path)} has no vectors list")
    for index, item in enumerate(payload):
        if not isinstance(item, dict) or not isinstance(item.get("id"), str):
            raise HarnessError(f"{side} vector[{index}] needs an object with a string id")
    return payload


def compare_vectors(reference: Path, candidate: Path, options: dict[str, Any]) -> Comparison:
    """Known-answer comparison over `vectors.json` produced by both sides.

    Vectors are matched by `id`, never by position, so a candidate that drops,
    reorders, or duplicates a vector is a failure rather than a silent pass.
    """
    name = options.get("vector_file", "vectors.json")
    fields = options.get("compare_fields")
    expected = {item["id"]: item for item in _load_vectors(reference / name, "reference")}
    actual_list = _load_vectors(candidate / name, "candidate")
    actual: dict[str, dict[str, Any]] = {}
    duplicates: list[str] = []
    for item in actual_list:
        if item["id"] in actual:
            duplicates.append(item["id"])
        actual[item["id"]] = item

    mismatches: list[dict[str, Any]] = []
    for vector_id in duplicates:
        mismatches.append({"vector": vector_id, "reason": "duplicated in candidate output"})

    checked = 0
    for vector_id, expected_vector in expected.items():
        actual_vector = actual.get(vector_id)
        if actual_vector is None:
            mismatches.append({"vector": vector_id, "reason": "missing from candidate output"})
            continue
        checked += 1
        keys = fields or [k for k in expected_vector if k != "id"]
        differing = {
            key: {"expected": expected_vector.get(key), "actual": actual_vector.get(key)}
            for key in keys
            if expected_vector.get(key) != actual_vector.get(key)
        }
        if differing and len(mismatches) < MAX_REPORTED_MISMATCHES:
            mismatches.append({"vector": vector_id, "reason": "field mismatch", "fields": differing})
        elif differing:
            mismatches.append({"vector": vector_id, "reason": "field mismatch"})

    extra = sorted(set(actual) - set(expected))
    for vector_id in extra[:MAX_REPORTED_MISMATCHES]:
        mismatches.append({"vector": vector_id, "reason": "not present in reference"})

    return Comparison(
        ok=not mismatches and checked == len(expected) and checked > 0,
        comparator="vectors",
        checked=checked,
        mismatches=mismatches[:MAX_REPORTED_MISMATCHES],
        details={
            "reference_vectors": len(expected),
            "candidate_vectors": len(actual),
            "compared_fields": fields or "all-reference-fields",
            "extra_vectors": len(extra),
        },
    )


def compare_digest(reference: Path, candidate: Path, options: dict[str, Any]) -> Comparison:
    """Whole-directory digest equality, for large opaque artifact sets."""
    from .core import sha256_tree

    expected = sha256_tree(reference)
    actual = sha256_tree(candidate)
    files = sum(1 for path in reference.rglob("*") if path.is_file())
    return Comparison(
        ok=expected == actual and files > 0,
        comparator="digest",
        checked=files,
        mismatches=[]
        if expected == actual
        else [{"reason": "tree digest mismatch", "expected": expected, "actual": actual}],
        details={"reference_digest": expected, "candidate_digest": actual},
    )


COMPARATORS: dict[str, Callable[[Path, Path, dict[str, Any]], Comparison]] = {
    "exact-bytes": compare_exact_bytes,
    "vectors": compare_vectors,
    "digest": compare_digest,
}


def get(name: str) -> Callable[[Path, Path, dict[str, Any]], Comparison]:
    try:
        return COMPARATORS[name]
    except KeyError:
        known = ", ".join(sorted(COMPARATORS))
        raise HarnessError(f"unknown comparator {name!r}; available: {known}") from None


def compare_repeats(directories: list[Path]) -> Comparison:
    """Independent candidate runs must produce byte-identical output."""
    from .core import sha256_tree

    if len(directories) < 2:
        return Comparison(
            ok=True,
            comparator="determinism",
            checked=len(directories),
            details={"note": "single execution; determinism not exercised"},
        )
    digests = [sha256_tree(directory) for directory in directories]
    unique = sorted(set(digests))
    return Comparison(
        ok=len(unique) == 1,
        comparator="determinism",
        checked=len(directories),
        mismatches=[]
        if len(unique) == 1
        else [{"reason": "repeated executions differ", "distinct_digests": unique}],
        details={"executions": len(directories), "digests": digests},
    )
