#!/usr/bin/env python3
"""Toolchain capability discovery and environment snapshots.

`lab/status` reports the health of the protected laboratory. This module
answers a different question: does the host have what the *selected experiment*
declares it needs, and what exact versions produced a given result.
"""

from __future__ import annotations

from typing import Any

from .core import ROOT, read_json, relative, tool_version, utc_now, write_json
from . import plugins


# Version probes for tools whose --version flag is non-standard.
VERSION_ARGS: dict[str, tuple[str, ...]] = {
    "yosys": ("-V",),
    "sv2v": ("--numeric-version",),
    "docker": ("--version",),
}

INSTALL_HINTS: dict[str, str] = {
    "verilator": "brew install verilator",
    "yosys": "brew install yosys",
    "sv2v": "brew install sv2v",
    "iverilog": "brew install icarus-verilog",
    "gtkwave": "brew install --cask gtkwave",
    "cmake": "brew install cmake",
    "ninja": "brew install ninja",
    "riscv-none-elf-gcc": "./workspace/tools/bootstrap-riscv-toolchain",
    "docker": "install Docker Desktop",
}


def probe(name: str) -> dict[str, Any]:
    return tool_version(name, VERSION_ARGS.get(name, ("--version",)))


def snapshot(names: list[str]) -> dict[str, Any]:
    tools = [probe(name) for name in sorted(set(names))]
    return {
        "schema_version": 1,
        "captured_utc": utc_now(),
        "tools": tools,
        "available": [tool["name"] for tool in tools if tool["available"]],
        "missing": [tool["name"] for tool in tools if not tool["available"]],
    }


def required_tools(experiment_id: str) -> dict[str, list[str]]:
    """Tools an experiment's harness.json declares, split by necessity."""
    manifest = plugins.load_manifest(experiment_id)
    requirements = manifest.get("requirements", {})
    return {
        "required": list(requirements.get("required", [])),
        "optional": list(requirements.get("optional", [])),
    }


def check(experiment_id: str | None = None) -> dict[str, Any]:
    if experiment_id:
        requirements = required_tools(experiment_id)
    else:
        requirements = {
            "required": ["python3", "git", "cc"],
            "optional": sorted(INSTALL_HINTS),
        }
    names = requirements["required"] + requirements["optional"]
    result = snapshot(names)
    missing_required = [
        name for name in requirements["required"] if name in result["missing"]
    ]
    result["experiment_id"] = experiment_id
    result["required"] = requirements["required"]
    result["optional"] = requirements["optional"]
    result["missing_required"] = missing_required
    result["ok"] = not missing_required
    result["hints"] = {
        name: INSTALL_HINTS[name] for name in result["missing"] if name in INSTALL_HINTS
    }
    return result


def record(experiment_id: str | None, path: str | None = None) -> str:
    result = check(experiment_id)
    target = ROOT / (
        path or f".aisl/harness/{experiment_id or 'lab'}/environment.json"
    )
    write_json(target, result)
    return relative(target)
