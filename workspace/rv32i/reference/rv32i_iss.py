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
    """Raised when the simulation must stop.

    Before the privileged subset existed this stood for both "the program hit
    an exception" and "the simulation is over", because a trap always halted
    the core. With a trap vector those are different events: an exception is
    ordinary architectural behaviour that the hart handles and continues from,
    while stopping is something only the environment decides. This exception
    now means only the second.
    """

    def __init__(self, kind: str, pc: int, instruction: int) -> None:
        super().__init__(f"{kind} at pc={pc:#010x} instruction={instruction:#010x}")
        self.kind = kind
        self.pc = pc
        self.instruction = instruction


# Machine-mode exception causes, from the privileged specification.
CAUSE_INSTRUCTION_MISALIGNED = 0
CAUSE_ILLEGAL_INSTRUCTION = 2
CAUSE_BREAKPOINT = 3
CAUSE_LOAD_MISALIGNED = 4
CAUSE_STORE_MISALIGNED = 6
CAUSE_ECALL_M = 11

# CSR addresses. The top two bits encode read-only when they are 0b11.
CSR_MSTATUS, CSR_MISA, CSR_MIE, CSR_MTVEC = 0x300, 0x301, 0x304, 0x305
CSR_MCOUNTEREN, CSR_MSTATUSH, CSR_MCOUNTINHIBIT = 0x306, 0x310, 0x320
CSR_MSCRATCH, CSR_MEPC, CSR_MCAUSE, CSR_MTVAL, CSR_MIP = 0x340, 0x341, 0x342, 0x343, 0x344
CSR_MCYCLE, CSR_MINSTRET, CSR_MCYCLEH, CSR_MINSTRETH = 0xB00, 0xB02, 0xB80, 0xB82
CSR_CYCLE, CSR_INSTRET, CSR_CYCLEH, CSR_INSTRETH = 0xC00, 0xC02, 0xC80, 0xC82
CSR_MVENDORID, CSR_MARCHID, CSR_MIMPID, CSR_MHARTID = 0xF11, 0xF12, 0xF13, 0xF14

# misa for RV32I: MXL=1 in the top two bits, extension bit I.
MISA_RV32I = (1 << 30) | (1 << 8)

# mstatus bits this implementation keeps. MPP is hardwired to machine mode
# because no other privilege level exists here.
MSTATUS_MIE = 1 << 3
MSTATUS_MPIE = 1 << 7
MSTATUS_MPP = 0b11 << 11
MSTATUS_WRITABLE = MSTATUS_MIE | MSTATUS_MPIE

# Only the standard machine interrupt-enable bits are writable; nothing raises
# an interrupt in this implementation, so mip reads as zero.
MIE_WRITABLE = (1 << 3) | (1 << 7) | (1 << 11)


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

    def __init__(self, memory: Memory, pc: int = 0,
                 halt_address: int | None = None) -> None:
        self.x = [0] * 32
        self.pc = pc & MASK
        self.memory = memory
        self.retired = 0
        # A store to this address ends the simulation. This is the HTIF
        # convention the Sail model, the certification framework, and every
        # testbench here now share. Before the privileged subset existed the
        # cores stopped at ebreak; with a trap vector, ebreak is handled and
        # execution continues, so stopping had to become something the
        # environment decides rather than something the ISA does.
        self.halt_address = halt_address
        self.csr = {
            # mstatus resets to zero, including MPP. The privileged
            # specification leaves most mstatus reset values implementation
            # defined, and hardwiring MPP to machine mode was equally legal,
            # but the Sail model resets it to zero and the certification suite
            # compares against Sail. Every later transition -- trap entry, MRET,
            # and an explicit write -- was already identical between the two.
            CSR_MSTATUS: 0,
            CSR_MISA: MISA_RV32I,
            CSR_MIE: 0, CSR_MTVEC: 0, CSR_MSCRATCH: 0,
            CSR_MEPC: 0, CSR_MCAUSE: 0, CSR_MTVAL: 0,
            CSR_MCOUNTEREN: 0, CSR_MCOUNTINHIBIT: 0,
            CSR_MCYCLE: 0, CSR_MINSTRET: 0, CSR_MCYCLEH: 0, CSR_MINSTRETH: 0,
        }

    # --- control and status registers -----------------------------------
    def csr_read(self, address: int) -> int:
        """Read a CSR, or raise KeyError for one this implementation lacks."""
        if address in (CSR_MVENDORID, CSR_MARCHID, CSR_MIMPID, CSR_MHARTID):
            return 0                                    # read-only zero
        if address == CSR_MIP:
            return 0                                    # nothing raises interrupts
        if address == CSR_MSTATUSH:
            return 0
        if address in (CSR_CYCLE, CSR_MCYCLE):
            return self.csr[CSR_MCYCLE]
        if address in (CSR_CYCLEH, CSR_MCYCLEH):
            return self.csr[CSR_MCYCLEH]
        if address in (CSR_INSTRET, CSR_MINSTRET):
            return self.csr[CSR_MINSTRET]
        if address in (CSR_INSTRETH, CSR_MINSTRETH):
            return self.csr[CSR_MINSTRETH]
        return self.csr[address]

    def csr_write(self, address: int, value: int) -> None:
        """Write a CSR, applying the WARL masking each register defines."""
        value &= MASK
        if address == CSR_MSTATUS:
            # MPP is WARL. Machine is the only implemented privilege level, so
            # a write selecting supervisor or the reserved encoding reads back
            # as machine; zero is retained, matching the model.
            mpp = (value >> 11) & 0b11
            if mpp not in (0b00, 0b11):
                mpp = 0b11
            self.csr[CSR_MSTATUS] = (value & MSTATUS_WRITABLE) | (mpp << 11)
        elif address == CSR_MISA:
            pass                                        # read-only in this design
        elif address == CSR_MIE:
            self.csr[CSR_MIE] = value & MIE_WRITABLE
        elif address == CSR_MTVEC:
            # Base is four-byte aligned; mode is WARL and only direct and
            # vectored are legal, so anything else reads back as direct.
            mode = value & 0b11
            self.csr[CSR_MTVEC] = (value & ~0b11) | (mode if mode < 2 else 0)
        elif address == CSR_MEPC:
            self.csr[CSR_MEPC] = value & ~0b11          # IALIGN is 32 here
        elif address in (CSR_MIP, CSR_MSTATUSH):
            pass                                        # read-only zero
        elif address in (CSR_MVENDORID, CSR_MARCHID, CSR_MIMPID, CSR_MHARTID):
            raise KeyError(address)                     # read-only: illegal to write
        else:
            self.csr[address] = value

    def take_trap(self, cause: int, tval: int, pc: int) -> None:
        """Enter machine mode: record the cause and vector to mtvec."""
        status = self.csr[CSR_MSTATUS]
        previous_mie = 1 if status & MSTATUS_MIE else 0
        status &= ~(MSTATUS_MIE | MSTATUS_MPIE)
        status |= MSTATUS_MPP | (MSTATUS_MPIE if previous_mie else 0)
        self.csr[CSR_MSTATUS] = status
        self.csr[CSR_MEPC] = pc & ~0b11
        self.csr[CSR_MCAUSE] = cause & MASK
        self.csr[CSR_MTVAL] = tval & MASK
        # Exceptions vector to the base regardless of the mode field; only
        # interrupts use the vectored offset, and none exist here.
        self.pc = self.csr[CSR_MTVEC] & ~0b11

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

    def _exception(self, cause: int, tval: int, pc: int,
                   instruction: int) -> dict[str, Any]:
        """Take an exception and return the record for the faulting instruction."""
        self.take_trap(cause, tval, pc)
        self.retired += 1
        self._count()
        return {"pc": pc, "instruction": instruction, "rd": None, "value": None,
                "memory_write": None, "next_pc": self.pc, "trap": cause}

    def _count(self) -> None:
        """Advance the retired-instruction counters unless inhibited.

        mcycle counts retired instructions here rather than clock cycles: a
        model with no pipeline has no cycles to count. The RTL counts real
        cycles, so the two disagree by construction and mcycle is therefore
        excluded from differential stimulus. minstret means the same thing in
        both and is not excluded.
        """
        inhibit = self.csr[CSR_MCOUNTINHIBIT]
        if not inhibit & 0b001:
            low = (self.csr[CSR_MCYCLE] + 1) & MASK
            if low == 0:
                self.csr[CSR_MCYCLEH] = (self.csr[CSR_MCYCLEH] + 1) & MASK
            self.csr[CSR_MCYCLE] = low
        if not inhibit & 0b100:
            low = (self.csr[CSR_MINSTRET] + 1) & MASK
            if low == 0:
                self.csr[CSR_MINSTRETH] = (self.csr[CSR_MINSTRETH] + 1) & MASK
            self.csr[CSR_MINSTRET] = low

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
                return self._exception(CAUSE_ILLEGAL_INSTRUCTION, instruction,
                                   pc, instruction)
            if taken:
                next_pc = (pc + offset) & MASK

        elif opcode == 0b0000011:  # loads
            address = (a + self.imm_i(instruction)) & MASK
            width = {0b000: 1, 0b100: 1, 0b001: 2, 0b101: 2, 0b010: 4}.get(funct3)
            if width is None:
                return self._exception(CAUSE_ILLEGAL_INSTRUCTION, instruction,
                                       pc, instruction)
            if address % width:
                return self._exception(CAUSE_LOAD_MISALIGNED, address, pc, instruction)
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
                return self._exception(CAUSE_ILLEGAL_INSTRUCTION, instruction,
                                   pc, instruction)
            written_register, written_value = rd, value

        elif opcode == 0b0100011:  # stores
            address = (a + self.imm_s(instruction)) & MASK
            width = {0b000: 1, 0b001: 2, 0b010: 4}.get(funct3)
            if width is None:
                return self._exception(CAUSE_ILLEGAL_INSTRUCTION, instruction,
                                       pc, instruction)
            if address % width:
                return self._exception(CAUSE_STORE_MISALIGNED, address, pc, instruction)
            if self.halt_address is not None and address == self.halt_address:
                raise Trap("halt", pc, instruction)
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
                return self._exception(CAUSE_ILLEGAL_INSTRUCTION, instruction,
                                   pc, instruction)
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
                return self._exception(CAUSE_ILLEGAL_INSTRUCTION, instruction,
                                   pc, instruction)
            written_register, written_value = rd, value

        elif opcode == 0b0001111:  # FENCE: ordering only, no visible state
            pass

        elif opcode == 0b1110011:  # SYSTEM: ECALL, EBREAK, MRET, WFI, Zicsr
            funct12 = (instruction >> 20) & 0xFFF
            if funct3 == 0:
                if funct12 == 0x000:
                    return self._exception(CAUSE_ECALL_M, 0, pc, instruction)
                if funct12 == 0x001:
                    return self._exception(CAUSE_BREAKPOINT, pc, pc, instruction)
                if funct12 == 0x302:                      # MRET
                    status = self.csr[CSR_MSTATUS]
                    mpie = 1 if status & MSTATUS_MPIE else 0
                    status &= ~MSTATUS_MIE
                    status |= (MSTATUS_MIE if mpie else 0) | MSTATUS_MPIE | MSTATUS_MPP
                    self.csr[CSR_MSTATUS] = status
                    next_pc = self.csr[CSR_MEPC] & ~0b11
                elif funct12 == 0x105:                    # WFI: no interrupts, so a nop
                    pass
                else:
                    return self._exception(CAUSE_ILLEGAL_INSTRUCTION, instruction,
                                           pc, instruction)
            else:
                address = funct12
                immediate_form = funct3 & 0b100
                source = rs1 if not immediate_form else rs1   # zimm shares the rs1 field
                operand = (rs1 & 0x1F) if immediate_form else a
                writes = True
                if (funct3 & 0b011) == 0b001:             # csrrw / csrrwi
                    reads = rd != 0
                else:                                      # set and clear forms
                    reads = True
                    writes = source != 0
                read_only = (address >> 10) == 0b11
                if writes and read_only:
                    return self._exception(CAUSE_ILLEGAL_INSTRUCTION, instruction,
                                           pc, instruction)
                try:
                    old_value = self.csr_read(address) if reads else 0
                except KeyError:
                    return self._exception(CAUSE_ILLEGAL_INSTRUCTION, instruction,
                                           pc, instruction)
                if writes:
                    operation = funct3 & 0b011
                    if operation == 0b001:
                        new_value = operand
                    elif operation == 0b010:
                        new_value = old_value | operand
                    else:
                        new_value = old_value & ~operand
                    try:
                        self.csr_write(address, new_value)
                    except KeyError:
                        return self._exception(CAUSE_ILLEGAL_INSTRUCTION, instruction,
                                               pc, instruction)
                written_register, written_value = rd, old_value

        else:
            return self._exception(CAUSE_ILLEGAL_INSTRUCTION, instruction,
                                   pc, instruction)

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
            return self._exception(CAUSE_INSTRUCTION_MISALIGNED, next_pc, pc, instruction)

        if written_register is not None:
            self.write(written_register, written_value)
        self.pc = next_pc
        self.retired += 1
        self._count()
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
