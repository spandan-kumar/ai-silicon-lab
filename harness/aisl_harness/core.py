#!/usr/bin/env python3
"""Shared primitives for the autonomous research harness.

Standard library only, matching the rest of the laboratory tooling.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
from typing import Any, Iterable, Sequence


ROOT = Path(__file__).resolve().parents[2]
STATE_ROOT = ROOT / ".aisl" / "harness"

# Roots the harness must never write to. They hold the protected Doom judge,
# reference, oracle, and trust manifest.
PROTECTED_ROOTS = ("lab", "ground_truth")


class HarnessError(Exception):
    """A condition the harness refuses to guess its way past."""


def utc_now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_tree(root: Path, patterns: Sequence[str] = ("**/*",)) -> str:
    """Order-independent digest of a directory's file contents and names."""
    entries: list[str] = []
    for pattern in patterns:
        for path in sorted(root.glob(pattern)):
            if path.is_file():
                entries.append(f"{path.relative_to(root).as_posix()}:{sha256_file(path)}")
    return sha256_bytes("\n".join(sorted(entries)).encode("utf-8"))


def relative(path: Path) -> str:
    try:
        return path.resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return str(path)


def read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise HarnessError(f"{relative(path)}: cannot load JSON: {exc}") from exc


def write_json(path: Path, value: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def minimal_env(extra: dict[str, str] | None = None) -> dict[str, str]:
    """A small deterministic environment, mirroring the protected evaluator."""
    env = {
        "PATH": os.environ.get("PATH", "/usr/bin:/bin:/usr/sbin:/sbin"),
        "HOME": os.environ.get("HOME", "/tmp"),
        "LANG": "C",
        "LC_ALL": "C",
        "TZ": "UTC",
        "SOURCE_DATE_EPOCH": "0",
        "PYTHONHASHSEED": "0",
        "PYTHONDONTWRITEBYTECODE": "1",
    }
    if extra:
        env.update(extra)
    return env


def run(
    command: Sequence[str] | str,
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    timeout: float | None = None,
    shell: bool = False,
) -> dict[str, Any]:
    """Execute a command and return a JSON-serialisable record of what happened.

    The record is evidence: it always carries the exact command, exit status,
    captured streams, and wall time, including for failures.
    """
    started = time_monotonic()
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd or ROOT),
            env=env if env is not None else minimal_env(),
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
            shell=shell,
        )
    except subprocess.TimeoutExpired as exc:
        return {
            "command": command if isinstance(command, str) else list(command),
            "cwd": relative(cwd or ROOT),
            "exit_code": None,
            "timed_out": True,
            "timeout_seconds": timeout,
            "stdout": (exc.stdout or b"").decode("utf-8", "replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or ""),
            "stderr": (exc.stderr or b"").decode("utf-8", "replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or ""),
            "wall_seconds": round(time_monotonic() - started, 6),
        }
    except OSError as exc:
        return {
            "command": command if isinstance(command, str) else list(command),
            "cwd": relative(cwd or ROOT),
            "exit_code": None,
            "timed_out": False,
            "error": str(exc),
            "stdout": "",
            "stderr": str(exc),
            "wall_seconds": round(time_monotonic() - started, 6),
        }
    return {
        "command": command if isinstance(command, str) else list(command),
        "cwd": relative(cwd or ROOT),
        "exit_code": completed.returncode,
        "timed_out": False,
        "stdout": completed.stdout,
        "stderr": completed.stderr,
        "wall_seconds": round(time_monotonic() - started, 6),
    }


def time_monotonic() -> float:
    import time

    return time.monotonic()


def tool_version(name: str, args: Sequence[str] = ("--version",)) -> dict[str, Any]:
    """Resolve a tool and its first version line, or record it as unavailable."""
    path = shutil.which(name)
    if path is None:
        return {"name": name, "path": None, "version": None, "available": False}
    record = run([path, *args], timeout=60)
    text = (record.get("stdout") or "") + (record.get("stderr") or "")
    lines = [line.strip() for line in text.splitlines() if line.strip()]
    return {
        "name": name,
        "path": path,
        "version": lines[0] if lines else None,
        "available": True,
    }


def git_state() -> dict[str, Any]:
    head = run(["git", "rev-parse", "HEAD"], timeout=30)
    status = run(["git", "status", "--porcelain"], timeout=60)
    commit = (head.get("stdout") or "").strip() or None
    dirty_lines = [line for line in (status.get("stdout") or "").splitlines() if line.strip()]
    return {
        "commit": commit,
        "clean": head.get("exit_code") == 0 and not dirty_lines,
        "dirty_entries": len(dirty_lines),
        "available": head.get("exit_code") == 0,
    }


def assert_not_protected(path: Path) -> None:
    """Refuse to write inside the protected judge or ground-truth roots."""
    try:
        parts = path.resolve().relative_to(ROOT).parts
    except ValueError:
        return
    if parts and parts[0] in PROTECTED_ROOTS:
        raise HarnessError(
            f"{relative(path)}: the harness never writes inside protected root {parts[0]}/"
        )


def flatten(items: Iterable[Iterable[Any]]) -> list[Any]:
    return [item for group in items for item in group]
