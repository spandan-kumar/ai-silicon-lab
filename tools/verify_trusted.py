#!/usr/bin/env python3
"""Check protected-file hashes and manifest coverage without requiring hardware tools."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess

from experiment_registry import ROOT, SHA256_RE, JsonLoadError, load_json, sha256_file


def verify_trusted(root: Path = ROOT) -> dict:
    root = root.resolve()
    issues = []
    checked = 0
    manifest_name = "ground_truth/trusted-manifest.json"
    try:
        manifest = load_json(root / manifest_name)
        if not isinstance(manifest, dict) or manifest.get("schema_version") != 1 or isinstance(manifest.get("schema_version"), bool):
            raise ValueError("expected a version 1 trusted manifest")
        files = manifest.get("files")
        if not isinstance(files, dict) or not files:
            raise ValueError("trusted manifest must contain a non-empty files object")
        if manifest.get("protected_roots") != ["lab", "ground_truth"]:
            raise ValueError("protected_roots must be lab and ground_truth")
        tracked = subprocess.run(["git", "ls-files", "-z", "--", "lab", "ground_truth"],
                                 cwd=root, capture_output=True, text=True, check=False)
        if tracked.returncode:
            raise ValueError("cannot list protected files: " + tracked.stderr.strip())
        expected_paths = set(tracked.stdout.split("\0")) - {"", manifest_name}
        for missing in sorted(expected_paths - files.keys()):
            issues.append(f"tracked protected file is absent from manifest: {missing}")
        for extra in sorted(files.keys() - expected_paths):
            issues.append(f"manifest entry is not a tracked protected file: {extra}")
        for relative, expected in files.items():
            if relative not in expected_paths:
                continue
            if not isinstance(expected, str) or not SHA256_RE.fullmatch(expected):
                issues.append(f"invalid SHA-256 digest: {relative}")
                continue
            try:
                path = (root / relative).resolve()
                path.relative_to(root)
                if not path.is_file():
                    raise ValueError("not a regular file")
                actual = sha256_file(path)
                checked += 1
                if actual.lower() != expected.lower():
                    issues.append(f"trusted hash mismatch: {relative}")
            except (OSError, ValueError, RuntimeError) as exc:
                issues.append(f"cannot verify {relative}: {exc}")
    except (JsonLoadError, OSError, ValueError) as exc:
        issues.append(str(exc))
    return {"ok": not issues, "checked": checked, "issues": issues}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    result = verify_trusted()
    if args.json:
        print(json.dumps(result, indent=2, sort_keys=True))
    else:
        print(f"trusted files: {'pass' if result['ok'] else 'fail'} ({result['checked']} checked)")
        for issue in result["issues"]:
            print(f"- {issue}")
    return 0 if result["ok"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
