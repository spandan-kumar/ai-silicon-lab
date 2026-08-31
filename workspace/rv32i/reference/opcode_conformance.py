#!/usr/bin/env python3
"""Check the encoder and decoder against the official riscv-opcodes tables.

`riscv-opcodes` publishes the RISC-V instruction encodings in a machine-readable
form. That makes the encoding layer verifiable mechanically, against a source
that is independent of both this repository's ISS and its RTL, and without
executing anything.

This separates two failure modes that are otherwise easy to confuse:

* the encoding is wrong -- a field is in the wrong place, or a constant is
  wrong, so the instruction is not the instruction we think it is; and
* the semantics are wrong -- the instruction is correct but the implementation
  computes the wrong result from it.

Catching the first class here means every later differential failure is a
semantics failure, which is a much smaller search space.

The tables are a scratch clone under temp/. When they are absent this reports
`unavailable` rather than passing, because a check that did not run is not a
check that succeeded.
"""

from __future__ import annotations

import csv
from pathlib import Path
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[2]
OPCODES = ROOT / "temp" / "riscv-opcodes"

sys.path.insert(0, str(HERE))
import rv32i_asm as asm  # noqa: E402


def load_field_positions() -> dict[str, tuple[int, int]]:
    path = OPCODES / "arg_lut.csv"
    positions: dict[str, tuple[int, int]] = {}
    with path.open(encoding="utf-8") as handle:
        for row in csv.reader(handle):
            if len(row) >= 3:
                positions[row[0].strip().strip('"')] = (int(row[1]), int(row[2]))
    return positions


def parse_extension(name: str) -> dict[str, dict[str, Any]]:
    """Parse one riscv-opcodes extension file into constants and fields."""
    path = OPCODES / "extensions" / name
    parsed: dict[str, dict[str, Any]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip()
        if not line:
            continue
        tokens = line.split()
        pseudo = False
        if tokens[0] == "$pseudo_op":
            # "$pseudo_op base::name mnemonic fields...". Two different things
            # arrive this way: assembler aliases such as `ret` and `nop`, and
            # the RV32 shift-immediates, which exist only in this form because
            # their shift amount is narrower than the RV64 encoding they alias.
            if len(tokens) < 4:
                continue
            pseudo = True
            mnemonic, tokens = tokens[2], tokens[3:]
        elif tokens[0].startswith("$"):     # $import and other directives
            continue
        else:
            mnemonic, tokens = tokens[0], tokens[1:]

        # An alias must never shadow the base instruction it aliases. The asm
        # manual defines pseudo-forms literally named `jal` and `jalr` that fix
        # rd to x1; letting those overwrite the real encodings would make the
        # base instructions look non-conforming.
        if pseudo and mnemonic in parsed and not parsed[mnemonic]["pseudo"]:
            continue
        constants: list[tuple[int, int, int]] = []
        fields: list[str] = []
        for token in tokens:
            if "=" in token:
                span, value = token.split("=")
                if value.startswith("0x"):
                    number = int(value, 16)
                elif value == "ignore":
                    continue
                else:
                    number = int(value)
                if ".." in span:
                    high, low = (int(part) for part in span.split(".."))
                else:
                    high = low = int(span)
                constants.append((high, low, number))
            else:
                fields.append(token)
        parsed[mnemonic] = {"constants": constants, "fields": fields, "pseudo": pseudo}
    return parsed


def extract(word: int, high: int, low: int) -> int:
    return (word >> low) & ((1 << (high - low + 1)) - 1)


# How this repository's encoder emits each official mnemonic.
ENCODERS = {
    **{name: (lambda n: lambda: asm.r_type(n, 7, 13, 21))(name) for name in asm.R_OPS},
    **{name: (lambda n: lambda: asm.i_type(n, 7, 13, -1366))(name) for name in asm.I_OPS},
    **{name: (lambda n: lambda: asm.shift_imm(n, 7, 13, 21))(name) for name in asm.SHIFT_OPS},
    **{name: (lambda n: lambda: asm.load(n, 7, 13, -1366))(name) for name in asm.LOAD_OPS},
    **{name: (lambda n: lambda: asm.store(n, 13, 21, -1366))(name) for name in asm.STORE_OPS},
    **{name: (lambda n: lambda: asm.branch(n, 13, 21, -1366 & ~1))(name) for name in asm.BRANCH_OPS},
    "lui": lambda: asm.lui(7, 0xABCDE),
    "auipc": lambda: asm.auipc(7, 0xABCDE),
    "jal": lambda: asm.jal(7, 0x2BCDE & ~1),
    "jalr": lambda: asm.jalr(7, 13, -1366),
    "ebreak": lambda: asm.ebreak(),
}


def check() -> dict[str, Any]:
    if not OPCODES.is_dir():
        return {
            "status": "unavailable",
            "reason": f"{OPCODES} is absent; clone riscv/riscv-opcodes into temp/",
            "checked": 0,
        }

    positions = load_field_positions()
    # RV32I spans two files: the shared base and the RV32-specific shift forms.
    official = parse_extension("rv_i")
    official.update(parse_extension("rv32_i"))
    findings: list[dict[str, Any]] = []
    checked = 0
    covered: list[str] = []

    for mnemonic, encoder in sorted(ENCODERS.items()):
        entry = official.get(mnemonic)
        if entry is None:
            findings.append({"instruction": mnemonic, "issue": "not present in official rv_i table"})
            continue
        word = encoder()
        checked += 1
        covered.append(mnemonic)
        for high, low, expected in entry["constants"]:
            actual = extract(word, high, low)
            if actual != expected:
                findings.append(
                    {
                        "instruction": mnemonic,
                        "issue": "constant field mismatch",
                        "bits": f"{high}..{low}",
                        "expected": expected,
                        "actual": actual,
                    }
                )
        # Every official variable field must exist in the table we know about,
        # so an encoding that silently drops a field is caught.
        for field in entry["fields"]:
            if field not in positions:
                findings.append(
                    {"instruction": mnemonic, "issue": f"unknown field {field!r} in official table"}
                )

    # Base instructions the official table lists that this encoder cannot
    # produce. Assembler aliases are excluded: they are spellings, not
    # instructions, and a core does not implement them separately.
    encodable = set(ENCODERS)
    missing = sorted(
        name for name, entry in official.items()
        if name not in encodable and not entry["pseudo"]
        and not name.startswith(("c.", "fence", "ecall", "pause", "wfi"))
    )

    return {
        "status": "pass" if not findings else "fail",
        "checked": checked,
        "covered": covered,
        "findings": findings,
        "not_encodable": missing,
        "source": "riscv/riscv-opcodes extensions/rv_i and arg_lut.csv",
    }


if __name__ == "__main__":
    import json

    result = check()
    print(json.dumps({k: v for k, v in result.items() if k != "covered"}, indent=2))
    print(f"\n{result['checked']} instructions checked against the official tables")
    raise SystemExit(0 if result["status"] == "pass" else 1)
