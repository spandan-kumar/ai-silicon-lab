#!/usr/bin/env python3
"""Exhaustively verify and map current public AES S-box circuits."""

from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import shutil
import subprocess
import urllib.request
from pathlib import Path

from fetch_nangate45 import EXPECTED_SHA256 as NANGATE45_SHA256


ROOT = Path(__file__).resolve().parents[1]
PINNED_NIST_REVISION = "4e23832e62f490aeffd8770b1285d99056b5f8bf"
NIST_RAW_ROOT = (
    "https://raw.githubusercontent.com/usnistgov/Circuits/"
    f"{PINNED_NIST_REVISION}/data/slp/aes/sbox"
)
DEFAULT_LIBERTY = (
    ROOT / "build" / "technology" / "nangate45" /
    "NangateOpenCellLibrary_typical.lib"
)
CONSTRAINTS = ROOT / "asic" / "nangate45.constr"
CLASSIC_SOURCE = (
    ROOT / "third_party" / "nist-circuits" /
    "aes-sbox-fwd-g113-a32-d27-ad6.slp"
)
TIMING_RE = re.compile(
    r"Area\s*=\s*([0-9.]+).*Delay\s*=\s*([0-9.]+)\s*ps"
)
LOGICAL_LOG_HASH_RE = re.compile(r"Logfile hash:\s*([0-9a-f]+)")


CIRCUITS = {
    "classic-g113-d27": {
        "filename": None,
        "sha256": "a09670fb9b27c18bf474acd52a03262251372aa2f2aa300fffd3cf933e56c01f",
        "gates": 113,
        "ands": 32,
        "gate_depth": 27,
        "and_depth": 6,
    },
    "a29-ad5-g140-d37": {
        "filename": "aes-sbox-fwd-a29-ad5-g140-gd37-xx111-14.ncff.txt",
        "sha256": "5d03ea986defeff5ca68d0c9df6630334aa1e914854633772d5f618112516c62",
        "gates": 140,
        "ands": 29,
        "gate_depth": 37,
        "and_depth": 5,
    },
    "a29-ad5-g141-d32": {
        "filename": "aes-sbox-fwd-a29-ad5-g141-gd32-xx112-14.ncff.txt",
        "sha256": "e55243a3cc49883ddb4f5f315643f56027aab203af49ab0d25880dd154229a12",
        "gates": 141,
        "ands": 29,
        "gate_depth": 32,
        "and_depth": 5,
    },
    "a29-ad5-g161-d24": {
        "filename": "aes-sbox-fwd-a29-ad5-g161-gd24-xx132-1.ncff.txt",
        "sha256": "47e64a9e7ae1fbd51e38bf9d3a0394c74c9635ff4f0ab37dec41749fc09fb2f9",
        "gates": 161,
        "ands": 29,
        "gate_depth": 24,
        "and_depth": 5,
    },
    "a29-ad5-g184-d20": {
        "filename": "aes-sbox-fwd-a29-ad5-g184-gd20-xx155-2.ncff.txt",
        "sha256": "a18a5edc747ff03fae0d0b3a1f241229b7d3493e3037a1d2b32cee64b0c2786b",
        "gates": 184,
        "ands": 29,
        "gate_depth": 20,
        "and_depth": 5,
    },
    "a29-ad6-g138-d38": {
        "filename": "aes-sbox-fwd-a29-ad6-g138-gd38-xx109-14.ncff.txt",
        "sha256": "13e27e7dfd655a3744d8fa349f400a7e6d83764f67c1a169d524a8f94789d565",
        "gates": 138,
        "ands": 29,
        "gate_depth": 38,
        "and_depth": 6,
    },
    "a29-ad6-g139-d33": {
        "filename": "aes-sbox-fwd-a29-ad6-g139-gd33-xx110-14.ncff.txt",
        "sha256": "cb14e276bb2b716111667614d817b53ab2033bc13b3fcf2847fec054904ed097",
        "gates": 139,
        "ands": 29,
        "gate_depth": 33,
        "and_depth": 6,
    },
    "a29-ad6-g154-d27": {
        "filename": "aes-sbox-fwd-a29-ad6-g154-gd27-xx125-1.ncff.txt",
        "sha256": "e1762d084bdd1b510ac4ea02a1053cdc9b0b3f901a8f67026f8c8c66ba28c978",
        "gates": 154,
        "ands": 29,
        "gate_depth": 27,
        "and_depth": 6,
    },
    "a29-ad6-g181-d21": {
        "filename": "aes-sbox-fwd-a29-ad6-g181-gd21-xx152-2.ncff.txt",
        "sha256": "882c6fd055e69d84c4963a93cbf54bf5dd99407d90710e5f69a89b29b52e0703",
        "gates": 181,
        "ands": 29,
        "gate_depth": 21,
        "and_depth": 6,
    },
}


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    return sha256_bytes(path.read_bytes())


def load_sbox() -> tuple[int, ...]:
    spec = importlib.util.spec_from_file_location(
        "aes_gcm_reference", ROOT / "reference" / "aes_gcm.py"
    )
    if spec is None or spec.loader is None:
        raise SystemExit("cannot load independent AES reference")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return tuple(module.SBOX)


def acquire_source(name: str, metadata: dict[str, object], cache: Path) -> Path:
    filename = metadata["filename"]
    if filename is None:
        source = CLASSIC_SOURCE
    else:
        source = cache / str(filename)
        if not source.exists() or sha256_file(source) != metadata["sha256"]:
            shared_source = ROOT / "build" / "sbox-circuit-study" / "sources" / str(filename)
            if shared_source.exists() and sha256_file(shared_source) == metadata["sha256"]:
                data = shared_source.read_bytes()
            else:
                url = f"{NIST_RAW_ROOT}/{filename}"
                with urllib.request.urlopen(url, timeout=30) as response:
                    data = response.read()
            if sha256_bytes(data) != metadata["sha256"]:
                raise SystemExit(f"source hash mismatch for {name}")
            source.write_bytes(data)
    if sha256_file(source) != metadata["sha256"]:
        raise SystemExit(f"pinned source hash mismatch for {name}")
    return source


def parse_slp(source: Path, expected_gates: int) -> list[tuple[str, str, str, str]]:
    operations: list[tuple[str, str, str, str]] = []
    active = False
    for raw_line in source.read_text().splitlines():
        line = raw_line.strip()
        if line == "begin SLP":
            if active:
                raise ValueError(f"nested SLP in {source}")
            active = True
            continue
        if line == "end SLP":
            active = False
            break
        if not active or not line or line.startswith(("#", "%")):
            continue
        parts = line.split()
        if len(parts) != 4 or parts[0] not in {"AND", "XOR", "XNOR"}:
            raise ValueError(f"unsupported SLP line in {source}: {line}")
        operations.append((parts[0], parts[1], parts[2], parts[3]))
    if active or len(operations) != expected_gates:
        raise ValueError(
            f"expected {expected_gates} gates in {source}, found {len(operations)}"
        )
    return operations


def evaluate(operations: list[tuple[str, str, str, str]], value: int) -> int:
    signals = {f"U{index}": (value >> (7 - index)) & 1 for index in range(8)}
    for operation, output, left, right in operations:
        if operation == "AND":
            result = signals[left] & signals[right]
        else:
            result = signals[left] ^ signals[right]
            if operation == "XNOR":
                result ^= 1
        signals[output] = result
    return sum(signals[f"S{index}"] << (7 - index) for index in range(8))


def verilog_signal(token: str) -> str:
    if token.startswith("U"):
        return f"value[{7 - int(token[1:])}]"
    if token.startswith("S"):
        return f"result[{7 - int(token[1:])}]"
    return token


def write_verilog(
    operations: list[tuple[str, str, str, str]], output: Path
) -> None:
    internals = [item[1] for item in operations if not item[1].startswith("S")]
    lines = [
        "module sbox_probe(input wire [7:0] value, output wire [7:0] result);",
        *(f"  wire {signal};" for signal in internals),
    ]
    for operation, destination, left, right in operations:
        if operation == "AND":
            expression = f"{verilog_signal(left)} & {verilog_signal(right)}"
        else:
            expression = f"{verilog_signal(left)} ^ {verilog_signal(right)}"
            if operation == "XNOR":
                expression = f"~({expression})"
        lines.append(f"  assign {verilog_signal(destination)} = {expression};")
    lines.extend(["endmodule", ""])
    output.write_text("\n".join(lines))


def relative(path: Path) -> Path:
    try:
        return path.resolve().relative_to(ROOT)
    except ValueError as error:
        raise SystemExit(f"study path must be under {ROOT}: {path}") from error


def map_circuit(name: str, source: Path, liberty: Path, output: Path) -> dict[str, object]:
    stat_path = output / f"{name}-stat.json"
    netlist_path = output / f"{name}-netlist.v"
    log_path = output / f"{name}.log"
    script = (
        f"read_verilog {relative(source)}; hierarchy -top sbox_probe; "
        "synth -top sbox_probe -flatten; "
        f"abc -liberty {relative(liberty)} -constr {relative(CONSTRAINTS)}; clean; "
        f"tee -o {relative(stat_path)} stat -json -liberty {relative(liberty)}; "
        f"write_verilog -noattr {relative(netlist_path)}"
    )
    subprocess.run(
        ["yosys", "-q", "-l", str(log_path), "-p", script], check=True, cwd=ROOT
    )
    statistics = json.loads(stat_path.read_text())["design"]
    log_text = log_path.read_text()
    timing = TIMING_RE.findall(log_text)
    if len(timing) != 1:
        raise SystemExit(f"expected one ABC timing result for {name}, found {len(timing)}")
    logical_log_hashes = LOGICAL_LOG_HASH_RE.findall(log_text)
    if len(logical_log_hashes) != 1:
        raise SystemExit(
            f"expected one Yosys logical log hash for {name}, found {len(logical_log_hashes)}"
        )
    combinational_area, delay_ps = map(float, timing[0])
    internal_types = sorted(
        cell for cell in statistics["num_cells_by_type"] if cell.startswith("$")
    )
    if internal_types:
        raise SystemExit(f"unmapped internal cells for {name}: {internal_types}")
    return {
        "mapped_cell_count": statistics["num_cells"],
        "mapped_cell_types": statistics["num_cells_by_type"],
        "total_cell_area_um2": statistics["area"],
        "abc_combinational_area_um2": combinational_area,
        "critical_combinational_delay_ps": delay_ps,
        "area_delay_um2_ps": round(float(statistics["area"]) * delay_ps, 6),
        "stat_sha256": sha256_file(stat_path),
        "netlist_sha256": sha256_file(netlist_path),
        # Yosys excludes volatile runtime and peak-memory fields from this hash.
        "yosys_logical_log_hash": logical_log_hashes[0],
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build" / "sbox-circuit-study")
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--liberty", type=Path, default=DEFAULT_LIBERTY)
    parser.add_argument("--circuit", action="append", choices=CIRCUITS)
    args = parser.parse_args()
    if shutil.which("yosys") is None:
        raise SystemExit("yosys is required")
    liberty = args.liberty.resolve()
    if not liberty.exists() or sha256_file(liberty) != NANGATE45_SHA256:
        raise SystemExit("pinned Nangate45 Liberty file missing or corrupt")
    output = args.output_dir.resolve()
    sources = output / "sources"
    generated = output / "generated"
    sources.mkdir(parents=True, exist_ok=True)
    generated.mkdir(parents=True, exist_ok=True)
    selected = set(args.circuit or CIRCUITS)
    expected_sbox = load_sbox()
    summary: dict[str, object] = {
        "schema_version": 1,
        "study": "public-aes-sbox-circuits-nangate45-v1",
        "nist_revision": PINNED_NIST_REVISION,
        "tool": subprocess.run(
            ["yosys", "-V"], check=True, capture_output=True, text=True
        ).stdout.strip(),
        "library": {
            "name": "NangateOpenCellLibrary",
            "corner": "typical",
            "sha256": NANGATE45_SHA256,
        },
        "constraints_sha256": sha256_file(CONSTRAINTS),
        "circuits": {},
    }
    for name, metadata in CIRCUITS.items():
        if name not in selected:
            continue
        source = acquire_source(name, metadata, sources)
        operations = parse_slp(source, int(metadata["gates"]))
        mismatches = [
            value for value in range(256)
            if evaluate(operations, value) != expected_sbox[value]
        ]
        if mismatches:
            raise SystemExit(f"functional mismatch for {name}: {mismatches[:8]}")
        verilog = generated / f"{name}.v"
        write_verilog(operations, verilog)
        result = {
            **metadata,
            "source": str(relative(source)),
            "source_sha256": sha256_file(source),
            "exhaustive_functional_vectors": 256,
            "functional_pass": True,
            **map_circuit(name, verilog, liberty, output),
        }
        summary["circuits"][name] = result
        print(
            f"sbox-study: PASS circuit={name} gates={metadata['gates']} "
            f"area_um2={result['total_cell_area_um2']:.3f} "
            f"delay_ps={result['critical_combinational_delay_ps']:.2f}"
        )
    summary_text = json.dumps(summary, indent=2, sort_keys=True) + "\n"
    (output / "summary.json").write_text(summary_text)
    if args.summary_output is not None:
        summary_output = args.summary_output.resolve()
        relative(summary_output)
        summary_output.parent.mkdir(parents=True, exist_ok=True)
        summary_output.write_text(summary_text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
