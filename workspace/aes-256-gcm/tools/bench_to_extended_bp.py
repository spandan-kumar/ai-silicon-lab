#!/usr/bin/env python3
"""Convert a NIST-style XAG BENCH file for Extended-BP-Framework.

The generated Python file retains AND gates and affine phases while exposing
the circuit in the input format expected by lemontrr/Extended-BP-Framework.
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path


PORT_RE = re.compile(r"^(INPUT|OUTPUT)\(([^)]+)\)$")
GATE_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_]*)\s*=\s*(AND|XOR|XNOR)\(([^,]+),\s*([^)]+)\)$")
WIRE_RE = re.compile(r"^([ta])(\d+)$")


def wire(name: str) -> str:
    name = name.strip()
    if match := re.fullmatch(r"U(\d+)", name):
        # NIST circuit ports are written most-significant bit first, while the
        # framework's x/y arrays use the numeric bit index.
        return f"x[{7 - int(match.group(1))}]"
    if match := re.fullmatch(r"S(\d+)", name):
        return f"y[{7 - int(match.group(1))}]"
    if match := WIRE_RE.fullmatch(name):
        array = "t" if match.group(1) == "t" else "g"
        return f"{array}[{int(match.group(2))}]"
    raise ValueError(f"unsupported wire name: {name}")


def parse_bench(path: Path) -> tuple[list[str], list[str], list[str]]:
    inputs: list[str] = []
    outputs: list[str] = []
    statements: list[str] = []
    for line_number, raw in enumerate(path.read_text().splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if match := PORT_RE.fullmatch(line):
            (inputs if match.group(1) == "INPUT" else outputs).append(match.group(2))
            continue
        match = GATE_RE.fullmatch(line)
        if not match:
            raise ValueError(f"{path}:{line_number}: unsupported BENCH syntax: {line}")
        lhs, operation, left, right = match.groups()
        operator = "&" if operation == "AND" else "^"
        phase = " ^ 1" if operation == "XNOR" else ""
        statements.append(f"{wire(lhs)} = {wire(left)} {operator} {wire(right)}{phase}")
    if inputs != [f"U{i}" for i in range(8)]:
        raise ValueError(f"expected INPUT(U0)..INPUT(U7), got {inputs}")
    if outputs != [f"S{i}" for i in range(8)]:
        raise ValueError(f"expected OUTPUT(S0)..OUTPUT(S7), got {outputs}")
    return inputs, outputs, statements


def render(statements: list[str], source: Path) -> str:
    body = "\n".join(f"        {statement}" for statement in statements)
    return f'''# Generated from {source.name} by bench_to_extended_bp.py.
def _gf_mul(a, b):
    result = 0
    for _ in range(8):
        if b & 1:
            result ^= a
        a = ((a << 1) ^ (0x11B if a & 0x80 else 0)) & 0xFF
        b >>= 1
    return result


def _aes_reference(value):
    inverse = 0 if value == 0 else 1
    if value:
        for _ in range(254):
            inverse = _gf_mul(inverse, value)
    return inverse ^ ((inverse << 1) | (inverse >> 7) & 1) & 0xFF ^ \\
        ((inverse << 2) | (inverse >> 6) & 3) & 0xFF ^ \\
        ((inverse << 3) | (inverse >> 5) & 7) & 0xFF ^ \\
        ((inverse << 4) | (inverse >> 4) & 15) & 0xFF ^ 0x63


def AES_Sbox():
    sbox = []
    for value in range(256):
        x = [(value >> i) & 1 for i in range(8)]
        y = [0] * 8
        t = [0] * 1000
        g = [0] * 1000

        ################### Here is your code !! ###################
{body}
        ################### Here is your code !! ###################

        sbox.append(sum(bit << i for i, bit in enumerate(y)))
    return sbox


if __name__ == "__main__":
    actual = AES_Sbox()
    expected = [_aes_reference(value) for value in range(256)]
    if actual != expected:
        raise SystemExit("generated circuit does not implement the AES S-box")
    print("PASS: all 256 AES S-box inputs")
'''


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("input", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    _, _, statements = parse_bench(args.input)
    args.output.write_text(render(statements, args.input))


if __name__ == "__main__":
    main()
