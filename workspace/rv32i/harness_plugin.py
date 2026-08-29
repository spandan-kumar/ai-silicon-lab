#!/usr/bin/env python3
"""RV32I experiment plugin.

Wires both cores into the autonomous harness. The reference side runs the
independent instruction set simulator; the candidate side runs Verilator over
the RTL. Each vector is one program, carrying the final architectural state,
the retired count, the stop reason, and a digest of the whole per-instruction
trace, so a single mismatched field means the two implementations diverged
somewhere in that program.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import shutil
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE / "reference"))
sys.path.insert(0, str(ROOT / "harness"))

import differential  # noqa: E402
import opcode_conformance  # noqa: E402
import rv32i_asm as asm  # noqa: E402
from coverage import Coverage  # noqa: E402
from rv32i_iss import Hart, Memory, Trap  # noqa: E402

from aisl_harness.contracts import (  # noqa: E402
    BuildResult, CandidateOutput, Context, ExperimentPlugin, ReferenceOutput, Workload,
)
from aisl_harness.core import (  # noqa: E402
    HarnessError, relative, run, sha256_file, sha256_tree, tool_version,
)

RTL_DIR = HERE / "rtl"
SIM_DIR = HERE / "sim"

DESIGNS = {
    "multicycle": {"rtl": [RTL_DIR / "rv32i_core.sv"], "tb": SIM_DIR / "tb_rv32i.cpp",
                   "top": "rv32i_core", "build": SIM_DIR / "build", "binary": "rv32i_sim"},
    "pipeline": {"rtl": [RTL_DIR / "rv32i_pipe.sv"], "tb": SIM_DIR / "tb_rv32i_pipe.cpp",
                 "top": "rv32i_pipe", "build": SIM_DIR / "build-pipe", "binary": "rv32i_pipe_sim"},
}

# (workload id, design, workflow, random program count, program length)
WORKLOADS = [
    ("multicycle-directed", "multicycle", "directed-only", 0, 0),
    ("multicycle-random", "multicycle", "w4-hazards", 200, 150),
    ("pipeline-directed", "pipeline", "directed-only", 0, 0),
    ("pipeline-random", "pipeline", "w4-hazards", 200, 150),
]

VERILATOR_FLAGS = ["-Wall", "-Wno-fatal", "-Wno-DECLFILENAME", "-Wno-UNUSEDSIGNAL", "--assert"]


def programs_for(workflow: str, count: int, length: int):
    if workflow == "directed-only":
        yield from asm.directed_hazard_programs()
        yield from asm.directed_programs()
    else:
        yield from differential.program_suite(workflow, count, length)


def trace_digest(trace: list[dict[str, Any]]) -> str:
    digest = hashlib.sha256()
    for entry in trace:
        digest.update(f"{entry['pc']}:{entry['instruction']}:".encode())
        digest.update(",".join(str(v) for v in entry["regs"]).encode())
    return digest.hexdigest()


class Rv32iPlugin(ExperimentPlugin):
    experiment_id = "rv32i-core"

    def describe(self) -> dict[str, Any]:
        return {
            "designs": {
                name: {relative(path): sha256_file(path) for path in design["rtl"]}
                for name, design in DESIGNS.items()
            },
            "reference_model": {
                relative(HERE / "reference" / "rv32i_iss.py"):
                    sha256_file(HERE / "reference" / "rv32i_iss.py")
            },
            "ground_truth": [
                "independent instruction set simulator written from the specification",
                "riscv/riscv-opcodes machine-readable encoding tables",
            ],
            "ground_truth_unavailable": {
                "riscv-arch-test": "needs a RISC-V toolchain and a reference model to "
                                   "generate signatures; neither is installed on this host",
                "sail-riscv": "the official formal model; needs a Sail/OCaml toolchain",
            },
        }

    def workloads(self) -> list[Workload]:
        return [
            Workload(id=identifier, role="differential-correctness", comparator="vectors",
                     description=f"{design} core, {workflow} stimulus",
                     parameters={"design": design, "workflow": workflow,
                                 "random_programs": count, "length": length},
                     repeat=1)
            for identifier, design, workflow, count, length in WORKLOADS
        ]

    def build(self, context: Context) -> BuildResult:
        commands, artifacts = [], {}
        ok = True
        for name, design in DESIGNS.items():
            command = run(
                ["verilator", "--cc", "--exe", "--build", "-j", "0", *VERILATOR_FLAGS,
                 "--top-module", design["top"], "--Mdir", str(design["build"]),
                 "-CFLAGS", "-std=c++17 -O2 -DAISL_ASSERTIONS", "-DAISL_ASSERTIONS",
                 *[str(p) for p in design["rtl"]], str(design["tb"]),
                 "-o", design["binary"]],
                timeout=900)
            commands.append(command)
            binary = design["build"] / design["binary"]
            if command.get("exit_code") == 0 and binary.is_file():
                artifacts[relative(binary)] = sha256_file(binary)
            else:
                ok = False
        artifacts["rtl-aggregate"] = sha256_tree(RTL_DIR)
        return BuildResult(ok=ok, commands=commands, artifacts=artifacts,
                           tools=[tool_version("verilator"), tool_version("cc")],
                           notes="Both cores built with assertions enabled.")

    def reference(self, context: Context) -> ReferenceOutput:
        workload = context.workload
        if workload is None:
            raise HarnessError("reference() requires a workload")
        p = workload.parameters
        vectors = []
        for name, program in programs_for(p["workflow"], p["random_programs"], p["length"]):
            memory = Memory()
            memory.load_image(0, asm.assemble(program))
            hart = Hart(memory, 0)
            trace, stop = [], "instruction-limit"
            for _ in range(200000):
                pc, word = hart.pc, memory.load_bytes(hart.pc, 4)
                try:
                    hart.step()
                except Trap as trap:
                    stop = trap.kind
                    break
                trace.append({"pc": pc, "instruction": word, "regs": list(hart.x)})
            vectors.append({"id": name, "retired": len(trace),
                            "final_regs": ",".join(str(v) for v in hart.x),
                            "trace_sha256": trace_digest(trace)})
        (context.output_dir / "vectors.json").write_text(
            json.dumps({"vectors": vectors}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return ReferenceOutput(directory=context.output_dir,
                               digest=sha256_tree(context.output_dir),
                               metadata={"model": "workspace/rv32i/reference/rv32i_iss.py",
                                         "programs": len(vectors)})

    def execute(self, context: Context) -> CandidateOutput:
        workload = context.workload
        if workload is None:
            raise HarnessError("execute() requires a workload")
        if context.oracle_dir is not None:
            raise HarnessError("candidate context must not carry oracle access")
        p = workload.parameters
        design = DESIGNS[p["design"]]
        binary = design["build"] / design["binary"]
        if not binary.is_file():
            raise HarnessError(f"{relative(binary)} is missing; build first")

        vectors, commands, cycles, retired = [], [], 0, 0
        for name, program in programs_for(p["workflow"], p["random_programs"], p["length"]):
            image = context.work_dir / "program.bin"
            image.write_bytes(asm.assemble(program))
            result_path = context.work_dir / "rtl.json"
            command = run([str(binary), "--image", str(image), "--output", str(result_path),
                           "--load-address", "0", "--max-cycles", "4000000"], timeout=600)
            if command.get("exit_code") != 0:
                commands.append(command)
                vectors.append({"id": name, "retired": -1, "final_regs": "simulator-failed",
                                "trace_sha256": "simulator-failed"})
                continue
            data = json.loads(result_path.read_text())
            cycles += data.get("cycles", 0)
            retired += data.get("retired", 0)
            vectors.append({"id": name, "retired": data["retired"],
                            "final_regs": ",".join(str(v) for v in data["final_regs"]),
                            "trace_sha256": trace_digest(data["trace"])})
        (context.output_dir / "vectors.json").write_text(
            json.dumps({"vectors": vectors}, indent=1, sort_keys=True) + "\n", encoding="utf-8")
        return CandidateOutput(
            directory=context.output_dir, digest=sha256_tree(context.output_dir),
            ok=all(v["retired"] >= 0 for v in vectors), commands=commands[:5],
            reported={"programs": len(vectors)},
            measured={"total_cycles": cycles, "total_retired": retired,
                      "cycles_per_instruction": round(cycles / retired, 4) if retired else None})

    def lint(self, context: Context) -> dict[str, Any] | None:
        warnings, ok = [], True
        for name, design in DESIGNS.items():
            command = run(["verilator", "--lint-only", *VERILATOR_FLAGS,
                           "--top-module", design["top"], *[str(p) for p in design["rtl"]]],
                          timeout=300)
            found = [l for l in (command.get("stderr") or "").splitlines() if l.startswith("%Warning")]
            warnings.extend(f"{name}: {w}" for w in found)
            ok = ok and command.get("exit_code") == 0
        return {"ok": ok and not warnings, "warnings": warnings}

    def synthesize(self, context: Context) -> dict[str, Any] | None:
        if shutil.which("yosys") is None:
            return None
        results, ok = {}, True
        for name, design in DESIGNS.items():
            script = "; ".join([
                "read_verilog -sv " + " ".join(str(p) for p in design["rtl"]),
                f"hierarchy -top {design['top']}",
                f"synth -top {design['top']} -flatten", "stat -json"])
            command = run(["yosys", "-Q", "-p", script], timeout=1800)
            ok = ok and command.get("exit_code") == 0
            text = command.get("stdout") or ""
            try:
                start = text.rfind('{\n   "creator"')
                payload = json.loads(text[start:text.rfind("}") + 1])
                key = next(k for k in payload["modules"] if design["top"] in k)
                module = payload["modules"][key]
                by_type = module.get("num_cells_by_type", {})
                results[name] = {
                    "num_cells": module.get("num_cells"),
                    "flip_flops": sum(v for k, v in by_type.items() if k.startswith("$_DFF")),
                }
            except (ValueError, KeyError, StopIteration):
                results[name] = {"parse_error": "could not read stat -json output"}
        return {"ok": ok, "designs": results}

    def policy_checks(self, context: Context) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []

        conformance = opcode_conformance.check()
        checks.append({
            "id": "encoding-conformance",
            "ok": conformance["status"] == "pass" if conformance["status"] != "unavailable" else None,
            "checked": conformance.get("checked"),
            "findings": conformance.get("findings", [])[:5],
            "source": conformance.get("source"),
            "note": "Encoder checked against the official machine-readable tables. "
                    "Unavailable when temp/riscv-opcodes is absent; unavailable is not a pass.",
        })

        coverage = Coverage()
        for _, program in programs_for("w4-hazards", 200, 150):
            memory = Memory()
            memory.load_image(0, asm.assemble(program))
            hart = Hart(memory, 0)
            for _ in range(200000):
                pc, word = hart.pc, memory.load_bytes(hart.pc, 4)
                before = list(hart.x)
                # The effective address must be supplied, or the coverage model
                # cannot see a load that reads back what a store just wrote.
                # Passing None here left that bin permanently empty and looked
                # like a stimulus gap when it was a defect in this call.
                address = None
                opcode = word & 0x7F
                if opcode in (0b0000011, 0b0100011):
                    if opcode == 0b0100011:
                        immediate = ((word >> 25) << 5) | ((word >> 7) & 0x1F)
                    else:
                        immediate = word >> 20
                    immediate -= 1 << 12 if immediate & 0x800 else 0
                    base = (word >> 15) & 0x1F
                    address = ((before[base] if base else 0) + immediate) & 0xFFFFFFFF
                try:
                    hart.step()
                except Trap:
                    break
                coverage.observe(word, before, pc, hart.pc, address)
        report = coverage.report()
        checks.append({
            "id": "instruction-coverage",
            "ok": report["instructions_covered"] == report["instructions_total"],
            "covered": f"{report['instructions_covered']}/{report['instructions_total']}",
            "missing": report["instructions_missing"],
            "note": "A corpus that agrees but does not execute an instruction is not "
                    "evidence about that instruction.",
        })
        checks.append({
            "id": "corner-coverage",
            "ok": report["corners_covered"] == report["corners_total"],
            "covered": f"{report['corners_covered']}/{report['corners_total']}",
            "missing": report["corners_missing"],
        })
        return checks


def create_plugin() -> ExperimentPlugin:
    return Rv32iPlugin()
