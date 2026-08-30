#!/usr/bin/env python3
"""Minimal ELF32 RISC-V writer.

The Sail model loads ELF files, while the rest of this experiment works with
flat images. Rather than depend on a linker script and a toolchain invocation
for what is a fixed, fully known layout, this emits the ELF directly: one
loadable segment whose file size covers the program and whose memory size
covers the data and signature regions the program writes.

Symbols are emitted because `--test-signature` locates the signature area by
the conventional `begin_signature` and `end_signature` symbols, the same way
riscv-arch-test does.
"""

from __future__ import annotations

import struct

EM_RISCV = 243
ET_EXEC = 2
PT_LOAD = 1
PF_RWX = 7
SHT_PROGBITS, SHT_SYMTAB, SHT_STRTAB = 1, 2, 3


def _string_table(names: list[str]) -> tuple[bytes, dict[str, int]]:
    blob = b"\x00"
    offsets: dict[str, int] = {}
    for name in names:
        offsets[name] = len(blob)
        blob += name.encode() + b"\x00"
    return blob, offsets


def write_elf(image: bytes, entry: int = 0, load_address: int = 0,
              mem_size: int | None = None,
              symbols: dict[str, int] | None = None) -> bytes:
    """Build an ELF32 little-endian RISC-V executable from a flat image."""
    symbols = symbols or {}
    mem_size = max(mem_size or len(image), len(image))

    ehsize, phentsize, shentsize, symsize = 52, 32, 40, 16
    phoff = ehsize
    data_off = phoff + phentsize
    image_padded = image + b"\x00" * ((4 - len(image) % 4) % 4)

    names = ["", ".text", ".symtab", ".strtab", ".shstrtab"]
    shstr, shstr_off = _string_table([n for n in names if n])
    strtab, str_off = _string_table(list(symbols))

    # Symbol table: a null entry followed by one global for each symbol.
    symtab = b"\x00" * symsize
    for name, value in symbols.items():
        # st_name, st_value, st_size, st_info(GLOBAL|NOTYPE), st_other, st_shndx
        symtab += struct.pack("<IIIBBH", str_off[name], value, 0, 0x10, 0, 1)

    symtab_off = data_off + len(image_padded)
    strtab_off = symtab_off + len(symtab)
    shstr_tab_off = strtab_off + len(strtab)
    shoff = shstr_tab_off + len(shstr)
    shoff += (4 - shoff % 4) % 4

    header = struct.pack(
        "<16sHHIIIIIHHHHHH",
        b"\x7fELF\x01\x01\x01" + b"\x00" * 9,
        ET_EXEC, EM_RISCV, 1, entry, phoff, shoff, 0,
        ehsize, phentsize, 1, shentsize, 5, 4,
    )
    phdr = struct.pack("<IIIIIIII", PT_LOAD, data_off, load_address, load_address,
                       len(image_padded), mem_size, PF_RWX, 4)

    def section(name_off: int, kind: int, flags: int, addr: int, offset: int,
                size: int, link: int, info: int, align: int, entsize: int) -> bytes:
        return struct.pack("<IIIIIIIIII", name_off, kind, flags, addr, offset,
                           size, link, info, align, entsize)

    sections = b"".join([
        section(0, 0, 0, 0, 0, 0, 0, 0, 0, 0),
        section(shstr_off[".text"], SHT_PROGBITS, 0x7, load_address, data_off,
                len(image_padded), 0, 0, 4, 0),
        section(shstr_off[".symtab"], SHT_SYMTAB, 0, 0, symtab_off, len(symtab),
                3, 1, 4, symsize),
        section(shstr_off[".strtab"], SHT_STRTAB, 0, 0, strtab_off, len(strtab),
                0, 0, 1, 0),
        section(shstr_off[".shstrtab"], SHT_STRTAB, 0, 0, shstr_tab_off, len(shstr),
                0, 0, 1, 0),
    ])

    blob = header + phdr + image_padded + symtab + strtab + shstr
    blob += b"\x00" * ((4 - len(blob) % 4) % 4)
    return blob + sections
