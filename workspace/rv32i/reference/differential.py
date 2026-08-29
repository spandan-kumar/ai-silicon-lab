#!/usr/bin/env python3
"""Differential comparison between the RV32I RTL and the reference model.

Runs the same program on both, compares architectural state after every
retired instruction, and reports the *first* divergence with enough context to
localise it. First divergence matters: after one wrong register the rest of the
trace is noise, and a report that lists a thousand consequent mismatches hides
the one instruction that actually broke.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))

import rv32i_asm as asm  # noqa: E402
from rv32i_iss import Hart, Memory, Trap  # noqa: E402

# Overridable so the mutation harness can point the same loop at a mutant
# build without duplicating any of the comparison logic.
SIMULATOR = Path(os.environ.get(
    "AISL_RV32I_SIM", ROOT / "workspace" / "rv32i" / "sim" / "build" / "rv32i_sim"))
LOAD_ADDRESS = 0
DATA_BASE = 0x1000


def disassemble(word: int) -> str:
    """Enough decoding to make a divergence report readable."""
    opcode = word & 0x7F
    rd = (word >> 7) & 0x1F
    funct3 = (word >> 12) & 0x7
    rs1 = (word >> 15) & 0x1F
    rs2 = (word >> 20) & 0x1F
    funct7 = (word >> 25) & 0x7F
    names = {
        0b0110111: "lui", 0b0010111: "auipc", 0b1101111: "jal",
        0b1100111: "jalr", 0b1110011: "system", 0b0001111: "fence",
    }
    if opcode in names:
        return f"{names[opcode]} rd=x{rd}"
    if opcode == 0b1100011:
        name = {0: "beq", 1: "bne", 4: "blt", 5: "bge", 6: "bltu", 7: "bgeu"}.get(funct3, "b?")
        return f"{name} x{rs1},x{rs2}"
    if opcode == 0b0000011:
        name = {0: "lb", 1: "lh", 2: "lw", 4: "lbu", 5: "lhu"}.get(funct3, "l?")
        return f"{name} x{rd},x{rs1}"
    if opcode == 0b0100011:
        name = {0: "sb", 1: "sh", 2: "sw"}.get(funct3, "s?")
        return f"{name} x{rs2},x{rs1}"
    if opcode == 0b0010011:
        name = {0: "addi", 2: "slti", 3: "sltiu", 4: "xori", 6: "ori", 7: "andi",
                1: "slli", 5: "srai" if funct7 == 0b0100000 else "srli"}.get(funct3, "i?")
        return f"{name} x{rd},x{rs1}"
    if opcode == 0b0110011:
        name = {0: "sub" if funct7 == 0b0100000 else "add", 1: "sll", 2: "slt",
                3: "sltu", 4: "xor", 6: "or", 7: "and",
                5: "sra" if funct7 == 0b0100000 else "srl"}.get(funct3, "r?")
        return f"{name} x{rd},x{rs1},x{rs2}"
    return f"unknown({word:#010x})"


def run_reference(image: bytes, limit: int) -> dict[str, Any]:
    memory = Memory()
    memory.load_image(LOAD_ADDRESS, image)
    hart = Hart(memory, LOAD_ADDRESS)
    trace: list[dict[str, Any]] = []
    stop = "instruction-limit"
    for _ in range(limit):
        pc, instruction = hart.pc, memory.load_bytes(hart.pc, 4)
        try:
            hart.step()
        except Trap as trap:
            stop = trap.kind
            break
        trace.append({"pc": pc, "instruction": instruction, "regs": list(hart.x)})
    return {"stop_reason": stop, "retired": len(trace), "trace": trace,
            "final_regs": list(hart.x), "memory": hart.memory.data}


def run_rtl(image_path: Path, output_path: Path, max_cycles: int) -> dict[str, Any]:
    completed = subprocess.run(
        [str(SIMULATOR), "--image", str(image_path), "--output", str(output_path),
         "--load-address", str(LOAD_ADDRESS), "--max-cycles", str(max_cycles)],
        capture_output=True, text=True, timeout=600,
    )
    if completed.returncode != 0:
        raise RuntimeError(f"simulator failed: {completed.stderr[:400]}")
    return json.loads(output_path.read_text())


# The reference stops *before* executing a trapping instruction; the RTL
# retires everything up to it too. These stop reasons mean the same thing.
EQUIVALENT_STOPS = {
    ("ebreak", "ebreak"), ("ecall", "ecall"),
    ("instruction-limit", "cycle-limit"),
    # The model and the RTL detect the same condition under different names.
    # Treating a naming difference as a divergence wastes iterations on a
    # defect in the harness rather than in the design.
    ("illegal-opcode", "illegal"), ("illegal-op", "illegal"),
    ("illegal-op-imm", "illegal"), ("illegal-branch-funct3", "illegal"),
    ("illegal-load-funct3", "illegal"), ("illegal-store-funct3", "illegal"),
}


def compare(reference: dict[str, Any], rtl: dict[str, Any]) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    ref_trace, rtl_trace = reference["trace"], rtl["trace"]

    if reference["stop_reason"] != rtl["stop_reason"] and \
            (reference["stop_reason"], rtl["stop_reason"]) not in EQUIVALENT_STOPS:
        findings.append({
            "kind": "stop-reason",
            "reference": reference["stop_reason"],
            "rtl": rtl["stop_reason"],
        })

    # First divergence in the executed instruction stream, then in state.
    for index in range(min(len(ref_trace), len(rtl_trace))):
        expected, actual = ref_trace[index], rtl_trace[index]
        if expected["pc"] != actual["pc"]:
            findings.append({
                "kind": "control-flow",
                "index": index,
                "expected_pc": expected["pc"], "actual_pc": actual["pc"],
                "previous": disassemble(ref_trace[index - 1]["instruction"]) if index else None,
                "previous_pc": ref_trace[index - 1]["pc"] if index else None,
            })
            break
        if expected["instruction"] != actual["instruction"]:
            findings.append({
                "kind": "instruction-fetch", "index": index, "pc": expected["pc"],
                "expected": expected["instruction"], "actual": actual["instruction"],
            })
            break
        differing = [r for r in range(32) if expected["regs"][r] != actual["regs"][r]]
        if differing:
            findings.append({
                "kind": "register-state",
                "index": index,
                "pc": expected["pc"],
                "instruction": f"{expected['instruction']:#010x}",
                "disassembly": disassemble(expected["instruction"]),
                "registers": {
                    f"x{r}": {"expected": expected["regs"][r], "actual": actual["regs"][r]}
                    for r in differing[:6]
                },
            })
            break

    if not findings and len(ref_trace) != len(rtl_trace):
        findings.append({
            "kind": "retire-count",
            "reference": len(ref_trace), "rtl": len(rtl_trace),
        })

    return {
        "ok": not findings,
        "findings": findings,
        "reference_retired": len(ref_trace),
        "rtl_retired": len(rtl_trace),
        "rtl_cycles": rtl.get("cycles"),
    }


def run_program(program: list[int], work_dir: Path, *, limit: int = 20000,
                max_cycles: int = 2000000) -> dict[str, Any]:
    work_dir.mkdir(parents=True, exist_ok=True)
    image = asm.assemble(program)
    image_path = work_dir / "program.bin"
    image_path.write_bytes(image)
    reference = run_reference(image, limit)
    rtl = run_rtl(image_path, work_dir / "rtl.json", max_cycles)
    result = compare(reference, rtl)
    result["stop_reason"] = reference["stop_reason"]
    return result



# --- workflow configurations ----------------------------------------------
#
# Named so that a change to the loop can be measured against the loop it
# replaces. Each is a complete recipe for what stimulus the loop runs.

WORKFLOWS = {
    # The starting point: flat random programs, forward control flow only.
    "w1-random-v1": {"version": 1, "directed": False},
    # Block-structured generation with a centred data pointer, so constructs
    # are atomic and memory offsets take both signs.
    "w2-random-v3": {"version": 3, "directed": False},
    # The same random corpus preceded by directed encoding-boundary tests.
    "w3-directed-plus-random": {"version": 3, "directed": True},
    # Adds directed pipeline-hazard tests. These are plain RV32I programs, so
    # they cost a non-pipelined design nothing, but they construct the
    # producer/consumer/distance conjunctions that random code reaches only by
    # coincidence.
    "w4-hazards": {"version": 3, "directed": True, "hazards": True},
}


def program_suite(workflow: str, count: int, length: int):
    """Yield (name, program) for a workflow, directed tests first.

    Directed tests run first on purpose: they are targeted, so when they find
    something they find it immediately, and the name of the failing test says
    what broke without any further bisection.
    """
    config = WORKFLOWS[workflow]
    if config.get("hazards"):
        for name, program in asm.directed_hazard_programs():
            yield name, program
    if config["directed"]:
        for name, program in asm.directed_programs():
            yield name, program
    for offset in range(count):
        seed = 1 + offset
        yield f"random-{seed}", asm.random_program(
            seed, length, data_base=DATA_BASE, version=config["version"])


def sweep(seeds: range, work_dir: Path, length: int = 60,
          version: int = 2) -> dict[str, Any]:
    failures: list[dict[str, Any]] = []
    total_cycles = 0
    total_retired = 0
    for seed in seeds:
        program = asm.random_program(seed, length, data_base=DATA_BASE, version=version)
        result = run_program(program, work_dir)
        total_cycles += result.get("rtl_cycles") or 0
        total_retired += result.get("reference_retired") or 0
        if not result["ok"]:
            failures.append({"seed": seed, **result})
    return {
        "programs": len(seeds),
        "failures": len(failures),
        "first_failures": failures[:5],
        "total_cycles": total_cycles,
        "total_retired": total_retired,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="RV32I differential test")
    parser.add_argument("--seeds", type=int, default=50)
    parser.add_argument("--start", type=int, default=1)
    parser.add_argument("--length", type=int, default=60)
    parser.add_argument("--work", default=".aisl/rv32i/diff")
    parser.add_argument("--version", type=int, default=3)
    args = parser.parse_args()

    work = ROOT / args.work
    summary = sweep(range(args.start, args.start + args.seeds), work, args.length,
                    version=args.version)
    print(json.dumps(summary, indent=2)[:4000])
    print(f"\n{summary['programs'] - summary['failures']}/{summary['programs']} programs agree")
    raise SystemExit(0 if summary["failures"] == 0 else 1)
