#!/usr/bin/env python3
"""Verify and summarize a completed OrangeCrab gateware build."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


TARGET = Path(__file__).resolve().parent
REPOSITORY = TARGET.parents[2]
DEFAULT_BUILD = TARGET / "build"
EXPECTED_YOSYS_WARNINGS = {
    "Wire VexRiscv.\\IBusSimplePlugin_rspJoin_fetchRsp_isRvc is used but has no driver.",
    "Wire VexRiscv.\\CsrPlugin_mtvec_mode [1] is used but has no driver.",
    "Wire VexRiscv.\\CsrPlugin_mtvec_mode [0] is used but has no driver.",
}
HASHED_ARTIFACTS = {
    "bitstream": "gateware/gsd_orangecrab.bit",
    "trellis_config": "gateware/gsd_orangecrab.config",
    "routed_netlist": "gateware/gsd_orangecrab.json",
    "csr_csv": "csr.csv",
    "csr_json": "csr.json",
    "bios": "software/bios/bios.bin",
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


def command_output(arguments: list[str | Path]) -> str:
    return subprocess.check_output([str(argument) for argument in arguments], text=True).strip()


def parse_timing(log: str) -> dict[str, dict[str, float | str]]:
    matches = re.findall(
        r"Info: Max frequency for clock\s+'([^']+)':\s+([0-9.]+) MHz "
        r"\((PASS|FAIL) at ([0-9.]+) MHz\)",
        log,
    )
    timing = {
        clock: {
            "maximum_mhz": float(maximum),
            "constraint_mhz": float(constraint),
            "status": status.lower(),
        }
        for clock, maximum, status, constraint in matches
    }
    sys_clock = timing.get("$glbnet$sys_clk")
    require(sys_clock is not None, "final system-clock timing result is missing")
    require(sys_clock["constraint_mhz"] == 48.0, "system-clock constraint is not 48 MHz")
    require(sys_clock["status"] == "pass", "routed system clock fails timing")
    return timing


def parse_resources(log: str) -> dict[str, dict[str, int]]:
    resources: dict[str, dict[str, int]] = {}
    for name in ("DP16KD", "MULT18X18D", "TRELLIS_FF", "TRELLIS_COMB"):
        match = re.search(rf"Info:\s+{name}:\s+([0-9]+)/\s*([0-9]+)\s+([0-9]+)%", log)
        require(match is not None, f"resource count is missing for {name}")
        used, available, percent = (int(value) for value in match.groups())
        resources[name] = {"used": used, "available": available, "reported_percent": percent}
    return resources


def verify_bios(build: Path, csr_header: str) -> dict[str, object]:
    for macro in (
        "CSR_DDRCTRL_INIT_DONE_ADDR",
        "CSR_DDRCTRL_INIT_ERROR_ADDR",
    ):
        require(macro in csr_header, f"BIOS header lacks {macro}")
    objdump = (
        REPOSITORY
        / ".aisl/toolchains/xpack-riscv-none-elf-gcc-14.2.0-3/bin/riscv-none-elf-objdump"
    )
    require(objdump.is_file(), f"RISC-V objdump is missing: {objdump}")
    disassembly = command_output([objdump, "-d", build / "software/bios/bios.elf"])
    for marker in ("<sdram_init>", "<memtest>", "f0001000"):
        require(marker in disassembly, f"BIOS DDR-init proof lacks {marker}")
    sdram_body_match = re.search(
        r"<sdram_init>:\n(?P<body>.*?)(?=\n[0-9a-f]+ <[^>]+>:)",
        disassembly,
        flags=re.DOTALL,
    )
    require(sdram_body_match is not None, "could not isolate BIOS sdram_init disassembly")
    sdram_body = sdram_body_match.group("body")
    require(re.search(r"\bsw\s+\w+,4\(s6\)", sdram_body) is not None, "BIOS never writes init_error")
    require(re.search(r"\bsw\s+\w+,0\(s6\)", sdram_body) is not None, "BIOS never writes init_done")
    return {
        "sdram_init_present": True,
        "destructive_memtest_present": True,
        "init_done_csr_address": "0xf0001000",
        "init_error_csr_address": "0xf0001004",
    }


def verify(build: Path, build_seconds: float | None) -> dict[str, object]:
    log_path = build / "litex.log"
    script_path = build / "gateware/build_gsd_orangecrab.sh"
    csr_csv_path = build / "csr.csv"
    csr_header_path = build / "software/include/generated/csr.h"
    for path in (log_path, script_path, csr_csv_path, csr_header_path):
        require(path.is_file(), f"required build artifact is missing: {path}")

    log = log_path.read_text(encoding="utf-8", errors="replace")
    build_script = script_path.read_text(encoding="utf-8")
    csr_csv = csr_csv_path.read_text(encoding="utf-8")
    csr_header = csr_header_path.read_text(encoding="utf-8")

    require("--timing-allow-fail" not in build_script, "nextpnr timing failures are permitted")
    require("--seed 1" in build_script, "nextpnr seed is not pinned to 1")
    require("--nextpnr-timingstrict" in log, "strict nextpnr timing was not requested")
    require(
        "constraining clock net 'clk48' to 48.00 MHz" in log,
        "48 MHz clock constraint is missing",
    )
    require("Found and reported 0 problems." in log, "post-synthesis Yosys check did not pass")
    require("Warnings: 3 unique messages, 3 total" in log, "unexpected Yosys warning count")
    require("Info: Program finished normally." in log, "nextpnr did not finish normally")

    yosys_warnings = {
        match.group(1)
        for match in re.finditer(r"^Warning: (.+)$", log, flags=re.MULTILINE)
        if not match.group(1).startswith(("AIG with boxes", "The network is combinational"))
    }
    require(yosys_warnings == EXPECTED_YOSYS_WARNINGS, "unexpected synthesis warning set")
    for register_name in (
        "ddrctrl_init_done",
        "ddrctrl_init_error",
        "aisl_control_execution_cycles",
        "aisl_control_capture_pause_cycles",
    ):
        require(register_name in csr_csv, f"CSR map lacks {register_name}")
    require("csr_base,uart," not in csr_csv, "a blocking BIOS console UART is present")
    require("generation timestamp normalized" in csr_csv, "CSR timestamp was not normalized")

    hashes = {}
    for name, relative in HASHED_ARTIFACTS.items():
        path = build / relative
        require(path.is_file(), f"hashed artifact is missing: {path}")
        hashes[name] = {"bytes": path.stat().st_size, "sha256": sha256_file(path)}

    result: dict[str, object] = {
        "schema_version": 1,
        "success": True,
        "target": {
            "board": "OrangeCrab r0.2",
            "device": "LFE5U-85F-8MG285C",
            "system_clock_hz": 48_000_000,
            "external_ddr_bytes": 128 * 1024 * 1024,
        },
        "strict_timing": True,
        "timing": parse_timing(log),
        "resources": parse_resources(log),
        "post_synthesis_check_problems": 0,
        "synthesis_warnings": sorted(yosys_warnings),
        "bios_ddr_initialization": verify_bios(build, csr_header),
        "artifacts": hashes,
    }
    if build_seconds is not None:
        result["build_seconds"] = build_seconds
        result["build_seconds_source"] = "measured by /usr/bin/time -p around make gateware"
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-dir", type=Path, default=DEFAULT_BUILD)
    parser.add_argument("--build-seconds", type=float)
    args = parser.parse_args()
    result = verify(args.build_dir.resolve(), args.build_seconds)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
