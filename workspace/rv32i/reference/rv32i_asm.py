#!/usr/bin/env python3
"""RV32I instruction encoder and constrained-random program generator.

No RISC-V toolchain exists on this host, and requiring one would make the
experiment depend on a large download. Encoding instructions directly is also
better for ISA verification: it reaches encodings a compiler would never emit,
including hazard patterns, x0 as a destination, and boundary immediates.

The encoder is written from the same specification section as the ISS. It is
checked against CV32E40P's decoder, which is independent of both.
"""

from __future__ import annotations

from typing import Iterator


MASK = 0xFFFFFFFF

R_OPS = {
    "add": (0b000, 0b0000000), "sub": (0b000, 0b0100000),
    "sll": (0b001, 0b0000000), "slt": (0b010, 0b0000000),
    "sltu": (0b011, 0b0000000), "xor": (0b100, 0b0000000),
    "srl": (0b101, 0b0000000), "sra": (0b101, 0b0100000),
    "or": (0b110, 0b0000000), "and": (0b111, 0b0000000),
}
I_OPS = {"addi": 0b000, "slti": 0b010, "sltiu": 0b011,
         "xori": 0b100, "ori": 0b110, "andi": 0b111}
SHIFT_OPS = {"slli": (0b001, 0b0000000), "srli": (0b101, 0b0000000),
             "srai": (0b101, 0b0100000)}
LOAD_OPS = {"lb": 0b000, "lh": 0b001, "lw": 0b010, "lbu": 0b100, "lhu": 0b101}
STORE_OPS = {"sb": 0b000, "sh": 0b001, "sw": 0b010}
BRANCH_OPS = {"beq": 0b000, "bne": 0b001, "blt": 0b100,
              "bge": 0b101, "bltu": 0b110, "bgeu": 0b111}


def _check(value: int, low: int, high: int, name: str) -> int:
    if not low <= value <= high:
        raise ValueError(f"{name} {value} outside [{low}, {high}]")
    return value


def r_type(name: str, rd: int, rs1: int, rs2: int) -> int:
    funct3, funct7 = R_OPS[name]
    return (funct7 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | 0b0110011


def i_type(name: str, rd: int, rs1: int, imm: int) -> int:
    _check(imm, -2048, 2047, "I-immediate")
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (I_OPS[name] << 12) | (rd << 7) | 0b0010011


def shift_imm(name: str, rd: int, rs1: int, shamt: int) -> int:
    funct3, funct7 = SHIFT_OPS[name]
    _check(shamt, 0, 31, "shamt")
    return (funct7 << 25) | (shamt << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | 0b0010011


def load(name: str, rd: int, rs1: int, imm: int) -> int:
    _check(imm, -2048, 2047, "load offset")
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (LOAD_OPS[name] << 12) | (rd << 7) | 0b0000011


def store(name: str, rs1: int, rs2: int, imm: int) -> int:
    _check(imm, -2048, 2047, "store offset")
    imm &= 0xFFF
    return (((imm >> 5) & 0x7F) << 25) | (rs2 << 20) | (rs1 << 15) \
        | (STORE_OPS[name] << 12) | ((imm & 0x1F) << 7) | 0b0100011


def branch(name: str, rs1: int, rs2: int, offset: int) -> int:
    _check(offset, -4096, 4094, "branch offset")
    if offset & 1:
        raise ValueError("branch offset must be even")
    imm = offset & 0x1FFF
    return ((((imm >> 12) & 1) << 31) | (((imm >> 5) & 0x3F) << 25) | (rs2 << 20)
            | (rs1 << 15) | (BRANCH_OPS[name] << 12) | (((imm >> 1) & 0xF) << 8)
            | (((imm >> 11) & 1) << 7) | 0b1100011)


def lui(rd: int, imm20: int) -> int:
    return ((imm20 & 0xFFFFF) << 12) | (rd << 7) | 0b0110111


def auipc(rd: int, imm20: int) -> int:
    return ((imm20 & 0xFFFFF) << 12) | (rd << 7) | 0b0010111


def jal(rd: int, offset: int) -> int:
    _check(offset, -1048576, 1048574, "jal offset")
    if offset & 1:
        raise ValueError("jal offset must be even")
    imm = offset & 0x1FFFFF
    return ((((imm >> 20) & 1) << 31) | (((imm >> 1) & 0x3FF) << 21)
            | (((imm >> 11) & 1) << 20) | (((imm >> 12) & 0xFF) << 12)
            | (rd << 7) | 0b1101111)


def jalr(rd: int, rs1: int, imm: int) -> int:
    _check(imm, -2048, 2047, "jalr offset")
    return ((imm & 0xFFF) << 20) | (rs1 << 15) | (0b000 << 12) | (rd << 7) | 0b1100111


def ebreak() -> int:
    return (1 << 20) | 0b1110011


def nop() -> int:
    return i_type("addi", 0, 0, 0)


def assemble(words: list[int]) -> bytes:
    return b"".join(word.to_bytes(4, "little") for word in words)


class Xorshift32:
    """Portable reproducible generator; identical definition to the AES corpus."""

    def __init__(self, seed: int) -> None:
        self.state = (seed & MASK) or 0x1234_5678

    def next(self) -> int:
        x = self.state
        x ^= (x << 13) & MASK
        x ^= x >> 17
        x ^= (x << 5) & MASK
        self.state = x & MASK
        return self.state

    def below(self, bound: int) -> int:
        return self.next() % bound if bound > 0 else 0

    def pick(self, items):
        return items[self.below(len(items))]

    def signed(self, bits: int) -> int:
        span = 1 << bits
        return self.below(span) - (span >> 1)


# Registers the generator may use as destinations. x0 is included on purpose:
# writes to it must be discarded, which is a classic source of core bugs.
DEST_REGS = list(range(0, 32))
SRC_REGS = list(range(0, 32))

# Interesting immediates: boundaries and sign-change points, not just uniform
# random values. Uniform random rarely hits the cases that break a design.
CORNER_IMMEDIATES = [0, 1, -1, 2047, -2048, -2047, 2046, 4, -4, 0x7FF, -0x800]


# Registers the generator reserves. x31 holds the data pointer; x29 is the
# scratch used to build a JALR target; x28 is a bounded-loop counter.
DATA_POINTER = 31
JALR_SCRATCH = 29
LOOP_COUNTER = 28
RESERVED = {DATA_POINTER, JALR_SCRATCH, LOOP_COUNTER}


def random_program(
    seed: int,
    length: int,
    *,
    data_base: int = 0x1000,
    data_size: int = 0x400,
    allow_memory: bool = True,
    allow_control_flow: bool = True,
    version: int = 2,
) -> list[int]:
    """Generate a terminating random RV32I program.

    Control flow is constrained so the program always terminates and stays
    inside the code region. That is a stimulus constraint, not a claim about
    what the ISA permits.

    `version` selects the stimulus generation used, so a workflow change can be
    measured against the workflow it replaced rather than asserted to be better:

    * version 1 -- forward branches and JAL only. Measured on this core it left
      JALR entirely unexecuted while reporting every program as passing.
    * version 2 -- adds JALR via an AUIPC-built target with a deliberately odd
      offset, bounded backward-branch loops, and store/load pairs to the same
      address.
    """
    if version >= 3:
        return random_program_blocks(seed, length, data_base=data_base,
                                     data_size=data_size)

    rng = Xorshift32(seed)
    program: list[int] = []

    # Prologue: put a valid, in-range data pointer in x31 and seed some
    # registers with varied values so later instructions have real operands.
    program.append(lui(31, data_base >> 12))
    for reg in range(1, 8):
        program.append(lui(reg, rng.below(0x100000)))
        program.append(i_type("addi", reg, reg, rng.signed(12)))

    body_start = len(program)
    while len(program) - body_start < length:
        remaining = length - (len(program) - body_start)

        # Version 2 constructs are drawn from their own roll so that they add
        # to the version 1 mix instead of displacing part of it. Displacing it
        # is exactly what the first attempt did: the new cases took over the
        # dispatch range that produced forward branches and JAL, and coverage
        # fell from 36 instructions to 31 while every program still passed.
        if version >= 2 and remaining > 8:
            special = rng.below(100)
            rd = rng.pick(DEST_REGS)
            rs1 = rng.pick(SRC_REGS)
            rs2 = rng.pick(SRC_REGS)
            if rd in RESERVED:
                rd = 30

            if special < 4:
                # JALR with a target built from the current PC. The offset is
                # sometimes odd on purpose: the specification requires the low
                # bit of the computed target to be cleared, and nothing else
                # in the corpus exercises that rule.
                skip = 2 + rng.below(2)
                program.append(auipc(JALR_SCRATCH, 0))
                program.append(jalr(rng.pick([0, rd]), JALR_SCRATCH,
                                    4 * skip + (1 if rng.below(2) else 0)))
                for _ in range(skip - 2):
                    program.append(r_type("add", rd, rs1, rs2))
                continue

            if special < 7:
                # A bounded backward branch. The body never writes the counter,
                # so the loop always terminates.
                iterations = 2 + rng.below(3)
                body = 1 + rng.below(2)
                program.append(i_type("addi", LOOP_COUNTER, 0, iterations))
                for _ in range(body):
                    program.append(r_type(rng.pick(list(R_OPS)), rd, rs1, rs2))
                program.append(i_type("addi", LOOP_COUNTER, LOOP_COUNTER, -1))
                program.append(branch("bne", LOOP_COUNTER, 0, -4 * (body + 1)))
                continue

            if special < 11 and allow_memory:
                # Store then load the same address, so lane selection is
                # exercised against data that was just written.
                width_name = rng.pick(["sb", "sh", "sw"])
                width = {"sb": 1, "sh": 2, "sw": 4}[width_name]
                offset = rng.below(data_size // width) * width
                load_name = {"sb": rng.pick(["lb", "lbu"]),
                             "sh": rng.pick(["lh", "lhu"]),
                             "sw": "lw"}[width_name]
                program.append(store(width_name, DATA_POINTER, rs2, offset))
                program.append(load(load_name, rd, DATA_POINTER, offset))
                continue

        kind = rng.below(100)
        rd = rng.pick(DEST_REGS)
        rs1 = rng.pick(SRC_REGS)
        rs2 = rng.pick(SRC_REGS)
        # Ordinary instructions must not clobber the reserved registers.
        if rd in RESERVED:
            rd = 30

        if kind < 26:
            program.append(r_type(rng.pick(list(R_OPS)), rd, rs1, rs2))
        elif kind < 44:
            imm = rng.pick(CORNER_IMMEDIATES) if rng.below(3) == 0 else rng.signed(12)
            program.append(i_type(rng.pick(list(I_OPS)), rd, rs1, imm))
        elif kind < 54:
            program.append(shift_imm(rng.pick(list(SHIFT_OPS)), rd, rs1, rng.below(32)))
        elif kind < 60:
            program.append(lui(rd, rng.below(0x100000)))
        elif kind < 65:
            program.append(auipc(rd, rng.below(0x100000)))
        elif kind < 78 and allow_memory:
            name = rng.pick(list(LOAD_OPS))
            width = {"lb": 1, "lbu": 1, "lh": 2, "lhu": 2, "lw": 4}[name]
            offset = rng.below(data_size // width) * width
            program.append(load(name, rd, DATA_POINTER, offset))
        elif kind < 88 and allow_memory:
            name = rng.pick(list(STORE_OPS))
            width = {"sb": 1, "sh": 2, "sw": 4}[name]
            offset = rng.below(data_size // width) * width
            program.append(store(name, DATA_POINTER, rs2, offset))
        elif kind < 96 and allow_control_flow and remaining > 4:
            skip = 1 + rng.below(3)
            program.append(branch(rng.pick(list(BRANCH_OPS)), rs1, rs2, 4 * (skip + 1)))
        elif allow_control_flow and remaining > 4:
            skip = 1 + rng.below(2)
            program.append(jal(rd, 4 * (skip + 1)))
        else:
            program.append(r_type("add", rd, rs1, rs2))

    program.append(ebreak())
    return program


# --- version 3: block-structured generation -------------------------------
#
# Versions 1 and 2 emit a flat instruction list and compute branch offsets in
# instruction counts. That is safe only while every instruction is independent.
# It stopped being safe the moment version 2 introduced constructs that span
# several instructions and depend on their own first instruction having run:
# a forward branch generated earlier can land in the middle of a loop, skipping
# the counter initialiser, and the program never terminates. Measured on 60
# programs, 14 failed to terminate for exactly this reason.
#
# Version 3 makes the unit of generation a block instead of an instruction.
# Blocks are atomic, and every control-flow target is a block boundary, so no
# jump can land inside a construct. Offsets are resolved in a second pass once
# block positions are known.



def _signed_offset(rng: "Xorshift32", data_size: int, width: int) -> int:
    """A width-aligned offset on either side of the data pointer."""
    slots = data_size // width
    return (rng.below(slots) - slots // 2) * width


class _Block:
    __slots__ = ("words", "control")

    def __init__(self, words: list[int], control: dict | None = None) -> None:
        self.words = words
        self.control = control          # patched once block offsets are known


def _resolve(blocks: list[_Block]) -> list[int]:
    """Second pass: place blocks, then encode every control-flow target."""
    offsets: list[int] = []
    position = 0
    for block in blocks:
        offsets.append(position)
        position += len(block.words)
    end = position

    program: list[int] = []
    for index, block in enumerate(blocks):
        words = list(block.words)
        control = block.control
        if control is not None:
            # Clamp to the last block, which is the terminating ebreak. Landing
            # past it runs into memory the image never wrote, which decodes as
            # an all-zero illegal instruction rather than ending the program.
            target_block = min(index + control["delta"], len(blocks) - 1)
            target_word = offsets[target_block]
            here = offsets[index] + len(words) - 1
            byte_offset = (target_word - here) * 4
            if control["kind"] == "branch":
                words[-1] = branch(control["op"], control["rs1"], control["rs2"], byte_offset)
            else:
                words[-1] = jal(control["rd"], byte_offset)
        program.extend(words)
    return program


def random_program_blocks(
    seed: int,
    length: int,
    *,
    data_base: int = 0x1000,
    data_size: int = 0x400,
) -> list[int]:
    rng = Xorshift32(seed)
    blocks: list[_Block] = []

    # The data pointer sits in the middle of the region so that offsets on both
    # sides of it are valid. With the pointer at the base, every generated
    # offset is non-negative and a sign-extension defect in the S-immediate is
    # unobservable -- which is exactly how one survived the first mutation run.
    centre = data_base + data_size // 2
    prologue = [lui(DATA_POINTER, centre >> 12),
                i_type("addi", DATA_POINTER, DATA_POINTER, centre & 0xFFF)]
    for reg in range(1, 8):
        prologue.append(lui(reg, rng.below(0x100000)))
        prologue.append(i_type("addi", reg, reg, rng.signed(12)))
    blocks.append(_Block(prologue))

    emitted = 0
    while emitted < length:
        kind = rng.below(100)
        rd = rng.pick(DEST_REGS)
        rs1 = rng.pick(SRC_REGS)
        rs2 = rng.pick(SRC_REGS)
        if rd in RESERVED:
            rd = 30

        if kind < 24:
            block = _Block([r_type(rng.pick(list(R_OPS)), rd, rs1, rs2)])
        elif kind < 40:
            imm = rng.pick(CORNER_IMMEDIATES) if rng.below(3) == 0 else rng.signed(12)
            block = _Block([i_type(rng.pick(list(I_OPS)), rd, rs1, imm)])
        elif kind < 49:
            block = _Block([shift_imm(rng.pick(list(SHIFT_OPS)), rd, rs1, rng.below(32))])
        elif kind < 54:
            block = _Block([lui(rd, rng.below(0x100000))])
        elif kind < 59:
            block = _Block([auipc(rd, rng.below(0x100000))])
        elif kind < 69:
            name = rng.pick(list(LOAD_OPS))
            width = {"lb": 1, "lbu": 1, "lh": 2, "lhu": 2, "lw": 4}[name]
            block = _Block([load(name, rd, DATA_POINTER,
                                 _signed_offset(rng, data_size, width))])
        elif kind < 77:
            name = rng.pick(list(STORE_OPS))
            width = {"sb": 1, "sh": 2, "sw": 4}[name]
            block = _Block([store(name, DATA_POINTER, rs2,
                                  _signed_offset(rng, data_size, width))])
        elif kind < 84:
            # Store then load the same address; lane selection meets data that
            # was just written.
            width_name = rng.pick(["sb", "sh", "sw"])
            width = {"sb": 1, "sh": 2, "sw": 4}[width_name]
            offset = _signed_offset(rng, data_size, width)
            load_name = {"sb": rng.pick(["lb", "lbu"]),
                         "sh": rng.pick(["lh", "lhu"]),
                         "sw": "lw"}[width_name]
            block = _Block([store(width_name, DATA_POINTER, rs2, offset),
                            load(load_name, rd, DATA_POINTER, offset)])
        elif kind < 90:
            # Forward branch. The target is a block boundary, so it can never
            # land inside a construct.
            block = _Block([0], {"kind": "branch", "op": rng.pick(list(BRANCH_OPS)),
                                 "rs1": rs1, "rs2": rs2, "delta": 1 + rng.below(3)})
        elif kind < 93:
            block = _Block([0], {"kind": "jal", "rd": rd, "delta": 1 + rng.below(3)})
        elif kind < 97:
            # JALR through a PC-relative target. The block is `skip` words long
            # and the computed target is exactly one past its end, which is the
            # next block boundary. The offset is sometimes odd on purpose: the
            # specification requires the low bit of the target to be cleared.
            skip = 2 + rng.below(2)
            words = [auipc(JALR_SCRATCH, 0),
                     jalr(rng.pick([0, rd]), JALR_SCRATCH,
                          4 * skip + (1 if rng.below(2) else 0))]
            while len(words) < skip:
                words.append(r_type("add", rd, rs1, rs2))
            block = _Block(words)
        else:
            # Bounded backward loop, entirely inside one block so nothing can
            # enter it past the counter initialiser.
            iterations = 2 + rng.below(3)
            body = 1 + rng.below(2)
            words = [i_type("addi", LOOP_COUNTER, 0, iterations)]
            for _ in range(body):
                words.append(r_type(rng.pick(list(R_OPS)), rd, rs1, rs2))
            words.append(i_type("addi", LOOP_COUNTER, LOOP_COUNTER, -1))
            words.append(branch("bne", LOOP_COUNTER, 0, -4 * (body + 1)))
            block = _Block(words)

        blocks.append(block)
        emitted += len(block.words)

    blocks.append(_Block([ebreak()]))
    return _resolve(blocks)


# --- directed encoding-boundary programs ----------------------------------
#
# Random stimulus cannot reach the high bits of a branch or jump immediate. A
# branch that spans a few blocks encodes an offset of tens of bytes, so B-format
# bits 11 and 12 and J-format bit 11 are always zero and any defect in them is
# invisible. Two mutants survived the first campaign for exactly this reason.
#
# Reaching those bits needs distance, and distance is cheap: padding executes in
# three cycles per instruction. These programs are directed rather than random
# because the property under test is a specific bit position, not a distribution.


def directed_far_branch(op: str, taken: bool, distance_bytes: int = 2052) -> list[int]:
    """Branch over `distance_bytes`, far enough to set immediate bit 11.

    x3 ends at 111 when the branch is taken and 222 when it is not, so the
    outcome is visible in architectural state either way.
    """
    if distance_bytes % 4 or distance_bytes < 12:
        raise ValueError("distance must be a multiple of 4 and at least 12")
    # Operands chosen explicitly per condition. Deriving them from a rule was
    # wrong for bge and bgeu, which produced "not taken" cases that were in
    # fact taken -- a test that silently checks the wrong thing.
    operands = {
        ("beq", True): (5, 5),  ("beq", False): (5, 7),
        ("bne", True): (5, 7),  ("bne", False): (5, 5),
        ("blt", True): (3, 9),  ("blt", False): (9, 3),
        ("bge", True): (9, 3),  ("bge", False): (3, 9),
        ("bltu", True): (3, 9), ("bltu", False): (9, 3),
        ("bgeu", True): (9, 3), ("bgeu", False): (3, 9),
    }
    left, right = operands[(op, taken)]
    program = [
        i_type("addi", 1, 0, left),
        i_type("addi", 2, 0, right),
        i_type("addi", 3, 0, 0),
        branch(op, 1, 2, distance_bytes),
        i_type("addi", 3, 0, 222),
        ebreak(),
    ]
    program += [nop()] * (distance_bytes // 4 - 2)
    program += [i_type("addi", 3, 0, 111), ebreak()]
    return program


def directed_far_jal(distance_bytes: int = 2052) -> list[int]:
    """JAL over `distance_bytes`, setting J-immediate bit 11, checking the link."""
    program = [
        i_type("addi", 3, 0, 0),
        jal(5, distance_bytes),
        i_type("addi", 3, 0, 222),
        ebreak(),
    ]
    program += [nop()] * (distance_bytes // 4 - 2)
    program += [i_type("addi", 3, 0, 111), ebreak()]
    return program


def directed_far_backward_branch(distance_bytes: int = 2048) -> list[int]:
    """A bounded loop whose back edge is a large negative branch offset.

    A negative offset of this size sets B-immediate bit 12 while leaving bit 11
    clear, which is the case that distinguishes the two bits.
    """
    iterations = 2
    program = [i_type("addi", LOOP_COUNTER, 0, iterations), i_type("addi", 3, 0, 0)]
    jal_index = len(program)
    program.append(jal(0, distance_bytes))
    program += [nop()] * (distance_bytes // 4 - 1)
    program.append(i_type("addi", LOOP_COUNTER, LOOP_COUNTER, -1))
    program.append(i_type("addi", 3, 3, 1))
    check_index = len(program)
    program.append(branch("bne", LOOP_COUNTER, 0, -4 * (check_index - jal_index)))
    program.append(ebreak())
    return program


def directed_immediate_extremes() -> list[int]:
    """Boundary immediates for every format that carries one."""
    program = [lui(DATA_POINTER, 0x2), i_type("addi", DATA_POINTER, DATA_POINTER, 0)]
    for value in (2047, -2048, -1, 0, 1):
        program += [
            i_type("addi", 4, 0, value),
            i_type("slti", 5, 4, value),
            i_type("sltiu", 6, 4, value),
            i_type("xori", 7, 4, value),
            i_type("ori", 8, 4, value),
            i_type("andi", 9, 4, value),
        ]
    for shift in (0, 1, 31):
        program += [
            shift_imm("slli", 10, 4, shift),
            shift_imm("srli", 11, 4, shift),
            shift_imm("srai", 12, 4, shift),
        ]
    # Loads and stores at both signs of offset, aligned to their widths.
    for offset in (-2048, -4, 0, 4, 2044):
        program += [store("sw", DATA_POINTER, 4, offset),
                    load("lw", 13, DATA_POINTER, offset),
                    store("sb", DATA_POINTER, 4, offset + 1),
                    load("lb", 14, DATA_POINTER, offset + 1),
                    load("lbu", 15, DATA_POINTER, offset + 1)]
    program += [lui(16, 0xFFFFF), lui(17, 0x00001), auipc(18, 0xFFFFF), auipc(19, 0)]
    program.append(ebreak())
    return program


def directed_programs() -> list[tuple[str, list[int]]]:
    """The directed suite, each entry named so a failure identifies itself."""
    suite: list[tuple[str, list[int]]] = []
    for op in ("beq", "bne", "blt", "bge", "bltu", "bgeu"):
        for taken in (True, False):
            suite.append((f"far-{op}-{'taken' if taken else 'nottaken'}",
                          directed_far_branch(op, taken)))
    suite.append(("far-jal", directed_far_jal()))
    suite.append(("far-jal-4100", directed_far_jal(4100)))
    suite.append(("far-backward-branch", directed_far_backward_branch()))
    suite.append(("immediate-extremes", directed_immediate_extremes()))
    suite.append(("arithmetic-edges", directed_arithmetic_edges()))
    return suite


# --- directed pipeline-hazard programs -------------------------------------
#
# The hazard situations a pipeline gets wrong are conjunctions: a particular
# producer, a particular consumer, and a particular distance between them.
# Random stimulus reaches them only by coincidence. On the pipelined core one
# mutant survived sixty random programs -- forwarding that ignores the validity
# of the MEM stage -- because killing it needs a register written by a squashed
# instruction and read at the branch target, which random code almost never
# lines up.
#
# These programs are written for the pipeline, but they are ordinary RV32I and
# the reference model executes them like any other program, so they cost the
# non-pipelined design nothing.

def _hazard_prologue() -> list[int]:
    return [lui(DATA_POINTER, 0x1), i_type("addi", DATA_POINTER, DATA_POINTER, 0x200)]


def hazard_squashed_writer() -> list[int]:
    """A squashed instruction must not forward its result.

    The two instructions after a taken branch are flushed. If forwarding
    ignores stage validity, their register writes still reach the instruction
    at the branch target.
    """
    program = _hazard_prologue()
    base = len(program)
    program += [
        i_type("addi", 5, 0, 111),      # the value the target must observe
        i_type("addi", 1, 0, 1),
        i_type("addi", 2, 0, 1),
        branch("beq", 1, 2, 12),        # taken: skips the next two
        i_type("addi", 5, 0, 222),      # squashed
        i_type("addi", 5, 0, 333),      # squashed
        r_type("add", 6, 5, 0),         # must read 111
        r_type("add", 7, 0, 5),         # and again as the second operand
        ebreak(),
    ]
    assert len(program) - base == 9
    return program


def hazard_forward_distances() -> list[int]:
    """Producer-consumer pairs at every pipeline distance."""
    program = _hazard_prologue()
    program += [i_type("addi", 1, 0, 7), i_type("addi", 2, 0, 3)]
    # distance 1: EX to EX
    program += [r_type("add", 3, 1, 2), r_type("add", 4, 3, 1)]
    # distance 2: MEM to EX
    program += [r_type("sub", 5, 1, 2), nop(), r_type("add", 6, 5, 1)]
    # distance 3: WB to EX
    program += [r_type("xor", 7, 1, 2), nop(), nop(), r_type("add", 8, 7, 1)]
    # a chain, each element depending on the one before it
    program += [r_type("add", 9, 1, 2), r_type("add", 10, 9, 9),
                r_type("add", 11, 10, 9), r_type("add", 12, 11, 10)]
    # both operands from the immediately preceding instruction
    program += [r_type("add", 13, 1, 2), r_type("add", 14, 13, 13)]
    program.append(ebreak())
    return program


def hazard_load_use() -> list[int]:
    """Load-use interlocks on each operand and at each distance."""
    program = _hazard_prologue()
    program += [i_type("addi", 4, 0, 0x2A), store("sw", DATA_POINTER, 4, 0),
                i_type("addi", 5, 0, -1), store("sw", DATA_POINTER, 5, 4)]
    # rs1 immediately after the load
    program += [load("lw", 1, DATA_POINTER, 0), r_type("add", 2, 1, 0)]
    # rs2 immediately after the load
    program += [load("lw", 6, DATA_POINTER, 0), r_type("add", 7, 0, 6)]
    # both operands from the same load
    program += [load("lw", 8, DATA_POINTER, 4), r_type("add", 9, 8, 8)]
    # one instruction of separation
    program += [load("lw", 10, DATA_POINTER, 0), nop(), r_type("add", 11, 10, 10)]
    # a branch that depends on the load
    program += [load("lw", 12, DATA_POINTER, 4), branch("beq", 12, 0, 8),
                i_type("addi", 13, 0, 1), i_type("addi", 14, 0, 2)]
    # a store whose data comes straight from a load
    program += [load("lw", 15, DATA_POINTER, 0), store("sw", DATA_POINTER, 15, 8),
                load("lw", 16, DATA_POINTER, 8)]
    # narrow loads feeding an immediate consumer
    program += [load("lb", 17, DATA_POINTER, 0), r_type("add", 18, 17, 17),
                load("lhu", 19, DATA_POINTER, 4), r_type("add", 20, 19, 19)]
    program.append(ebreak())
    return program


def hazard_control_dependencies() -> list[int]:
    """Branches and jumps whose operands come from just-computed values."""
    program = _hazard_prologue()
    program += [i_type("addi", 1, 0, 5), i_type("addi", 2, 0, 5)]
    # branch operands produced by the instruction directly before it
    program += [r_type("add", 3, 1, 0), branch("beq", 3, 1, 8),
                i_type("addi", 21, 0, 1), i_type("addi", 22, 0, 2)]
    # two branches back to back
    program += [branch("bne", 1, 2, 8), branch("beq", 1, 2, 8),
                i_type("addi", 23, 0, 3), i_type("addi", 24, 0, 4)]
    # JALR whose base register was just written
    program += [auipc(29, 0), jalr(0, 29, 12), i_type("addi", 25, 0, 9),
                i_type("addi", 26, 0, 10)]
    # a jump immediately after a load
    program += [load("lw", 27, DATA_POINTER, 0), jal(28, 8),
                i_type("addi", 30, 0, 11), i_type("addi", 30, 0, 12)]
    program.append(ebreak())
    return program


def directed_hazard_programs() -> list[tuple[str, list[int]]]:
    return [
        ("hazard-squashed-writer", hazard_squashed_writer()),
        ("hazard-forward-distances", hazard_forward_distances()),
        ("hazard-load-use", hazard_load_use()),
        ("hazard-control-dependencies", hazard_control_dependencies()),
    ]


def directed_arithmetic_edges() -> list[int]:
    """Signed overflow, borrow, and the cases where signed and unsigned differ.

    RV32I has no overflow trap, so overflow is only observable as a wrapped
    result. Random operands reach it inconsistently: the corner bin was covered
    by the flat generator and lost by the block-structured one, because the
    operand distribution changed. A directed test does not depend on the
    distribution.
    """
    program: list[int] = []
    # Build the boundary constants: 0x7fffffff, 0x80000000, 0xffffffff, 1, -1.
    program += [lui(1, 0x80000), i_type("addi", 1, 1, -1)]     # x1 = 0x7fffffff
    program += [lui(2, 0x80000)]                               # x2 = 0x80000000
    program += [i_type("addi", 3, 0, -1)]                      # x3 = 0xffffffff
    program += [i_type("addi", 4, 0, 1)]                       # x4 = 1
    program += [i_type("addi", 5, 0, 0)]                       # x5 = 0

    # Signed overflow in both directions, and a wrap through zero.
    program += [r_type("add", 6, 1, 4)]      # INT_MAX + 1
    program += [r_type("add", 7, 1, 1)]      # INT_MAX + INT_MAX
    program += [r_type("add", 8, 2, 3)]      # INT_MIN + (-1)
    program += [r_type("add", 9, 2, 2)]      # INT_MIN + INT_MIN
    program += [r_type("add", 10, 3, 4)]     # -1 + 1

    # Borrow, including INT_MIN - 1 and 0 - INT_MIN.
    program += [r_type("sub", 11, 5, 4)]     # 0 - 1
    program += [r_type("sub", 12, 2, 4)]     # INT_MIN - 1
    program += [r_type("sub", 13, 5, 2)]     # 0 - INT_MIN
    program += [r_type("sub", 14, 4, 1)]     # 1 - INT_MAX

    # Signed and unsigned comparison disagree exactly when the sign bits differ.
    for a, b in ((2, 4), (3, 4), (1, 2), (3, 1)):
        program += [r_type("slt", 15, a, b), r_type("sltu", 16, a, b),
                    r_type("slt", 17, b, a), r_type("sltu", 18, b, a)]

    # Shifts at both ends against a negative value.
    program += [shift_imm("srai", 19, 2, 31), shift_imm("srli", 20, 2, 31),
                shift_imm("slli", 21, 3, 31), shift_imm("srai", 22, 3, 0)]
    program += [i_type("slti", 23, 2, -1), i_type("sltiu", 24, 2, -1),
                i_type("slti", 25, 1, 2047), i_type("sltiu", 26, 3, -2048)]
    program.append(ebreak())
    return program
