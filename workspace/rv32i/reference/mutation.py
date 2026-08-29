#!/usr/bin/env python3
"""Mutation testing: measure what the verification loop can actually catch.

A passing test suite reports the absence of observed failures. It does not
report the suite's power to observe them. This module supplies the missing
measurement: it injects a catalogue of realistic single-point defects into the
RTL, runs the loop against each mutant, and reports the fraction killed and
how many programs each kill took.

Mutation score is the number the workflow is tuned against. A stimulus change
that raises coverage but not mutation score has not been shown to help, and a
change that raises both has been.

Each mutation is a defect a person could plausibly write: a dropped mask, a
signed comparison where an unsigned one belongs, a swapped immediate field, a
sign extension that became a zero extension.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import time
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
DESIGNS = {
    "multicycle": {
        "rtl": ROOT / "workspace" / "rv32i" / "rtl" / "rv32i_core.sv",
        "tb": ROOT / "workspace" / "rv32i" / "sim" / "tb_rv32i.cpp",
        "top": "rv32i_core",
    },
    "pipeline": {
        "rtl": ROOT / "workspace" / "rv32i" / "rtl" / "rv32i_pipe.sv",
        "tb": ROOT / "workspace" / "rv32i" / "sim" / "tb_rv32i_pipe.cpp",
        "top": "rv32i_pipe",
    },
}

sys.path.insert(0, str(HERE))


# (id, description, exact source text to find, replacement)
MUTATIONS: list[tuple[str, str, str, str]] = [
    ("jalr-no-lsb-clear", "JALR does not clear the low bit of its target",
     "pc_q <= (a + imm_i) & ~32'd1;", "pc_q <= (a + imm_i);"),
    ("blt-unsigned", "BLT compares unsigned",
     "3'b100: branch_taken = (a_signed < b_signed);", "3'b100: branch_taken = (a < b);"),
    ("bge-strict", "BGE uses strictly-greater",
     "3'b101: branch_taken = (a_signed >= b_signed);", "3'b101: branch_taken = (a_signed > b_signed);"),
    ("beq-inverted", "BEQ takes the branch when operands differ",
     "3'b000: branch_taken = (a == b);", "3'b000: branch_taken = (a != b);"),
    ("bltu-signed", "BLTU compares signed",
     "3'b110: branch_taken = (a < b);", "3'b110: branch_taken = (a_signed < b_signed);"),
    ("sltu-signed", "SLTU compares signed",
     "3'b011: alu_rr = {31'd0, (a < b)};", "3'b011: alu_rr = {31'd0, (a_signed < b_signed)};"),
    ("slt-unsigned", "SLT compares unsigned",
     "3'b010: alu_rr = {31'd0, (a_signed < b_signed)};", "3'b010: alu_rr = {31'd0, (a < b)};"),
    ("sltiu-signed", "SLTIU compares signed",
     "3'b011: alu_ri = {31'd0, (a < imm_i)};", "3'b011: alu_ri = {31'd0, (a_signed < imm_i)};"),
    ("add-sub-swapped", "ADD and SUB selected by the wrong polarity",
     "3'b000: alu_rr = (funct7[5]) ? (a - b) : (a + b);",
     "3'b000: alu_rr = (funct7[5]) ? (a + b) : (a - b);"),
    ("sra-becomes-srl", "SRA performs a logical shift",
     "3'b101: alu_rr = (funct7[5]) ? sra_by_reg : (a >> shamt_r);",
     "3'b101: alu_rr = (a >> shamt_r);"),
    ("srai-becomes-srli", "SRAI performs a logical shift",
     "3'b101: alu_ri = (funct7[5]) ? sra_by_imm : (a >> shamt_i);",
     "3'b101: alu_ri = (a >> shamt_i);"),
    ("shamt-unmasked", "register shift amount taken from the wrong bits",
     "assign shamt_r = b[4:0];", "assign shamt_r = b[5:1];"),
    ("imm-i-zero-extended", "I-immediate zero-extended instead of sign-extended",
     "assign imm_i = {{20{instruction_q[31]}}, instruction_q[31:20]};",
     "assign imm_i = {20'd0, instruction_q[31:20]};"),
    ("imm-s-zero-extended", "S-immediate zero-extended instead of sign-extended",
     "assign imm_s = {{20{instruction_q[31]}}, instruction_q[31:25], instruction_q[11:7]};",
     "assign imm_s = {20'd0, instruction_q[31:25], instruction_q[11:7]};"),
    ("imm-b-bits-swapped", "B-immediate bits 12 and 11 exchanged",
     "assign imm_b = {{19{instruction_q[31]}}, instruction_q[31], instruction_q[7],",
     "assign imm_b = {{19{instruction_q[31]}}, instruction_q[7], instruction_q[31],"),
    ("imm-j-bits-swapped", "J-immediate bit 11 and the 19:12 field exchanged",
     "assign imm_j = {{11{instruction_q[31]}}, instruction_q[31], instruction_q[19:12],\n                  instruction_q[20], instruction_q[30:21], 1'b0};",
     "assign imm_j = {{11{instruction_q[31]}}, instruction_q[31], {7'd0, instruction_q[20]},\n                  instruction_q[19:12][0], instruction_q[30:21], 1'b0};"),
    ("imm-u-not-shifted", "U-immediate placed in the low bits",
     "assign imm_u = {instruction_q[31:12], 12'd0};",
     "assign imm_u = {12'd0, instruction_q[31:12]};"),
    ("lb-zero-extended", "LB zero-extends instead of sign-extending",
     "3'b000:  load_result = {{24{load_byte[7]}}, load_byte};",
     "3'b000:  load_result = {24'd0, load_byte};"),
    ("lh-zero-extended", "LH zero-extends instead of sign-extending",
     "3'b001:  load_result = {{16{load_half[15]}}, load_half};",
     "3'b001:  load_result = {16'd0, load_half};"),
    ("lhu-sign-extended", "LHU sign-extends instead of zero-extending",
     "3'b101:  load_result = {16'd0, load_half};",
     "3'b101:  load_result = {{16{load_half[15]}}, load_half};"),
    ("load-half-lane-swapped", "LH/LHU select the wrong halfword lane",
     "assign load_half = load_offset_q[1] ? mem_rdata[31:16] : mem_rdata[15:0];",
     "assign load_half = load_offset_q[1] ? mem_rdata[15:0] : mem_rdata[31:16];"),
    ("x0-writable", "writes to x0 are not discarded",
     "if (index != 5'd0) regs_q[index] <= value;", "regs_q[index] <= value;"),
    ("x0-read-not-zero", "x0 does not read as zero",
     "assign a = (rs1 == 5'd0) ? 32'd0 : regs_q[rs1];", "assign a = regs_q[rs1];"),
    ("auipc-uses-next-pc", "AUIPC adds the immediate to pc+4",
     "write_register(rd, pc_q + imm_u);", "write_register(rd, pc_q + 32'd4 + imm_u);"),
    ("store-be-unshifted", "SB byte enable not shifted to the addressed lane",
     "store_be   = 4'b0001 << mem_offset;", "store_be   = 4'b0001;"),
    ("branch-uses-jal-imm", "branches use the J-immediate",
     "pc_q <= branch_taken ? (pc_q + imm_b) : (pc_q + 32'd4);",
     "pc_q <= branch_taken ? (pc_q + imm_j) : (pc_q + 32'd4);"),
]



# Defects specific to a pipeline. None of these can exist in the multi-cycle
# core, so the catalogue that measured that design says nothing about whether
# the loop can see them.
PIPELINE_MUTATIONS: list[tuple[str, str, str, str]] = [
    ("no-forward-mem-to-a", "operand a is not forwarded from MEM",
     "    if (mem_writes && (mem_rd == ex_rs1) && (ex_rs1 != 5'd0)) ex_a = mem_result_q;\n    else if (wb_writes && (wb_rd == ex_rs1) && (ex_rs1 != 5'd0)) ex_a = wb_result_q;",
     "    if (wb_writes && (wb_rd == ex_rs1) && (ex_rs1 != 5'd0)) ex_a = wb_result_q;"),
    ("no-forward-wb-to-b", "operand b is not forwarded from WB",
     "    if (mem_writes && (mem_rd == ex_rs2) && (ex_rs2 != 5'd0)) ex_b = mem_result_q;\n    else if (wb_writes && (wb_rd == ex_rs2) && (ex_rs2 != 5'd0)) ex_b = wb_result_q;",
     "    if (mem_writes && (mem_rd == ex_rs2) && (ex_rs2 != 5'd0)) ex_b = mem_result_q;"),
    ("forward-priority-inverted", "stale WB value wins over the newer MEM value",
     "    if (mem_writes && (mem_rd == ex_rs1) && (ex_rs1 != 5'd0)) ex_a = mem_result_q;\n    else if (wb_writes && (wb_rd == ex_rs1) && (ex_rs1 != 5'd0)) ex_a = wb_result_q;",
     "    if (wb_writes && (wb_rd == ex_rs1) && (ex_rs1 != 5'd0)) ex_a = wb_result_q;\n    else if (mem_writes && (mem_rd == ex_rs1) && (ex_rs1 != 5'd0)) ex_a = mem_result_q;"),
    ("no-load-use-stall", "the load-use hazard is never detected",
     "  assign stall = load_use_hazard;", "  assign stall = 1'b0;"),
    ("load-use-ignores-rs2", "the load-use check only looks at rs1",
     "                           && (((f_rd(ex_instruction_q) == id_rs1) && (id_rs1 != 5'd0))\n                               || ((f_rd(ex_instruction_q) == id_rs2) && (id_rs2 != 5'd0)));",
     "                           && ((f_rd(ex_instruction_q) == id_rs1) && (id_rs1 != 5'd0));"),
    ("no-wb-bypass-in-id", "ID reads the register file without the writeback bypass",
     "    if (wb_writes && (wb_rd == id_rs1) && (id_rs1 != 5'd0)) id_a = wb_result_q;",
     "    if (1'b0) id_a = wb_result_q;"),
    ("flush-misses-id", "a taken branch does not flush the instruction in ID",
     "          ex_valid_q <= id_valid_q && !flush;", "          ex_valid_q <= id_valid_q;"),
    ("branch-target-off-by-four", "branch target computed from pc+4",
     "          ex_target = ex_pc_q + f_imm_b(ex_instruction_q);",
     "          ex_target = ex_pc_q + 32'd4 + f_imm_b(ex_instruction_q);"),
    ("forward-ignores-validity", "forwarding fires for a bubble in MEM",
     "  assign mem_writes = mem_valid_q && f_writes_reg(mem_instruction_q)",
     "  assign mem_writes = f_writes_reg(mem_instruction_q)"),
    ("store-data-not-forwarded", "store data uses the stale register read",
     "        mem_store_q <= ex_b;", "        mem_store_q <= ex_b_q;"),
]


def build_mutant(source: str, work: Path, design: dict) -> Path | None:
    """Verilate one mutant. Returns the binary, or None if it will not build."""
    rtl_dir = work / "rtl"
    rtl_dir.mkdir(parents=True, exist_ok=True)
    mutant = rtl_dir / design["rtl"].name
    mutant.write_text(source, encoding="utf-8")
    obj = work / "obj"
    completed = subprocess.run(
        ["verilator", "--cc", "--exe", "--build", "-j", "0",
         "-Wall", "-Wno-fatal", "-Wno-DECLFILENAME", "-Wno-UNUSEDSIGNAL",
         "-Wno-WIDTH", "-Wno-SELRANGE", "-Wno-UNOPTFLAT",
         "--top-module", design["top"], "--Mdir", str(obj),
         "-CFLAGS", "-std=c++17 -O1",
         str(mutant), str(design["tb"]), "-o", "mutant_sim"],
        capture_output=True, text=True, timeout=600,
    )
    binary = obj / "mutant_sim"
    return binary if completed.returncode == 0 and binary.is_file() else None


def evaluate(version: str, programs: int, length: int, work: Path,
             design_name: str = "multicycle") -> dict[str, Any]:
    """Run the loop against every mutant and report the mutation score."""
    import differential

    design = DESIGNS[design_name]
    catalogue = MUTATIONS if design_name == "multicycle" else PIPELINE_MUTATIONS
    baseline = design["rtl"].read_text(encoding="utf-8")
    results: list[dict[str, Any]] = []

    for index, (identifier, description, find, replace) in enumerate(catalogue):
        if find not in baseline:
            results.append({"id": identifier, "status": "not-applied",
                            "reason": "anchor text absent from the RTL"})
            continue
        mutant_source = baseline.replace(find, replace, 1)
        mutant_work = work / identifier
        if mutant_work.exists():
            shutil.rmtree(mutant_work)
        binary = build_mutant(mutant_source, mutant_work, design)
        if binary is None:
            results.append({"id": identifier, "status": "build-failed",
                            "description": description})
            continue

        os.environ["AISL_RV32I_SIM"] = str(binary)
        import importlib
        importlib.reload(differential)

        killed_at = None
        killed_by = None
        started = time.monotonic()
        for position, (name, program) in enumerate(
                differential.program_suite(version, programs, length), start=1):
            try:
                outcome = differential.run_program(program, mutant_work / "run")
            except Exception:
                killed_at, killed_by = position, name
                break
            if not outcome["ok"]:
                killed_at, killed_by = position, name
                break
        results.append({
            "id": identifier,
            "description": description,
            "status": "killed" if killed_at else "survived",
            "programs_to_kill": killed_at,
            "killed_by": killed_by,
            "seconds": round(time.monotonic() - started, 3),
        })
        shutil.rmtree(mutant_work, ignore_errors=True)

    os.environ.pop("AISL_RV32I_SIM", None)
    applied = [r for r in results if r["status"] in ("killed", "survived")]
    killed = [r for r in applied if r["status"] == "killed"]
    return {
        "design": design_name,
        "workflow": version,
        "programs_per_mutant": programs,
        "program_length": length,
        "mutants_total": len(catalogue),
        "mutants_applied": len(applied),
        "killed": len(killed),
        "survived": len(applied) - len(killed),
        "mutation_score": round(len(killed) / len(applied), 4) if applied else None,
        "median_programs_to_kill": sorted(r["programs_to_kill"] for r in killed)[len(killed) // 2]
        if killed else None,
        "survivors": [r["id"] for r in applied if r["status"] == "survived"],
        "not_applied": [r["id"] for r in results if r["status"] == "not-applied"],
        "build_failed": [r["id"] for r in results if r["status"] == "build-failed"],
        "results": results,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RV32I mutation testing")
    parser.add_argument("--workflow", default="w3-directed-plus-random")
    parser.add_argument("--design", default="multicycle", choices=list(DESIGNS))
    parser.add_argument("--programs", type=int, default=40)
    parser.add_argument("--length", type=int, default=120)
    args = parser.parse_args()

    work = Path(tempfile.mkdtemp(prefix="aisl-mutation-"))
    try:
        summary = evaluate(args.workflow, args.programs, args.length, work, args.design)
    finally:
        shutil.rmtree(work, ignore_errors=True)
    print(json.dumps({k: v for k, v in summary.items() if k != "results"}, indent=2))
