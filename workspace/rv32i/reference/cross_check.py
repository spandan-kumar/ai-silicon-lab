#!/usr/bin/env python3
"""Independent cross-check against CV32E40P.

Every other comparison in this experiment shares an author. The reference
model and both local cores were written from the same specification by the
same person, so a misreading of the specification would appear in all three,
they would agree, and the loop would report success.

CV32E40P is an OpenHW Group core developed elsewhere and proven in silicon.
This repository vendors it and does not modify it. Agreement with it is the
evidence that no such shared misreading exists.

Architectural state is compared through a memory signature rather than through
any internal signal, because CV32E40P exposes no register-file read port and
must not be changed to add one. The program writes its own final register
values to memory; the comparison happens here, afterwards, on the memory image.
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

import rv32i_asm as asm  # noqa: E402
import differential  # noqa: E402
from rv32i_iss import Hart, Memory, Trap  # noqa: E402

CV32_SIM = ROOT / "workspace" / "rv32i" / "sim" / "build-cv32" / "cv32e40p_sim"
DATA_BASE = 0x1000
DATA_SIZE = 0x400


def reference_registers(program: list[int], limit: int = 200000) -> tuple[list[int], str]:
    """Run the reference and read its signature back out of memory.

    The signature is read from memory rather than from the register file so
    that both sides of every comparison observe the same thing. The epilogue
    clobbers x1 when it writes the termination word, after the signature has
    been stored, so a model reporting final register values and a model
    reporting the memory image disagree on x1 for a reason that has nothing to
    do with either being wrong.
    """
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


def run_cv32(program: list[int], work: Path, max_cycles: int = 4000000) -> dict[str, Any]:
    work.mkdir(parents=True, exist_ok=True)
    image = work / "program.bin"
    image.write_bytes(asm.assemble(program))
    result = work / "cv32.json"
    base, length = asm.signature_addresses(DATA_BASE, DATA_SIZE)
    halt = DATA_BASE + DATA_SIZE // 2 + asm.HALT_OFFSET
    completed = subprocess.run(
        [str(CV32_SIM), "--image", str(image), "--output", str(result),
         "--load-address", "0", "--halt-address", str(halt),
         "--signature-base", str(base), "--signature-words", str(length // 4),
         "--max-cycles", str(max_cycles)],
        capture_output=True, text=True, timeout=900)
    if completed.returncode != 0:
        raise RuntimeError(f"cv32e40p simulator failed: {completed.stderr[:300]}")
    return json.loads(result.read_text())


def cross_check(workflow: str, count: int, length: int, work: Path) -> dict[str, Any]:
    disagreements: list[dict[str, Any]] = []
    checked = 0
    total_cycles = 0
    for name, base_program in differential.program_suite(workflow, count, length):
        program = asm.with_signature(base_program)
        expected, stop = reference_registers(program)
        observed = run_cv32(program, work)
        checked += 1
        total_cycles += observed.get("cycles", 0)

        if observed["stop_reason"] != "halt-store":
            disagreements.append({"program": name, "kind": "did-not-halt",
                                  "cv32_stop": observed["stop_reason"],
                                  "reference_stop": stop})
            continue
        differing = [i for i in range(31) if observed["signature"][i] != expected[i]]
        if differing:
            disagreements.append({
                "program": name, "kind": "register-mismatch",
                "registers": {f"x{i + 1}": {"reference": expected[i],
                                            "cv32e40p": observed["signature"][i]}
                              for i in differing[:6]},
                "differing_count": len(differing),
            })
    return {
        "workflow": workflow,
        "programs": checked,
        "disagreements": len(disagreements),
        "detail": disagreements[:5],
        "cv32_cycles": total_cycles,
    }


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="CV32E40P independent cross-check")
    parser.add_argument("--workflow", default="w4-hazards")
    parser.add_argument("--programs", type=int, default=100)
    parser.add_argument("--length", type=int, default=120)
    parser.add_argument("--work", default=".aisl/rv32i/cross")
    args = parser.parse_args()

    if not CV32_SIM.is_file():
        print(json.dumps({"status": "unavailable",
                          "reason": f"{CV32_SIM} not built"}, indent=2))
        raise SystemExit(2)

    summary = cross_check(args.workflow, args.programs, args.length, ROOT / args.work)
    print(json.dumps(summary, indent=2))
    print(f"\n{summary['programs'] - summary['disagreements']}/{summary['programs']} "
          f"programs agree with CV32E40P")
    raise SystemExit(0 if summary["disagreements"] == 0 else 1)
