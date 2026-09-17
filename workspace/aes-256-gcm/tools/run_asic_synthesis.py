#!/usr/bin/env python3
"""Map the architecture sweep to the pinned Nangate45 standard-cell library."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
import subprocess
import time
from pathlib import Path

from fetch_nangate45 import EXPECTED_SHA256
from run_synthesis import ALL_CONFIGURATIONS, CONFIGURATIONS


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_LIBERTY = (
    ROOT / "build" / "technology" / "nangate45" /
    "NangateOpenCellLibrary_typical.lib"
)
CONSTRAINTS = ROOT / "asic" / "nangate45.constr"
TIMING_RE = re.compile(
    r"Area\s*=\s*([0-9.]+).*Delay\s*=\s*([0-9.]+)\s*ps"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def relative(path: Path) -> Path:
    try:
        return path.resolve().relative_to(ROOT)
    except ValueError as error:
        raise SystemExit(f"ASIC flow path must be under {ROOT}: {path}") from error


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--liberty", type=Path, default=DEFAULT_LIBERTY)
    parser.add_argument("--architecture", action="append", choices=ALL_CONFIGURATIONS)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    liberty = args.liberty.resolve()
    if not liberty.exists() or sha256(liberty) != EXPECTED_SHA256:
        raise SystemExit("pinned Nangate45 Liberty file missing or corrupt; run tools/fetch_nangate45.py")
    yosys = shutil.which("yosys")
    if yosys is None:
        raise SystemExit("yosys is required")
    version = subprocess.run(
        [yosys, "-V"], check=True, capture_output=True, text=True
    ).stdout.strip()
    liberty_argument = relative(liberty)
    constraints_argument = relative(CONSTRAINTS)
    summary: dict[str, object] = {
        "schema_version": 1,
        "flow": "yosys-abc-nangate45-typical-v1",
        "tool": version,
        "library": {
            "name": "NangateOpenCellLibrary",
            "technology_nm": 45,
            "corner": "typical",
            "voltage_v": 1.1,
            "temperature_c": 25,
            "sha256": EXPECTED_SHA256,
        },
        "constraints": {
            "input_driver": "BUF_X1",
            "output_load_ff": 5.0,
            "wire_load": "none",
            "file_sha256": sha256(CONSTRAINTS),
        },
        "scope": (
            "flattened RTL-to-standard-cell synthesis; ABC pre-layout combinational "
            "delay, no floorplan, placement, routing, extracted parasitics, clock tree, "
            "power, DRC, or signoff"
        ),
        "architectures": {},
    }
    selected = set(args.architecture or ALL_CONFIGURATIONS)
    for name, configuration in ALL_CONFIGURATIONS.items():
        if name not in selected:
            continue
        stem = str(configuration["stem"])
        stat_path = output_dir / f"{stem}-stat.json"
        netlist_path = output_dir / f"{stem}-netlist.v"
        log_path = output_dir / f"{stem}.log"
        source_text = " ".join(configuration["sources"])
        script = (
            f"read_verilog -sv -Irtl {source_text}; "
            f"chparam -set ARCH {configuration['arch']} aes_gcm_core; "
            "hierarchy -top aes_gcm_core; synth -top aes_gcm_core -flatten; "
            f"dfflibmap -liberty {liberty_argument}; "
            f"abc -liberty {liberty_argument} -constr {constraints_argument}; clean; "
            f"tee -o {relative(stat_path)} stat -json -liberty {liberty_argument}; "
            f"write_verilog -noattr {relative(netlist_path)}"
        )
        started = time.monotonic()
        subprocess.run(
            [yosys, "-q", "-l", str(log_path), "-p", script], check=True, cwd=ROOT
        )
        elapsed = time.monotonic() - started
        statistics = json.loads(stat_path.read_text())["design"]
        timing_matches = TIMING_RE.findall(log_path.read_text())
        if len(timing_matches) != 1:
            raise SystemExit(f"expected one ABC timing result in {log_path}, found {len(timing_matches)}")
        combinational_area, delay_ps = map(float, timing_matches[0])
        internal_types = sorted(
            cell for cell in statistics["num_cells_by_type"]
            if cell.startswith("$") and cell != "$scopeinfo"
        )
        if internal_types:
            raise SystemExit(f"unmapped internal cells in {name}: {internal_types}")
        result = {
            "arch_parameter": configuration["arch"],
            "sources": configuration["sources"] + ["rtl/aes_functions.svh"],
            "elapsed_seconds": round(elapsed, 6),
            "elapsed_source": "measured-monotonic-clock",
            "mapped_cell_count": statistics["num_cells"] - statistics["num_cells_by_type"].get("$scopeinfo", 0),
            "mapped_cell_types": {
                key: value for key, value in statistics["num_cells_by_type"].items()
                if key != "$scopeinfo"
            },
            "total_cell_area_um2": statistics["area"],
            "sequential_cell_area_um2": statistics["sequential_area"],
            "abc_combinational_area_um2": combinational_area,
            "critical_combinational_delay_ps": delay_ps,
            "prelayout_fmax_mhz": round(1_000_000.0 / delay_ps, 6),
            "stat_sha256": sha256(stat_path),
            "netlist_sha256": sha256(netlist_path),
            "log_sha256": sha256(log_path),
        }
        summary["architectures"][name] = result
        print(
            f"asic-synthesis: PASS architecture={name} "
            f"area_um2={statistics['area']:.3f} delay_ps={delay_ps:.2f} "
            f"prelayout_fmax_mhz={result['prelayout_fmax_mhz']:.3f}"
        )
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, sort_keys=True) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
