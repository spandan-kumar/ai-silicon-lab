#!/usr/bin/env python3
"""Generate a tiny hand-encoded RV32IM binary for RTL/harness bring-up."""

import pathlib
import struct
import sys


def i_type(immediate: int, rs1: int, funct3: int, rd: int, opcode: int = 0x13) -> int:
    return ((immediate & 0xFFF) << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | opcode


def lui(rd: int, upper: int) -> int:
    return ((upper & 0xFFFFF) << 12) | (rd << 7) | 0x37


def store_word(rs2: int, rs1: int, offset: int) -> int:
    immediate = offset & 0xFFF
    return (
        ((immediate >> 5) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (2 << 12)
        | ((immediate & 0x1F) << 7)
        | 0x23
    )


def m_op(rd: int, rs1: int, rs2: int, funct3: int) -> int:
    return (1 << 25) | (rs2 << 20) | (rs1 << 15) | (funct3 << 12) | (rd << 7) | 0x33


def branch_not_equal(rs1: int, rs2: int, offset: int) -> int:
    immediate = offset & 0x1FFF
    return (
        (((immediate >> 12) & 1) << 31)
        | (((immediate >> 5) & 0x3F) << 25)
        | (rs2 << 20)
        | (rs1 << 15)
        | (1 << 12)
        | (((immediate >> 1) & 0xF) << 8)
        | (((immediate >> 11) & 1) << 7)
        | 0x63
    )


def addi(rd: int, rs1: int, immediate: int) -> int:
    return i_type(immediate, rs1, 0, rd)


def emit_li(words: list[int], rd: int, value: int) -> None:
    value &= 0xFFFFFFFF
    upper = (value + 0x800) >> 12
    lower = value - (upper << 12)
    if upper:
        words.append(lui(rd, upper))
        words.append(addi(rd, rd, lower))
    else:
        words.append(addi(rd, 0, lower))


def generate_firmware() -> bytes:
    words: list[int] = []
    branches: list[int] = []

    emit_li(words, 5, 0x10000000)  # x5: MMIO base
    emit_li(words, 6, ord("O"))
    words.append(store_word(6, 5, 0x00))
    emit_li(words, 6, ord("K"))
    words.append(store_word(6, 5, 0x00))
    emit_li(words, 6, ord("\n"))
    words.append(store_word(6, 5, 0x00))

    emit_li(words, 6, 1)
    words.append(store_word(6, 5, 0x04))  # boot
    emit_li(words, 6, 2)
    words.append(store_word(6, 5, 0x04))  # Doom started

    emit_li(words, 1, 7)
    emit_li(words, 2, 6)
    words.append(m_op(3, 1, 2, 0))  # mul x3,x1,x2
    emit_li(words, 4, 42)
    branches.append(len(words))
    words.append(0)

    emit_li(words, 2, 84)
    words.append(m_op(3, 2, 1, 4))  # div x3,x2,x1
    emit_li(words, 4, 12)
    branches.append(len(words))
    words.append(0)

    emit_li(words, 6, 0x00100000)  # framebuffer
    emit_li(words, 7, 0x00112233)
    words.append(store_word(7, 6, 0))
    emit_li(words, 7, 0x00A0B0C0)
    words.append(store_word(7, 6, 4))
    words.append(store_word(6, 5, 0x08))
    words.append(store_word(0, 5, 0x0C))

    emit_li(words, 6, 1)
    words.append(store_word(6, 5, 0x30))
    emit_li(words, 6, 123)
    words.append(store_word(6, 5, 0x34))
    emit_li(words, 6, 1)
    words.append(store_word(6, 5, 0x38))
    words.append(store_word(0, 5, 0x3C))
    emit_li(words, 6, 3)
    words.append(store_word(6, 5, 0x04))  # capture
    emit_li(words, 6, 4)
    words.append(store_word(6, 5, 0x04))  # finish
    words.append(0x0000006F)  # jal x0,0 if the harness does not stop

    fail_word_index = len(words)
    emit_li(words, 6, 1)
    words.append(store_word(6, 5, 0x3C))
    emit_li(words, 6, 0xDEAD)
    words.append(store_word(6, 5, 0x04))
    words.append(0x00100073)  # ebreak

    # Word zero starts at PC 0.
    for branch_index in branches:
        branch_pc = branch_index * 4
        fail_pc = fail_word_index * 4
        words[branch_index] = branch_not_equal(3, 4, fail_pc - branch_pc)

    output = bytearray()
    for word in words:
        output.extend(struct.pack("<I", word))
    return bytes(output)


def main() -> None:
    if len(sys.argv) != 2:
        raise SystemExit(f"usage: {sys.argv[0]} OUTPUT_DIR")
    destination = pathlib.Path(sys.argv[1])
    destination.mkdir(parents=True, exist_ok=True)
    (destination / "firmware.bin").write_bytes(generate_firmware())
    (destination / "test.wad").write_bytes(b"PWAD\x00\x00\x00\x00\x0c\x00\x00\x00")
    (destination / "input.events").write_text("80 w 1\n98 w 0\n", encoding="ascii")


if __name__ == "__main__":
    main()
