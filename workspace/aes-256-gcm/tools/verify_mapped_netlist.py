#!/usr/bin/env python3
"""Run the complete GCM corpus against one Nangate45 mapped netlist."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
from pathlib import Path

from fetch_nangate45 import EXPECTED_SHA256
from run_synthesis import CONFIGURATIONS


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIBERTY = (
    ROOT / "build" / "technology" / "nangate45" /
    "NangateOpenCellLibrary_typical.lib"
)
HARNESS_DEFINES = {
    "iterative-1r1b": "ITERATIVE",
    "unrolled-2r8b": None,
    "balanced-1r8b": "BALANCED",
    "wide-2r16b": "WIDE",
    "ultrawide-2r32b": "ULTRAWIDE",
    "balanced-wide-1r16b": "BALANCED_WIDE",
    "balanced-ultrawide-1r32b": "BALANCED_ULTRAWIDE",
    "balanced-xwide-1r64b": "BALANCED_XWIDE",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> Path:
    try:
        return path.resolve().relative_to(ROOT)
    except ValueError as error:
        raise SystemExit(f"verification path must be under {ROOT}: {path}") from error


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--synthesis-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--liberty", type=Path, default=DEFAULT_LIBERTY)
    parser.add_argument("--architecture", choices=CONFIGURATIONS, required=True)
    args = parser.parse_args()
    synthesis_dir = args.synthesis_dir.resolve()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    liberty = args.liberty.resolve()
    if not liberty.exists() or sha256(liberty) != EXPECTED_SHA256:
        raise SystemExit("pinned Nangate45 Liberty file missing or corrupt")
    yosys = shutil.which("yosys")
    verilator = shutil.which("verilator")
    if yosys is None or verilator is None:
        raise SystemExit("yosys and verilator are required")

    configuration = CONFIGURATIONS[args.architecture]
    stem = str(configuration["stem"])
    netlist = synthesis_dir / f"{stem}-netlist.v"
    if not netlist.exists():
        raise SystemExit(f"mapped netlist missing: {netlist}")
    cell_model = output_dir / "nangate45-functional-cells.v"
    subprocess.run(
        [
            yosys, "-q", "-p",
            (
                f"read_liberty -ignore_miss_func -ignore_miss_data_latch {relative(liberty)}; "
                f"write_verilog -noattr {relative(cell_model)}"
            ),
        ],
        check=True,
        cwd=ROOT,
    )

    with tempfile.TemporaryDirectory(prefix="aisl-gate-verify-") as temporary:
        temp = Path(temporary)
        harness = temp / "gcm_harness.cpp"
        vectors = temp / "gcm_vectors.h"
        shutil.copy2(ROOT / "tests" / "gcm_harness.cpp", harness)
        shutil.copy2(ROOT / "tests" / "gcm_vectors.h", vectors)
        object_dir = temp / "obj"
        command = [
            verilator, "--cc", "--exe", "--build", "--sv", "-Wall",
            "-Wno-DECLFILENAME", "-Wno-UNUSEDSIGNAL", "-Wno-UNDRIVEN",
            "--Mdir", str(object_dir), "--top-module", "aes_gcm_core",
        ]
        define = HARNESS_DEFINES[args.architecture]
        cflags = f"-D{define} -O3" if define else "-O3"
        command += [
            "-CFLAGS", cflags,
            "-MAKEFLAGS", "OPT_FAST=-O3 OPT_GLOBAL=-O3",
            str(netlist), str(cell_model), str(harness),
        ]
        subprocess.run(command, check=True, cwd=ROOT)
        completed = subprocess.run(
            [str(object_dir / "Vaes_gcm_core")],
            check=True,
            capture_output=True,
            text=True,
        )

    log_path = output_dir / f"gcm-{stem}.txt"
    log_path.write_text(completed.stdout)
    expected = f"GCM RTL: PASS architecture={args.architecture} corpus_operations=1038"
    if expected not in completed.stdout:
        raise SystemExit("mapped-netlist corpus result is incomplete")
    summary = {
        "schema_version": 1,
        "architecture": args.architecture,
        "flow": "verilator-nangate45-functional-netlist-v1",
        "corpus_operations": 1038,
        "status": "pass",
        "liberty_sha256": sha256(liberty),
        "netlist_sha256": sha256(netlist),
        "functional_cell_model_sha256": sha256(cell_model),
        "harness_sha256": sha256(ROOT / "tests" / "gcm_harness.cpp"),
        "vectors_sha256": sha256(ROOT / "tests" / "gcm_vectors.h"),
        "log_sha256": sha256(log_path),
    }
    summary_path = output_dir / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(
        f"gate-verify: PASS architecture={args.architecture} "
        f"corpus_operations=1038 netlist_sha256={summary['netlist_sha256']}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
