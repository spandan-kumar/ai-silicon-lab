#!/usr/bin/env python3
"""RV32I instruction set simulator, written from the specification.

Ground truth #1 for the rv32i-core experiment. Written from the RISC-V
Unprivileged ISA specification, RV32I Base Integer Instruction Set v2.1.

This model and the RTL are written from the same specification by the same
author, which means a misreading of the specification would appear in both and
they would agree while both being wrong. That is why the experiment also
compares against CV32E40P, an independently developed silicon-proven core. Two
agreeing implementations are not evidence when they share an author; three are
evidence when one of them is independent.

Memory is a flat sparse byte map. Unaligned accesses are permitted and
resolved bytewise, which is a deliberate simplification recorded in the
experiment profile rather than a specification claim.
"""

from __future__ import annotations

from typing import Any

XLEN = 32
MASK = 0xFFFFFFFF


def sign_extend(value: int, bits: int) -> int:
    """Interpret the low `bits` of `value` as signed, return a Python int."""
    value &= (1 << bits) - 1
    if value & (1 << (bits - 1)):
        value -= 1 << bits
    return value


def to_signed(value: int) -> int:
    return sign_extend(value, XLEN)


class Trap(Exception):
    """Raised for ECALL, EBREAK, or an instruction the model does not decode."""

    def __init__(self, kind: str, pc: int, instruction: int) -> None:
        super().__init__(f"{kind} at pc={pc:#010x} instruction={instruction:#010x}")
        self.kind = kind
        self.pc = pc
        self.instruction = instruction


class Memory:
    """Sparse little-endian byte-addressed memory."""

    def __init__(self, initial: dict[int, int] | None = None) -> None:
        self.data: dict[int, int] = dict(initial or {})

    def load_bytes(self, address: int, count: int) -> int:
        value = 0
        for offset in range(count):
            value |= self.data.get((address + offset) & MASK, 0) << (8 * offset)
        return value

    def store_bytes(self, address: int, count: int, value: int) -> None:
        for offset in range(count):
            self.data[(address + offset) & MASK] = (value >> (8 * offset)) & 0xFF

    def load_image(self, address: int, image: bytes) -> None:
        for offset, byte in enumerate(image):
            self.data[(address + offset) & MASK] = byte


class Hart:
    """A single RV32I hart with 32 integer registers and a program counter."""

    def __init__(self, memory: Memory, pc: int = 0) -> None:
        self.x = [0] * 32
        self.pc = pc & MASK
        self.memory = memory
        self.retired = 0

    # --- register file: x0 is hardwired to zero -------------------------
    def read(self, index: int) -> int:
        return 0 if index == 0 else self.x[index]

    def write(self, index: int, value: int) -> None:
        if index != 0:
            self.x[index] = value & MASK

    # --- immediate decoders, one per format -----------------------------
    @staticmethod
    def imm_i(instruction: int) -> int:
        return sign_extend(instruction >> 20, 12)

    @staticmethod
    def imm_s(instruction: int) -> int:
        raw = ((instruction >> 25) << 5) | ((instruction >> 7) & 0x1F)
        return sign_extend(raw, 12)

    @staticmethod
    def imm_b(instruction: int) -> int:
        # imm[12|10:5] in [31:25], imm[4:1|11] in [11:7]; bit 0 is always zero.
        raw = (
            (((instruction >> 31) & 1) << 12)
            | (((instruction >> 7) & 1) << 11)
            | (((instruction >> 25) & 0x3F) << 5)
            | (((instruction >> 8) & 0xF) << 1)
        )
        return sign_extend(raw, 13)

    @staticmethod
    def imm_u(instruction: int) -> int:
        return instruction & 0xFFFFF000

    @staticmethod
    def imm_j(instruction: int) -> int:
        # imm[20|10:1|11|19:12]; bit 0 is always zero.
        raw = (
            (((instruction >> 31) & 1) << 20)
            | (((instruction >> 12) & 0xFF) << 12)
            | (((instruction >> 20) & 1) << 11)
            | (((instruction >> 21) & 0x3FF) << 1)
        )
        return sign_extend(raw, 21)

    def step(self) -> dict[str, Any]:
        """Execute one instruction. Returns a record of what it did."""
        pc = self.pc
        instruction = self.memory.load_bytes(pc, 4)
        opcode = instruction & 0x7F
        rd = (instruction >> 7) & 0x1F
        funct3 = (instruction >> 12) & 0x7
        rs1 = (instruction >> 15) & 0x1F
        rs2 = (instruction >> 20) & 0x1F
        funct7 = (instruction >> 25) & 0x7F

        a = self.read(rs1)
        b = self.read(rs2)
        next_pc = (pc + 4) & MASK
        written_register: int | None = None
        written_value: int | None = None
        memory_write: tuple[int, int, int] | None = None

        if opcode == 0b0110111:  # LUI
            written_register, written_value = rd, self.imm_u(instruction)

        elif opcode == 0b0010111:  # AUIPC
            written_register = rd
            written_value = (pc + self.imm_u(instruction)) & MASK

        elif opcode == 0b1101111:  # JAL
            written_register, written_value = rd, next_pc
            next_pc = (pc + self.imm_j(instruction)) & MASK

        elif opcode == 0b1100111 and funct3 == 0:  # JALR
            written_register, written_value = rd, next_pc
            # The sum is computed first, then bit 0 is cleared.
            next_pc = (a + self.imm_i(instruction)) & MASK & ~1

        elif opcode == 0b1100011:  # branches
            offset = self.imm_b(instruction)
            signed_a, signed_b = to_signed(a), to_signed(b)
            taken = {
                0b000: a == b,
                0b001: a != b,
                0b100: signed_a < signed_b,
                0b101: signed_a >= signed_b,
                0b110: a < b,
                0b111: a >= b,
            }.get(funct3)
            if taken is None:
                raise Trap("illegal-branch-funct3", pc, instruction)
            if taken:
                next_pc = (pc + offset) & MASK

        elif opcode == 0b0000011:  # loads
            address = (a + self.imm_i(instruction)) & MASK
            if funct3 == 0b000:
                value = sign_extend(self.memory.load_bytes(address, 1), 8) & MASK
            elif funct3 == 0b001:
                value = sign_extend(self.memory.load_bytes(address, 2), 16) & MASK
            elif funct3 == 0b010:
                value = self.memory.load_bytes(address, 4)
            elif funct3 == 0b100:
                value = self.memory.load_bytes(address, 1)
            elif funct3 == 0b101:
                value = self.memory.load_bytes(address, 2)
            else:
                raise Trap("illegal-load-funct3", pc, instruction)
            written_register, written_value = rd, value

        elif opcode == 0b0100011:  # stores
            address = (a + self.imm_s(instruction)) & MASK
            width = {0b000: 1, 0b001: 2, 0b010: 4}.get(funct3)
            if width is None:
                raise Trap("illegal-store-funct3", pc, instruction)
            self.memory.store_bytes(address, width, b)
            memory_write = (address, width, b & ((1 << (8 * width)) - 1))

        elif opcode == 0b0010011:  # register-immediate
            immediate = self.imm_i(instruction)
            shamt = (instruction >> 20) & 0x1F
            if funct3 == 0b000:
                value = (a + immediate) & MASK
            elif funct3 == 0b010:
                value = 1 if to_signed(a) < immediate else 0
            elif funct3 == 0b011:
                value = 1 if a < (immediate & MASK) else 0
            elif funct3 == 0b100:
                value = (a ^ immediate) & MASK
            elif funct3 == 0b110:
                value = (a | immediate) & MASK
            elif funct3 == 0b111:
                value = (a & immediate) & MASK
            elif funct3 == 0b001:
                value = (a << shamt) & MASK
            elif funct3 == 0b101:
                if funct7 == 0b0100000:
                    value = (to_signed(a) >> shamt) & MASK
                else:
                    value = (a & MASK) >> shamt
            else:
                raise Trap("illegal-op-imm", pc, instruction)
            written_register, written_value = rd, value

        elif opcode == 0b0110011:  # register-register
            shamt = b & 0x1F
            if funct3 == 0b000:
                value = ((a - b) if funct7 == 0b0100000 else (a + b)) & MASK
            elif funct3 == 0b001:
                value = (a << shamt) & MASK
            elif funct3 == 0b010:
                value = 1 if to_signed(a) < to_signed(b) else 0
            elif funct3 == 0b011:
                value = 1 if a < b else 0
            elif funct3 == 0b100:
                value = a ^ b
            elif funct3 == 0b101:
                if funct7 == 0b0100000:
                    value = (to_signed(a) >> shamt) & MASK
                else:
                    value = a >> shamt
            elif funct3 == 0b110:
                value = a | b
            elif funct3 == 0b111:
                value = a & b
            else:
                raise Trap("illegal-op", pc, instruction)
            written_register, written_value = rd, value

        elif opcode == 0b0001111:  # FENCE: ordering only, no visible state
            pass

        elif opcode == 0b1110011:  # ECALL / EBREAK
            raise Trap("ecall" if ((instruction >> 20) & 0xFFF) == 0 else "ebreak",
                       pc, instruction)

        else:
            raise Trap("illegal-opcode", pc, instruction)

        # RV32I without the C extension has IALIGN=32, so a control-flow target
        # that is not four-byte aligned raises instruction-address-misaligned.
        # B- and J-immediates encode multiples of two, so this is reachable.
        # The model omitted it, exactly as the RTL did: both were written by the
        # same author from the same reading, and the random corpus never built a
        # misaligned target. Formal verification found it.
        #
        # A trapping instruction commits nothing, so the link register of a
        # trapping JAL or JALR is not written.
        if next_pc & 0b11 and opcode in (0b1101111, 0b1100111, 0b1100011):
            raise Trap("misaligned-fetch", pc, instruction)

        if written_register is not None:
            self.write(written_register, written_value)
        self.pc = next_pc
        self.retired += 1
        return {
            "pc": pc,
            "instruction": instruction,
            "rd": written_register if written_register else None,
            "value": self.read(written_register) if written_register else None,
            "memory_write": memory_write,
            "next_pc": next_pc,
        }

    def run(self, limit: int) -> str:
        for _ in range(limit):
            try:
                self.step()
            except Trap as trap:
                return trap.kind
        return "instruction-limit"

    def signature(self) -> bytes:
        """Architectural state as bytes: x1..x31 then the program counter."""
        out = bytearray()
        for index in range(1, 32):
            out += self.x[index].to_bytes(4, "little")
        out += self.pc.to_bytes(4, "little")
        return bytes(out)
