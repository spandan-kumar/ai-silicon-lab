#!/usr/bin/env python3
"""Discovery and loading of experiment plugins.

An experiment joins the harness by adding `experiments/<id>/harness.json`. That
file is deliberately separate from `experiment.json`: the specification freezes
the question and acceptance contract, while the harness file says how this
repository currently executes it. A wiring change must never look like a change
to the frozen contract.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
from typing import Any

from .core import ROOT, HarnessError, read_json, relative
from .contracts import ExperimentPlugin, Workload


HARNESS_FILE = "harness.json"


def harness_path(experiment_id: str) -> Path:
    return ROOT / "experiments" / experiment_id / HARNESS_FILE


def load_manifest(experiment_id: str) -> dict[str, Any]:
    path = harness_path(experiment_id)
    if not path.is_file():
        raise HarnessError(
            f"experiment {experiment_id!r} has no {relative(path)}; "
            f"it is specified but not wired into the harness"
        )
    manifest = read_json(path)
    if not isinstance(manifest, dict):
        raise HarnessError(f"{relative(path)}: expected an object")
    if manifest.get("schema_version") != 1:
        raise HarnessError(f"{relative(path)}: schema_version must be 1")
    if manifest.get("experiment_id") != experiment_id:
        raise HarnessError(f"{relative(path)}: experiment_id does not match its directory")
    for key in ("plugin", "suites", "gates"):
        if key not in manifest:
            raise HarnessError(f"{relative(path)}: missing required key {key!r}")
    return manifest


def available() -> list[str]:
    directory = ROOT / "experiments"
    return sorted(
        child.name
        for child in directory.iterdir()
        if child.is_dir() and (child / HARNESS_FILE).is_file()
    )


def load_plugin(experiment_id: str, manifest: dict[str, Any]) -> ExperimentPlugin:
    relative_path = manifest["plugin"]
    if not isinstance(relative_path, str) or Path(relative_path).is_absolute():
        raise HarnessError("harness.json: plugin must be a repository-relative path")
    if ".." in Path(relative_path).parts:
        raise HarnessError("harness.json: plugin path may not escape the repository")
    module_path = ROOT / relative_path
    if not module_path.is_file():
        raise HarnessError(f"plugin module {relative_path} does not exist")

    entry = manifest.get("entry", "create_plugin")
    module_name = f"aisl_plugin_{experiment_id.replace('-', '_')}"
    spec = importlib.util.spec_from_file_location(module_name, module_path)
    if spec is None or spec.loader is None:
        raise HarnessError(f"cannot import plugin module {relative_path}")
    module = importlib.util.module_from_spec(spec)
    # Let the plugin import helpers from its own directory, the way the
    # existing verification scripts do.
    sys.path.insert(0, str(module_path.parent))
    sys.modules[module_name] = module
    try:
        spec.loader.exec_module(module)
    except Exception as exc:  # plugin import failure is evidence, not a crash
        raise HarnessError(f"{relative_path}: plugin import failed: {exc!r}") from exc
    finally:
        sys.path.remove(str(module_path.parent))

    factory = getattr(module, entry, None)
    if factory is None:
        raise HarnessError(f"{relative_path}: no entry point {entry!r}")
    plugin = factory()
    if not isinstance(plugin, ExperimentPlugin):
        raise HarnessError(
            f"{relative_path}: {entry}() must return an ExperimentPlugin subclass instance"
        )
    if plugin.experiment_id != experiment_id:
        raise HarnessError(
            f"{relative_path}: plugin.experiment_id {plugin.experiment_id!r} "
            f"does not match {experiment_id!r}"
        )
    return plugin


def suite_workloads(manifest: dict[str, Any], plugin: ExperimentPlugin) -> list[Workload]:
    """Intersect declared suites with the workloads the plugin actually offers.

    A suite that names a workload the plugin does not implement is an error. The
    harness refuses to quietly run a smaller suite than the one declared.
    """
    offered = {workload.id: workload for workload in plugin.workloads()}
    selected: list[Workload] = []
    for index, suite in enumerate(manifest["suites"]):
        if not isinstance(suite, dict):
            raise HarnessError(f"harness.json: suites[{index}] must be an object")
        workload_id = suite.get("workload")
        if workload_id not in offered:
            raise HarnessError(
                f"harness.json: suites[{index}] names workload {workload_id!r}, "
                f"which the plugin does not provide"
            )
        selected.append(offered[workload_id])
    return selected
