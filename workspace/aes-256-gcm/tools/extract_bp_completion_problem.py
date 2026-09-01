#!/usr/bin/env python3
"""Extract the final affine-completion problem from an Extended-BP log."""

from __future__ import annotations

import argparse
import ast
import hashlib
import re
from pathlib import Path


ADD_RE = re.compile(r"^\d+th Add .*?:\s*[^,]+,\s*(\d+)(?:,.*)?$")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("log", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()

    data = args.log.read_bytes()
    lines = data.decode().splitlines()
    y_line = next((line for line in lines if line.startswith("Y : ")), None)
    if y_line is None:
        raise ValueError("log has no Y matrix")
    targets_and_operands = ast.literal_eval(y_line.removeprefix("Y : "))
    if len(targets_and_operands) != 66:
        raise ValueError(f"expected 58 AND operands and 8 outputs, got {len(targets_and_operands)}")

    sources = [1 << index for index in range(8)]
    for line in lines:
        if match := ADD_RE.fullmatch(line):
            value = int(match.group(1))
            if value in sources:
                raise ValueError(f"duplicate basis value {value}")
            sources.append(value)

    missing_ands = [index for index in range(29) if 1 << (8 + index) not in sources]
    if missing_ands:
        raise ValueError(f"checkpoint is too early; missing AND outputs {missing_ands}")
    outputs = targets_and_operands[-8:]
    affine_gates = len(sources) - 8 - 29

    rendered = [
        "# Extended-BP affine completion problem",
        f"# source_log={args.log.resolve()}",
        f"# source_log_sha256={hashlib.sha256(data).hexdigest()}",
        f"# existing_affine_gates={affine_gates}",
        "DIM 37",
    ]
    rendered.extend(f"SOURCE {value:x}" for value in sources)
    rendered.extend(f"TARGET {value:x}" for value in outputs)
    args.output.write_text("\n".join(rendered) + "\n")
    print(
        f"sources={len(sources)} existing_affine_gates={affine_gates} "
        f"targets={len(outputs)} output={args.output}"
    )


if __name__ == "__main__":
    main()
