#!/usr/bin/env python3
"""Functional coverage for the RV32I differential loop.

A passing differential run says the two implementations agreed on what was
executed. It says nothing about what was not executed. This module answers the
second question, so that "60 of 60 programs agree" can be read together with
"and here is what those 60 programs never once did".

Coverage is measured on the reference trace, because the reference knows the
meaning of each instruction. It is stimulus coverage, not RTL toggle or branch
coverage, and it is labelled that way.
"""

from __future__ import annotations

from collections import Counter
from typing import Any


R_NAMES = {(0, 0): "add", (0, 32): "sub", (1, 0): "sll", (2, 0): "slt", (3, 0): "sltu",
           (4, 0): "xor", (5, 0): "srl", (5, 32): "sra", (6, 0): "or", (7, 0): "and"}
I_NAMES = {0: "addi", 2: "slti", 3: "sltiu", 4: "xori", 6: "ori", 7: "andi"}
SHIFT_NAMES = {(1, 0): "slli", (5, 0): "srli", (5, 32): "srai"}
LOAD_NAMES = {0: "lb", 1: "lh", 2: "lw", 4: "lbu", 5: "lhu"}
STORE_NAMES = {0: "sb", 1: "sh", 2: "sw"}
BRANCH_NAMES = {0: "beq", 1: "bne", 4: "blt", 5: "bge", 6: "bltu", 7: "bgeu"}

ALL_INSTRUCTIONS = (
    set(R_NAMES.values()) | set(I_NAMES.values()) | set(SHIFT_NAMES.values())
    | set(LOAD_NAMES.values()) | set(STORE_NAMES.values()) | set(BRANCH_NAMES.values())
    | {"lui", "auipc", "jal", "jalr"}
)


def classify(word: int) -> str | None:
    opcode = word & 0x7F
    funct3 = (word >> 12) & 0x7
    funct7 = (word >> 25) & 0x7F
    if opcode == 0b0110111:
        return "lui"
    if opcode == 0b0010111:
        return "auipc"
    if opcode == 0b1101111:
        return "jal"
    if opcode == 0b1100111:
        return "jalr"
    if opcode == 0b1100011:
        return BRANCH_NAMES.get(funct3)
    if opcode == 0b0000011:
        return LOAD_NAMES.get(funct3)
    if opcode == 0b0100011:
        return STORE_NAMES.get(funct3)
    if opcode == 0b0010011:
        if funct3 in (1, 5):
            return SHIFT_NAMES.get((funct3, funct7))
        return I_NAMES.get(funct3)
    if opcode == 0b0110011:
        return R_NAMES.get((funct3, funct7))
    return None


# Situations that break real cores and that uniform random stimulus reaches
# rarely or never. Each is a named bin so a gap is visible rather than implied.
CORNER_BINS = (
    "rd-is-x0",             # a write that must be discarded
    "rs1-is-x0",
    "rs2-is-x0",
    "rd-equals-rs1",        # destination aliases a source
    "shift-by-zero",
    "shift-by-31",
    "branch-taken",
    "branch-not-taken",
    "branch-backward",
    "add-overflow",         # signed overflow wraps rather than saturating
    "sub-borrow",
    "slt-signed-differs-unsigned",
    "load-after-store-same-address",
    "jalr-target-lsb-set",  # the bit that JALR must clear
    "negative-immediate",
    "max-positive-immediate",
    "min-negative-immediate",
)


class Coverage:
    def __init__(self) -> None:
        self.instructions: Counter[str] = Counter()
        self.corners: Counter[str] = Counter()
        self.unknown = 0
        self._last_store_address: int | None = None

    def observe(self, word: int, regs_before: list[int], pc: int,
                next_pc: int, memory_address: int | None = None) -> None:
        name = classify(word)
        if name is None:
            self.unknown += 1
            return
        self.instructions[name] += 1

        rd = (word >> 7) & 0x1F
        rs1 = (word >> 15) & 0x1F
        rs2 = (word >> 20) & 0x1F
        funct3 = (word >> 12) & 0x7
        opcode = word & 0x7F
        shamt = (word >> 20) & 0x1F
        a = regs_before[rs1] if rs1 else 0
        b = regs_before[rs2] if rs2 else 0

        writes = opcode not in (0b0100011, 0b1100011)
        if writes and rd == 0:
            self.corners["rd-is-x0"] += 1
        if rs1 == 0:
            self.corners["rs1-is-x0"] += 1
        if opcode in (0b0110011, 0b0100011, 0b1100011) and rs2 == 0:
            self.corners["rs2-is-x0"] += 1
        if writes and rd != 0 and rd == rs1:
            self.corners["rd-equals-rs1"] += 1

        if name in ("slli", "srli", "srai"):
            if shamt == 0:
                self.corners["shift-by-zero"] += 1
            if shamt == 31:
                self.corners["shift-by-31"] += 1
        if name in ("sll", "srl", "sra"):
            if (b & 31) == 0:
                self.corners["shift-by-zero"] += 1
            if (b & 31) == 31:
                self.corners["shift-by-31"] += 1

        if opcode == 0b1100011:
            taken = next_pc != (pc + 4) & 0xFFFFFFFF
            self.corners["branch-taken" if taken else "branch-not-taken"] += 1
            if taken and next_pc < pc:
                self.corners["branch-backward"] += 1

        if name == "add":
            total = a + b
            if ((a ^ total) & (b ^ total) & 0x8000_0000) != 0:
                self.corners["add-overflow"] += 1
        if name == "sub" and a < b:
            self.corners["sub-borrow"] += 1
        if name in ("slt", "sltu"):
            def signed(v: int) -> int:
                return v - (1 << 32) if v & 0x8000_0000 else v
            if (signed(a) < signed(b)) != (a < b):
                self.corners["slt-signed-differs-unsigned"] += 1

        if name == "jalr":
            immediate = word >> 20
            immediate -= 1 << 12 if immediate & 0x800 else 0
            if ((a + immediate) & 1) != 0:
                self.corners["jalr-target-lsb-set"] += 1

        if opcode in (0b0010011, 0b0000011, 0b0100011, 0b1100111) and \
                name not in ("slli", "srli", "srai"):
            if opcode == 0b0100011:
                immediate = (((word >> 25) << 5) | ((word >> 7) & 0x1F))
            else:
                immediate = word >> 20
            immediate -= 1 << 12 if immediate & 0x800 else 0
            if immediate < 0:
                self.corners["negative-immediate"] += 1
            if immediate == 2047:
                self.corners["max-positive-immediate"] += 1
            if immediate == -2048:
                self.corners["min-negative-immediate"] += 1

        if memory_address is not None:
            if opcode == 0b0100011:
                self._last_store_address = memory_address
            elif opcode == 0b0000011 and memory_address == self._last_store_address:
                self.corners["load-after-store-same-address"] += 1

    def report(self) -> dict[str, Any]:
        missing_instructions = sorted(ALL_INSTRUCTIONS - set(self.instructions))
        missing_corners = [name for name in CORNER_BINS if not self.corners[name]]
        return {
            "instructions_covered": len(ALL_INSTRUCTIONS) - len(missing_instructions),
            "instructions_total": len(ALL_INSTRUCTIONS),
            "instructions_missing": missing_instructions,
            "instruction_counts": dict(sorted(self.instructions.items())),
            "corners_covered": len(CORNER_BINS) - len(missing_corners),
            "corners_total": len(CORNER_BINS),
            "corners_missing": missing_corners,
            "corner_counts": {k: self.corners[k] for k in CORNER_BINS},
            "coverage_kind": "stimulus/functional, measured on the reference trace; "
                             "not RTL toggle or branch coverage",
        }
