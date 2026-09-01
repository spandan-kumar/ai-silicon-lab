#!/usr/bin/env python3
"""Generate and verify an HPC2-masked AES S-box with SILVER.

This script is deliberately separate from the functional/synthesis benchmark:
SILVER is a research verifier with its own build dependencies and license.  The
generated instruction list is an independently constructed representation of
the same scheduling rules used by benchmark_masked_sbox_circuits.py.
"""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path

from benchmark_masked_sbox_circuits import PipelineCompiler
from benchmark_sbox_circuits import CIRCUITS, ROOT, acquire_source, parse_slp, sha256_file


DEFAULT_CIRCUIT = "a29-ad5-g161-d24"
ANSI_RE = re.compile(r"\x1b\[[0-9;]*m")
RESULT_RE = re.compile(
    r"^.*?(probing\.standard|probing\.robust|NI\.standard|NI\.robust|"
    r"SNI\.standard|SNI\.robust|PINI\.standard|PINI\.robust|uniformity)"
    r".*-- (PASS|FAIL)\.",
    re.MULTILINE,
)


class SilverCircuit:
    """Emit SILVER's instruction language while reproducing the RTL schedule."""

    def __init__(self, operations: list[tuple[str, str, str, str]]) -> None:
        self.operations = operations
        self.lines: list[str] = []
        self.next_id = 0
        self.arrival = {f"U{i}": 0 for i in range(8)}
        self.signals: dict[str, tuple[int, int]] = {}
        self.vector_delays: dict[tuple[str, int], tuple[int, int]] = {}
        self.scalar_delays: dict[tuple[int, int], int] = {}
        self.and_count = 0
        self.swapped_ands = 0

    def add(self, operation: str, *operands: object, comment: str = "") -> int:
        node = self.next_id
        rendered = " ".join([operation, *(str(value) for value in operands)])
        if comment:
            rendered += f" # {comment}"
        self.lines.append(rendered)
        self.next_id += 1
        return node

    def delay_vector(self, name: str, source_cycle: int, target_cycle: int) -> tuple[int, int]:
        previous = self.signals[name]
        for cycle in range(source_cycle + 1, target_cycle + 1):
            key = (name, cycle)
            if key not in self.vector_delays:
                self.vector_delays[key] = (
                    self.add("reg", previous[0], comment=f"delay {name}[0] to cycle {cycle}"),
                    self.add("reg", previous[1], comment=f"delay {name}[1] to cycle {cycle}"),
                )
            previous = self.vector_delays[key]
        return previous

    def delay_scalar(self, node: int, source_cycle: int, target_cycle: int) -> int:
        previous = node
        for cycle in range(source_cycle + 1, target_cycle + 1):
            key = (node, cycle)
            if key not in self.scalar_delays:
                self.scalar_delays[key] = self.add(
                    "reg", previous, comment=f"delay random node {node} to cycle {cycle}"
                )
            previous = self.scalar_delays[key]
        return previous

    def compile_operation(self, operation: str, output: str, left: str, right: str) -> None:
        if operation in {"XOR", "XNOR"}:
            output_cycle = max(self.arrival[left], self.arrival[right])
            lhs = self.delay_vector(left, self.arrival[left], output_cycle)
            rhs = self.delay_vector(right, self.arrival[right], output_cycle)
            self.signals[output] = (
                self.add(operation.lower(), lhs[0], rhs[0], comment=f"{output}[0]"),
                self.add("xor", lhs[1], rhs[1], comment=f"{output}[1]"),
            )
            self.arrival[output] = output_cycle
            return

        normal_cycle = max(self.arrival[left] + 1, self.arrival[right] + 2)
        swapped_cycle = max(self.arrival[right] + 1, self.arrival[left] + 2)
        if swapped_cycle < normal_cycle:
            first, second, output_cycle = right, left, swapped_cycle
            self.swapped_ands += 1
        else:
            first, second, output_cycle = left, right, normal_cycle
        a = self.delay_vector(first, self.arrival[first], output_cycle - 1)
        b = self.delay_vector(second, self.arrival[second], output_cycle - 2)
        random_input = self.add("ref", self.next_id, comment=f"fresh random for {output}")
        random_aligned = self.delay_scalar(random_input, 0, output_cycle - 2)

        b_stage1 = (
            self.add("reg", b[0], comment=f"{output} b_stage1[0]"),
            self.add("reg", b[1], comment=f"{output} b_stage1[1]"),
        )
        cross_stage1 = (
            self.add("reg", self.add("xor", b[1], random_aligned), comment=f"{output} cross[0]"),
            self.add("reg", self.add("xor", b[0], random_aligned), comment=f"{output} cross[1]"),
        )
        r_stage1 = self.add("reg", random_aligned, comment=f"{output} r_stage1")
        outputs: list[int] = []
        for share in range(2):
            same = self.add("reg", self.add("and", a[share], b_stage1[share]))
            complement = self.add(
                "reg", self.add("and", self.add("not", a[share]), r_stage1)
            )
            cross = self.add("reg", self.add("and", a[share], cross_stage1[share]))
            outputs.append(self.add("xor", self.add("xor", same, complement), cross))
        self.signals[output] = (outputs[0], outputs[1])
        self.arrival[output] = output_cycle
        self.and_count += 1

    def render(self) -> tuple[str, int]:
        for index in range(8):
            # U0 is the AES most-significant bit, matching the RTL compiler.
            self.signals[f"U{index}"] = (
                self.add("in", self.next_id, f"{7 - index}_0", comment=f"U{index}[0]"),
                self.add("in", self.next_id, f"{7 - index}_1", comment=f"U{index}[1]"),
            )
        for operation in self.operations:
            self.compile_operation(*operation)
        latency = max(self.arrival[f"S{i}"] for i in range(8))
        for index in range(8):
            output = self.delay_vector(f"S{index}", self.arrival[f"S{index}"], latency)
            self.add("out", output[0], f"{7 - index}_0", comment=f"S{index}[0]")
            self.add("out", output[1], f"{7 - index}_1", comment=f"S{index}[1]")
        return "\n".join(self.lines) + "\n", latency


def stable_probe_certificate() -> dict[str, object]:
    """Exhaustively check every named stable single-bit probe of the RTL gadget."""
    distributions: dict[str, dict[str, list[int]]] = collections.defaultdict(dict)
    for secret_a in range(2):
        for secret_b in range(2):
            counts: dict[str, list[int]] = collections.defaultdict(lambda: [0, 0])
            for mask_a in range(2):
                for mask_b in range(2):
                    for random_bit in range(2):
                        a = (mask_a, mask_a ^ secret_a)
                        b = (mask_b, mask_b ^ secret_b)
                        cross = (b[1] ^ random_bit, b[0] ^ random_bit)
                        same = (a[0] & b[0], a[1] & b[1])
                        complement = ((1 ^ a[0]) & random_bit, (1 ^ a[1]) & random_bit)
                        cross_product = (a[0] & cross[0], a[1] & cross[1])
                        c = (
                            same[0] ^ complement[0] ^ cross_product[0],
                            same[1] ^ complement[1] ^ cross_product[1],
                        )
                        probes = {
                            "a0": a[0], "a1": a[1], "b0": b[0], "b1": b[1],
                            "r": random_bit, "cross0": cross[0], "cross1": cross[1],
                            "same0": same[0], "same1": same[1],
                            "complement0": complement[0], "complement1": complement[1],
                            "cross_product0": cross_product[0],
                            "cross_product1": cross_product[1], "c0": c[0], "c1": c[1],
                        }
                        if (c[0] ^ c[1]) != (secret_a & secret_b):
                            raise AssertionError("HPC2 recombination failed")
                        for name, value in probes.items():
                            counts[name][value] += 1
            secret = f"a={secret_a},b={secret_b}"
            for name, histogram in counts.items():
                distributions[name][secret] = histogram
    failures = {
        name: values
        for name, values in distributions.items()
        if len({tuple(histogram) for histogram in values.values()}) != 1
    }
    return {
        "model": "stable, first-order, one execution, one named scalar probe",
        "random_assignments_per_secret": 8,
        "probe_count": len(distributions),
        "pass": not failures,
        "failures": failures,
        "distributions": distributions,
    }


def run_silver(verifier: Path, silver_root: Path, instruction_file: Path) -> dict[str, object]:
    environment = os.environ.copy()
    native_lib = silver_root / "deps" / "sylvan-install" / "lib"
    for variable in ("DYLD_LIBRARY_PATH", "LD_LIBRARY_PATH"):
        paths = [str(native_lib), str(silver_root / "lib")]
        if environment.get(variable):
            paths.append(environment[variable])
        environment[variable] = os.pathsep.join(paths)
    command = [
        str(verifier), "--cores=1", "--memory=1073741824",
        f"--insfile={instruction_file}", "--verbose=1",
    ]
    result = subprocess.run(
        command, cwd=silver_root, env=environment, capture_output=True, text=True
    )
    output = ANSI_RE.sub("", result.stdout + result.stderr)
    if result.returncode != 0:
        raise SystemExit(output)
    parsed = dict(RESULT_RE.findall(output))
    expected = {
        "probing.standard", "probing.robust", "NI.standard", "NI.robust",
        "SNI.standard", "SNI.robust", "PINI.standard", "PINI.robust", "uniformity",
    }
    if set(parsed) != expected:
        raise SystemExit(f"Could not parse complete SILVER result:\n{output}")
    return {
        "results": parsed,
        "required_security_pass": all(
            parsed[name] == "PASS"
            for name in ("probing.robust", "NI.robust", "PINI.robust", "uniformity")
        ),
        "stdout_sha256": hashlib.sha256(output.encode()).hexdigest(),
        "stdout": output,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--circuit", choices=CIRCUITS, default=DEFAULT_CIRCUIT)
    parser.add_argument("--silver-root", type=Path, required=True)
    parser.add_argument("--silver-verifier", type=Path)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build" / "masked-sbox-security")
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()

    silver_root = args.silver_root.resolve()
    verifier = (args.silver_verifier or silver_root / "bin" / "native" / "verify").resolve()
    if not verifier.exists():
        raise SystemExit(f"SILVER verifier not found: {verifier}")
    output = args.output_dir.resolve()
    sources = output / "sources"
    output.mkdir(parents=True, exist_ok=True)
    sources.mkdir(parents=True, exist_ok=True)

    metadata = CIRCUITS[args.circuit]
    source = acquire_source(args.circuit, metadata, sources)
    operations = parse_slp(source, int(metadata["gates"]))
    compiler = SilverCircuit(operations)
    instruction_text, latency = compiler.render()
    instruction_file = output / f"{args.circuit}.nl"
    instruction_file.write_text(instruction_text)

    # Cross-check scheduling metadata against the independent RTL generator.
    rtl_compiler = PipelineCompiler(operations)
    _, rtl_latency, rtl_swaps = rtl_compiler.render()
    if (compiler.and_count, latency, compiler.swapped_ands) != (
        rtl_compiler.and_index, rtl_latency, rtl_swaps
    ):
        raise AssertionError("SILVER and RTL compilers disagree on schedule metadata")
    source_counts = collections.Counter(operation[0] for operation in operations)
    instruction_counts = collections.Counter(
        line.split(maxsplit=1)[0] for line in instruction_text.splitlines()
    )
    composition_checks = {
        "source_operations_are_xor_xnor_and_only": set(source_counts) <= {"XOR", "XNOR", "AND"},
        "one_hpc2_instance_per_source_and": source_counts["AND"] == compiler.and_count,
        "one_unique_fresh_ref_per_hpc2_instance": instruction_counts["ref"] == compiler.and_count,
        "six_boolean_and_nodes_per_hpc2_instance": instruction_counts["and"] == 6 * compiler.and_count,
        "silvers_and_count_matches_rtl_compiler": compiler.and_count == rtl_compiler.and_index,
        "silvers_latency_matches_rtl_compiler": latency == rtl_latency,
        "silvers_operand_swaps_match_rtl_compiler": compiler.swapped_ands == rtl_swaps,
    }
    if not all(composition_checks.values()):
        raise AssertionError(f"HPC2 composition precondition failed: {composition_checks}")

    silver_revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=silver_root, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    reference = run_silver(verifier, silver_root, silver_root / "test" / "hpc" / "hpc2_1.nl")
    candidate = run_silver(verifier, silver_root, instruction_file)
    summary = {
        "schema_version": 1,
        "claim_boundary": (
            "formal verification of the generated Boolean/register instruction graph in "
            "SILVER's first-order standard and robust probing models; this is not a physical "
            "side-channel measurement or a placed-and-routed netlist verification"
        ),
        "circuit": args.circuit,
        "source_sha256": sha256_file(source),
        "instruction_sha256": sha256_file(instruction_file),
        "instruction_nodes": compiler.next_id,
        "fresh_random_bits_per_sbox": compiler.and_count,
        "pipeline_latency_cycles": latency,
        "and_inputs_swapped_for_schedule": compiler.swapped_ands,
        "source_operation_counts": dict(sorted(source_counts.items())),
        "silver_instruction_counts": dict(sorted(instruction_counts.items())),
        "composition_checks": composition_checks,
        "silver_revision": silver_revision,
        "silver_verifier_sha256": sha256_file(verifier),
        "stable_probe_certificate": stable_probe_certificate(),
        "silver_reference_hpc2": reference,
        "silver_candidate": candidate,
    }
    summary_path = (args.summary_output or output / "security_report.json").resolve()
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(
        f"masked-sbox-security: {'PASS' if candidate['required_security_pass'] else 'FAIL'} "
        f"circuit={args.circuit} nodes={compiler.next_id} report={summary_path}"
    )
    return 0 if candidate["required_security_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
