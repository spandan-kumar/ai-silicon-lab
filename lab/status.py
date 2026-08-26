#!/usr/bin/env python3
"""Fast, honest health report for the laboratory itself."""

from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
from typing import Any


ROOT = Path(__file__).resolve().parents[1]


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def run(command: list[str], timeout: float = 30.0) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command, cwd=ROOT, capture_output=True, text=True, timeout=timeout, check=False
    )


def tool_version(name: str) -> str | None:
    path = shutil.which(name)
    if path is None:
        return None
    try:
        completed = run([path, "--version"])
    except (OSError, subprocess.SubprocessError):
        return path
    line = (completed.stdout or completed.stderr).splitlines()
    return line[0].strip() if line else path


def rtl_smoke() -> tuple[bool, str]:
    verilator = shutil.which("verilator")
    if verilator is None:
        return False, "verilator unavailable"
    # Verilator's generated GNU Makefile rejects paths containing spaces;
    # use the system temporary directory rather than the repository path.
    with tempfile.TemporaryDirectory(prefix="aisl-verilator-") as directory:
        work = Path(directory)
        source = work / "top.sv"
        harness = work / "sim.cpp"
        source.write_text(
            "module top(input logic clk, input logic rst, output logic [3:0] q);\n"
            "always_ff @(posedge clk) if (rst) q <= 4'd0; else q <= q + 4'd1;\n"
            "endmodule\n",
            encoding="utf-8",
        )
        harness.write_text(
            '#include "Vtop.h"\n'
            '#include "verilated.h"\n'
            'int main() {\n'
            '  VerilatedContext context; Vtop top{&context};\n'
            '  top.rst = 1; top.clk = 0; top.eval();\n'
            '  top.clk = 1; top.eval(); top.clk = 0; top.eval();\n'
            '  top.rst = 0;\n'
            '  for (int i = 0; i < 3; ++i) { top.clk = 1; top.eval(); top.clk = 0; top.eval(); }\n'
            '  return top.q == 3 ? 0 : 1;\n'
            '}\n',
            encoding="utf-8",
        )
        obj = work / "obj"
        try:
            built = run(
                [verilator, "--cc", "--exe", "--build", "--quiet", "--top-module", "top",
                 str(source), str(harness), "-Mdir", str(obj)],
                timeout=60.0,
            )
            binary = obj / "Vtop"
            if built.returncode != 0 or not binary.is_file():
                detail = (built.stderr or built.stdout).strip().splitlines()
                return False, detail[-1] if detail else "verilator build failed"
            executed = subprocess.run([str(binary)], cwd=ROOT, capture_output=True, text=True, timeout=10.0)
            return (executed.returncode == 0, "Verilator counter smoke test" if executed.returncode == 0 else "Verilator smoke executable failed")
        except (OSError, subprocess.SubprocessError) as exc:
            return False, str(exc)


def yosys_smoke() -> tuple[bool, str]:
    yosys = shutil.which("yosys")
    if yosys is None:
        return False, "yosys unavailable"
    with tempfile.TemporaryDirectory(prefix="aisl-yosys-") as directory:
        source = Path(directory) / "top.sv"
        source.write_text(
            "module top(input clk, input rst, output reg [3:0] q);\n"
            "always @(posedge clk) if (rst) q <= 0; else q <= q + 1;\n"
            "endmodule\n",
            encoding="utf-8",
        )
        completed = run([yosys, "-q", "-p", f"read_verilog -sv {source}; synth -top top; stat"], timeout=30.0)
        return (completed.returncode == 0, "Yosys synthesis smoke test" if completed.returncode == 0 else "Yosys synthesis failed")


def trusted_integrity() -> tuple[bool, str]:
    manifest_path = ROOT / "ground_truth" / "trusted-manifest.json"
    if not manifest_path.is_file():
        return False, "trusted manifest is missing"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        files = manifest["files"]
        for relative, expected in files.items():
            path = ROOT / relative
            if not path.is_file() or sha256_file(path) != expected:
                return False, f"integrity mismatch: {relative}"
        return True, f"{len(files)} protected files verified"
    except (OSError, json.JSONDecodeError, KeyError, TypeError) as exc:
        return False, str(exc)


def protection_state() -> tuple[bool, str]:
    try:
        completed = subprocess.run(
            ["ls", "-ldO", str(ROOT / "lab"), str(ROOT / "ground_truth")],
            capture_output=True, text=True, check=False,
        )
        text = completed.stdout + completed.stderr
        if "uchg" in text or " schg" in text:
            return True, "macOS immutable filesystem flag detected"
    except OSError:
        pass
    lsattr = shutil.which("lsattr")
    if lsattr:
        try:
            completed = subprocess.run([lsattr, "-d", str(ROOT / "lab"), str(ROOT / "ground_truth")], capture_output=True, text=True, check=False)
            if any(line.startswith("----i") for line in completed.stdout.splitlines()):
                return True, "Linux immutable filesystem flag detected"
        except OSError:
            pass
    return False, "lab/ and ground_truth/ are not filesystem-immutable"


def check_layout() -> tuple[bool, str]:
    required = (
        "workspace/rtl", "workspace/firmware", "workspace/software",
        "workspace/experiments", "workspace/tools", "workspace/docs",
        "lab", "ground_truth", "runs", "results", "docs",
    )
    missing = [path for path in required if not (ROOT / path).is_dir()]
    return (not missing, "layout complete" if not missing else "missing: " + ", ".join(missing))


def core_report() -> list[dict[str, Any]]:
    checks: list[dict[str, Any]] = []
    def add(name: str, ok: bool, detail: str) -> None:
        checks.append({"name": name, "ok": bool(ok), "detail": detail})

    layout_ok, layout_detail = check_layout()
    add("repository", layout_ok, layout_detail)
    add("compiler", any(shutil.which(name) for name in ("clang", "cc", "gcc")), tool_version("clang") or "no C compiler")
    python_version = tuple(int(part) for part in sys.version_info[:2])
    add("Python runtime", python_version >= (3, 8), sys.version.split()[0])
    rtl_ok, rtl_detail = rtl_smoke()
    add("RTL simulation", rtl_ok, rtl_detail)
    add("deterministic test infrastructure", (ROOT / "ground_truth/benchmark/input.events").is_file(), "input schedule present")

    benchmark_ok = False
    benchmark_detail = "benchmark unavailable"
    try:
        benchmark = json.loads((ROOT / "ground_truth/benchmark/benchmark.json").read_text(encoding="utf-8"))
        oracle = ROOT / benchmark["oracle_file"]
        video = benchmark["video"]
        execution = benchmark["execution"]
        expected_size = int(video["frame_bytes"]) * int(execution["capture_frames"])
        benchmark_ok = oracle.is_file() and oracle.stat().st_size == expected_size
        benchmark_detail = f"{execution['capture_frames']} frames, {video['width']}x{video['height']} RGB888"
    except (OSError, json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        benchmark_detail = str(exc)
    add("framebuffer oracle", benchmark_ok, benchmark_detail)

    wad = ROOT / "ground_truth/assets/freedoom1.wad"
    reference = ROOT / "ground_truth/reference/bin/doomgeneric-headless"
    doom_ok = wad.is_file() and reference.is_file() and os.access(reference, os.X_OK)
    add("DOOM reference", doom_ok, "Freedoom IWAD and headless engine present" if doom_ok else "reference binary or IWAD unavailable")
    evaluator = ROOT / "ground_truth/evaluator/evaluate.py"
    evaluator_ok = evaluator.is_file() and (ROOT / "lab/evaluate").is_file()
    add("evaluator", evaluator_ok, "trusted evaluator and entry point present" if evaluator_ok else "evaluator unavailable")
    add("experiment recording", os.access(ROOT / "runs", os.W_OK), "runs/ is writable" if os.access(ROOT / "runs", os.W_OK) else "runs/ is not writable")
    git_ok = git_run_ok()
    add("git reproducibility", git_ok, "Git repository has a commit" if git_ok else "no committed Git revision")
    protection_ok, protection_detail = protection_state()
    add("ground-truth protection", protection_ok, protection_detail)
    integrity_ok, integrity_detail = trusted_integrity()
    add("trusted-file integrity", integrity_ok, integrity_detail)
    return checks


def git_run_ok() -> bool:
    try:
        completed = run(["git", "rev-parse", "HEAD"])
        return completed.returncode == 0 and bool(completed.stdout.strip())
    except (OSError, subprocess.SubprocessError):
        return False


def optional_report() -> list[dict[str, Any]]:
    groups = {
        "Verilog alternate simulator": ("iverilog", "vvp"),
        "waveform viewer": ("gtkwave",),
        "FPGA synthesis/P&R": ("nextpnr", "vivado", "quartus_sh"),
        "ASIC implementation": ("openroad", "openlane"),
        "CPU emulation": ("qemu-system-x86_64", "qemu-system-riscv64"),
        "RISC-V cross compiler": ("riscv64-unknown-elf-gcc",),
        "ARM embedded cross compiler": ("arm-none-eabi-gcc",),
        "Rust toolchain": ("rustc", "cargo"),
        "physical FPGA": (),
    }
    result = []
    for name, commands in groups.items():
        if name == "physical FPGA":
            result.append({"name": name, "available": False, "detail": "none detected during setup"})
            continue
        found = [f"{command}: {shutil.which(command)}" for command in commands if shutil.which(command)]
        result.append({"name": name, "available": bool(found), "detail": "; ".join(found) if found else "unavailable"})
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args()
    core = core_report()
    optional = optional_report()
    report = {"status": "pass" if all(item["ok"] for item in core) else "fail", "core": core, "optional": optional}
    if args.json:
        print(json.dumps(report, sort_keys=True))
    else:
        print("AI Silicon Lab")
        for item in core:
            print(f"[{'PASS' if item['ok'] else 'FAIL'}] {item['name']}: {item['detail']}")
        print("\nOptional capabilities:")
        for item in optional:
            print(f"[{'PASS' if item['available'] else 'UNAVAILABLE'}] {item['name']}: {item['detail']}")
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
