#!/usr/bin/env python3
"""Synthesize the AES-GCM architecture sweep with the same generic flow."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import time
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
CONFIGURATIONS = {
    "iterative-1r1b": {
        "arch": 0,
        "stem": "iterative",
        "sources": ["rtl/aes_gcm_core.sv", "rtl/aes256_iterative_enc.sv", "rtl/ghash_iterative.sv"],
    },
    "unrolled-2r8b": {
        "arch": 1,
        "stem": "parallel",
        "sources": ["rtl/aes_gcm_core.sv", "rtl/aes256_parallel_enc.sv", "rtl/ghash_parallel.sv"],
    },
    "balanced-1r8b": {
        "arch": 2,
        "stem": "balanced",
        "sources": ["rtl/aes_gcm_core.sv", "rtl/aes256_iterative_enc.sv", "rtl/ghash_parallel.sv"],
    },
    "wide-2r16b": {
        "arch": 3,
        "stem": "wide",
        "sources": ["rtl/aes_gcm_core.sv", "rtl/aes256_parallel_enc.sv", "rtl/ghash_parallel.sv"],
    },
    "ultrawide-2r32b": {
        "arch": 4,
        "stem": "ultrawide",
        "sources": ["rtl/aes_gcm_core.sv", "rtl/aes256_parallel_enc.sv", "rtl/ghash_parallel.sv"],
    },
    "balanced-wide-1r16b": {
        "arch": 5,
        "stem": "balanced_wide",
        "sources": ["rtl/aes_gcm_core.sv", "rtl/aes256_iterative_enc.sv", "rtl/ghash_parallel.sv"],
    },
    "balanced-ultrawide-1r32b": {
        "arch": 6,
        "stem": "balanced_ultrawide",
        "sources": ["rtl/aes_gcm_core.sv", "rtl/aes256_iterative_enc.sv", "rtl/ghash_parallel.sv"],
    },
    "balanced-xwide-1r64b": {
        "arch": 7,
        "stem": "balanced_xwide",
        "sources": ["rtl/aes_gcm_core.sv", "rtl/aes256_iterative_enc.sv", "rtl/ghash_parallel.sv"],
    },
}

# Exploratory branches are kept out of the frozen baseline report collector.
EXPLORATORY_CONFIGURATIONS = {
    "karatsuba-1r2c": {
        "arch": 8,
        "stem": "karatsuba",
        "sources": ["rtl/aes_gcm_core.sv", "rtl/aes256_iterative_enc.sv", "rtl/aes256_parallel_enc.sv", "rtl/ghash_karatsuba.sv"],
    },
}
ALL_CONFIGURATIONS = {**CONFIGURATIONS, **EXPLORATORY_CONFIGURATIONS}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--architecture", action="append", choices=ALL_CONFIGURATIONS)
    args = parser.parse_args()
    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    yosys = shutil.which("yosys")
    if yosys is None:
        raise SystemExit("yosys is required")
    version = subprocess.run(
        [yosys, "-V"], check=True, capture_output=True, text=True
    ).stdout.strip()
    summary: dict[str, object] = {
        "schema_version": 1,
        "flow": "generic-yosys-synth-v1",
        "tool": version,
        "target": "generic Yosys Boolean-cell netlist; no technology mapping",
        "timing": None,
        "power": None,
        "architectures": {},
    }
    selected = set(args.architecture or ALL_CONFIGURATIONS)
    for name, configuration in ALL_CONFIGURATIONS.items():
        if name not in selected:
            continue
        stem = configuration["stem"]
        stat_path = output_dir / f"{stem}-stat.json"
        netlist_path = output_dir / f"{stem}-netlist.json"
        log_path = output_dir / f"{stem}.log"
        stat_argument = stat_path.relative_to(ROOT)
        netlist_argument = netlist_path.relative_to(ROOT)
        source_text = " ".join(configuration["sources"])
        script = (
            f"read_verilog -sv -Irtl {source_text}; "
            f"chparam -set ARCH {configuration['arch']} aes_gcm_core; "
            "hierarchy -top aes_gcm_core; synth -top aes_gcm_core; "
            f"tee -o {stat_argument} stat -json; write_json {netlist_argument}"
        )
        started = time.monotonic()
        subprocess.run(
            [yosys, "-q", "-l", str(log_path), "-p", script], check=True, cwd=ROOT
        )
        elapsed = time.monotonic() - started
        statistics = json.loads(stat_path.read_text())
        design = statistics["design"]
        summary["architectures"][name] = {
            "arch_parameter": configuration["arch"],
            "sources": configuration["sources"] + ["rtl/aes_functions.svh"],
            "elapsed_seconds": round(elapsed, 6),
            "elapsed_source": "measured-monotonic-clock",
            "generic_cell_count": design["num_cells"],
            "generic_cell_types": design["num_cells_by_type"],
            "stat_sha256": sha256(stat_path),
            "netlist_sha256": sha256(netlist_path),
            "log_sha256": sha256(log_path),
        }
        print(f"synthesis: PASS architecture={name} generic_cells={design['num_cells']} elapsed_seconds={elapsed:.3f}")
    (output_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
