#!/usr/bin/env python3
"""Cross-check against the Sail RISC-V model.

Sail is the authoritative executable specification of RISC-V, maintained by
RISC-V International. It is the strongest execution oracle available, and it is
the right one for this experiment in a way CV32E40P is not.

CV32E40P closed the shared-author gap for every rule the two implementations'
ISAs share. It could not close it for a rule where they differ: as an RV32IMC
core it has IALIGN=16, so a branch target that is 2 mod 4 is legal for it and
illegal for the RV32I core specified here. Formal verification found that gap.
Sail does not have it, because Sail is configured to the exact ISA under test --
the configuration in `rv32i-only.json` disables the C extension along with
everything else this core does not implement.

Architectural state is compared through the memory signature, read from memory
on both sides, so neither side reports a register value the other never stored.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(ROOT / "workspace" / "rv32i" / "reference"))

import rv32i_asm as asm  # noqa: E402
import differential  # noqa: E402
from elf import write_elf  # noqa: E402
from rv32i_iss import Hart, Memory, Trap  # noqa: E402

SAIL = ROOT / "temp" / "sail-riscv" / "sail-riscv-Mac-arm64" / "bin" / "sail_riscv_sim"
CONFIG = HERE / "rv32i-only.json"
DATA_BASE, DATA_SIZE = 0x1000, 0x400
MEM_SIZE = 0x1600


def reference_signature(program: list[int], limit: int = 200000) -> tuple[list[int], str]:
    memory = Memory()
    memory.load_image(0, asm.assemble(program))
    hart = Hart(memory, 0, halt_address=asm.halt_address(DATA_BASE, DATA_SIZE))
    stop = "instruction-limit"
    for _ in range(limit):
        try:
            hart.step()
        except Trap as trap:
            stop = trap.kind
            break
    base, length = asm.signature_addresses(DATA_BASE, DATA_SIZE)
    signature = [
        int.from_bytes(bytes(memory.data.get(base + 4 * i + b, 0) for b in range(4)), "little")
        for i in range(length // 4)
    ]
    return signature, stop


def run_sail(program: list[int], work: Path, limit: int = 2000000) -> dict[str, Any]:
    work.mkdir(parents=True, exist_ok=True)
    base, length = asm.signature_addresses(DATA_BASE, DATA_SIZE)

    elf = work / "program.elf"
    # Pad the loadable image with explicit zeros out to the full memory size so
    # the initial contents of the data and signature regions are defined by the
    # ELF rather than by whichever default each model happens to use. These
    # testbenches read unwritten memory as zero; Sail reads it as 0xFF. Neither
    # is wrong -- the ISA says nothing about it -- so the environment has to
    # state it, exactly as the reset register values had to be stated.
    image = asm.assemble(program)
    image = image + b"\x00" * (MEM_SIZE - len(image))
    elf.write_bytes(write_elf(
        image, mem_size=MEM_SIZE,
        symbols={"begin_signature": base, "end_signature": base + length,
                 "tohost": DATA_BASE + DATA_SIZE // 2 + asm.HALT_OFFSET}))
    signature_path = work / "signature.txt"
    if signature_path.exists():
        signature_path.unlink()
    completed = subprocess.run(
        [str(SAIL), "--rv32", "--config-override", str(CONFIG),
         "--test-signature", str(signature_path), "--inst-limit", str(limit), str(elf)],
        capture_output=True, text=True, timeout=600)
    tail = (completed.stdout or "").strip().splitlines()
    outcome = tail[-1] if tail else ""
    signature: list[int] = []
    if signature_path.is_file():
        signature = [int(word, 16) for word in signature_path.read_text().split()]
    return {"exit": completed.returncode, "outcome": outcome, "signature": signature}


def cross_check(workflow: str, count: int, length: int, work: Path) -> dict[str, Any]:
    disagreements: list[dict[str, Any]] = []
    checked = 0
    for name, base_program in differential.program_suite(workflow, count, length):
        program = asm.with_signature(base_program)
        expected, stop = reference_signature(program)
        observed = run_sail(program, work)
        checked += 1
        if observed["exit"] != 0:
            disagreements.append({"program": name, "kind": "sail-did-not-succeed",
                                  "outcome": observed["outcome"], "reference_stop": stop})
            continue
        differing = [i for i in range(len(expected)) if observed["signature"][i] != expected[i]]
        if differing:
            disagreements.append({
                "program": name, "kind": "register-mismatch",
                "registers": {f"x{i + 1}": {"reference": expected[i],
                                            "sail": observed["signature"][i]}
                              for i in differing[:6]},
                "differing_count": len(differing)})
    return {"workflow": workflow, "programs": checked,
            "disagreements": len(disagreements), "detail": disagreements[:5]}


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Sail model cross-check")
    parser.add_argument("--workflow", default="w4-hazards")
    parser.add_argument("--programs", type=int, default=60)
    parser.add_argument("--length", type=int, default=120)
    parser.add_argument("--work", default=".aisl/rv32i/sail")
    args = parser.parse_args()

    if not SAIL.is_file():
        print(json.dumps({"status": "unavailable",
                          "reason": f"{SAIL} not present"}, indent=2))
        raise SystemExit(2)

    summary = cross_check(args.workflow, args.programs, args.length, ROOT / args.work)
    print(json.dumps(summary, indent=2)[:3000])
    print(f"\n{summary['programs'] - summary['disagreements']}/{summary['programs']} "
          f"programs agree with the Sail model")
    raise SystemExit(0 if summary["disagreements"] == 0 else 1)
