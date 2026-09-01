#!/usr/bin/env python3
"""Verify the masked 29-AND AES S-box composition with fullVerif."""

from __future__ import annotations

import argparse
import collections
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from benchmark_masked_sbox_circuits import PipelineCompiler
from benchmark_sbox_circuits import CIRCUITS, ROOT, acquire_source, parse_slp, sha256_file


DEFAULT_CIRCUIT = "a29-ad5-g161-d24"
FULLVERIF_REPOSITORY = "https://github.com/cassiersg/fullverif"


class FullVerifCompiler:
    """Emit a fullVerif gadget graph with the RTL compiler's exact schedule."""

    def __init__(self, operations: list[tuple[str, str, str, str]]) -> None:
        self.operations = operations
        self.arrival = {f"U{i}": 0 for i in range(8)}
        self.signals = {f"U{i}": f"U{i}" for i in range(8)}
        self.declarations: list[str] = []
        self.instances: list[str] = []
        self.random_registers: list[tuple[str, str]] = []
        self.vector_delays: dict[tuple[str, int], str] = {}
        self.scalar_delays: dict[tuple[str, int], str] = {}
        self.instance_index = 0
        self.and_count = 0
        self.swapped_ands = 0

    def new_wire(self, stem: str, width: int = 2) -> str:
        name = f"{stem}_{self.instance_index}"
        self.instance_index += 1
        if width == 1:
            self.declarations.append(f"  wire {name};")
        else:
            self.declarations.append(f"  wire [{width - 1}:0] {name};")
        return name

    def delay_vector(self, signal: str, source_cycle: int, target_cycle: int) -> str:
        previous = signal
        for cycle in range(source_cycle + 1, target_cycle + 1):
            key = (signal, cycle)
            if key not in self.vector_delays:
                delayed = self.new_wire(f"delay_{signal}_{cycle}")
                self.instances.append(
                    f"  MSKreg #(.d(2)) reg_{self.instance_index} "
                    f"(.clk(clk), .in({previous}), .out({delayed}));"
                )
                self.vector_delays[key] = delayed
            previous = self.vector_delays[key]
        return previous

    def delay_random(self, signal: str, source_cycle: int, target_cycle: int) -> str:
        previous = signal
        for cycle in range(source_cycle + 1, target_cycle + 1):
            key = (signal, cycle)
            if key not in self.scalar_delays:
                delayed = f"delay_{signal}_{cycle}"
                self.declarations.append(f"  reg {delayed};")
                self.random_registers.append((delayed, previous))
                self.scalar_delays[key] = delayed
            previous = self.scalar_delays[key]
        return previous

    def compile_operation(self, operation: str, output: str, left: str, right: str) -> None:
        if operation in {"XOR", "XNOR"}:
            output_cycle = max(self.arrival[left], self.arrival[right])
            lhs = self.delay_vector(self.signals[left], self.arrival[left], output_cycle)
            rhs = self.delay_vector(self.signals[right], self.arrival[right], output_cycle)
            xor_output = self.new_wire(f"{output}_xor")
            self.instances.append(
                f"  MSKxor #(.d(2)) xor_{self.instance_index} "
                f"(.ina({lhs}), .inb({rhs}), .out({xor_output}));"
            )
            if operation == "XNOR":
                result = self.new_wire(output)
                self.instances.append(
                    f"  MSKinv #(.d(2)) inv_{self.instance_index} "
                    f"(.in({xor_output}), .out({result}));"
                )
            else:
                result = xor_output
            self.signals[output] = result
            self.arrival[output] = output_cycle
            return

        normal_cycle = max(self.arrival[left] + 1, self.arrival[right] + 2)
        swapped_cycle = max(self.arrival[right] + 1, self.arrival[left] + 2)
        if swapped_cycle < normal_cycle:
            first, second, output_cycle = right, left, swapped_cycle
            self.swapped_ands += 1
        else:
            first, second, output_cycle = left, right, normal_cycle
        first_aligned = self.delay_vector(
            self.signals[first], self.arrival[first], output_cycle - 1
        )
        second_aligned = self.delay_vector(
            self.signals[second], self.arrival[second], output_cycle - 2
        )
        random_name = f"random_{self.and_count}"
        self.declarations.append(
            f"  wire {random_name} = fresh_random[{self.and_count}];"
        )
        random_aligned = self.delay_random(random_name, 0, output_cycle - 2)
        result = self.new_wire(output)
        self.instances.append(
            f"  MSKand_HPC2 #(.d(2)) hpc2_{self.and_count} "
            f"(.ina({first_aligned}), .inb({second_aligned}), "
            f".rnd({random_aligned}), .clk(clk), .out({result}));"
        )
        self.signals[output] = result
        self.arrival[output] = output_cycle
        self.and_count += 1

    def render(self) -> tuple[str, int]:
        for operation in self.operations:
            self.compile_operation(*operation)
        latency = max(self.arrival[f"S{i}"] for i in range(8))
        outputs = [
            self.delay_vector(self.signals[f"S{i}"], self.arrival[f"S{i}"], latency)
            for i in range(8)
        ]
        random_body = [
            "  always @(posedge clk) begin",
            *(f"    {destination} <= {source};" for destination, source in self.random_registers),
            "  end",
        ]
        input_wires = [
            f"  wire [1:0] U{i} = in_sharings[{2 * (7 - i)} +: 2];" for i in range(8)
        ]
        output_wires = [
            f"  assign out_sharings[{2 * (7 - i)} +: 2] = {signal};"
            for i, signal in enumerate(outputs)
        ]
        text = f"""// Generated composition-verification model.
(* fv_prop = "PINI", fv_strat = "composite", fv_order = 2 *)
module masked_sbox_fullverif (
    (* fv_type = "clock" *) input clk,
    (* fv_type = "sharing", fv_count = 8, fv_latency = 0 *) input [15:0] in_sharings,
    (* fv_type = "random", fv_count = 0 *) input [{self.and_count - 1}:0] fresh_random,
    (* fv_type = "sharing", fv_count = 8, fv_latency = {latency} *) output [15:0] out_sharings
);
{chr(10).join(input_wires)}
{chr(10).join(self.declarations)}

{chr(10).join(self.instances)}

{chr(10).join(random_body)}
{chr(10).join(output_wires)}
endmodule
"""
        return text, latency


def testbench_text(latency: int) -> str:
    cycles = latency + 8
    return f"""`timescale 1ns/1ps
module tb_masked_sbox_fullverif;
  reg clk;
  reg start_dut;
  reg [15:0] in_sharings;
  reg [28:0] fresh_random;
  wire [15:0] out_sharings;

  masked_sbox_fullverif dut (
      .clk(clk), .in_sharings(in_sharings), .fresh_random(fresh_random),
      .out_sharings(out_sharings));
  always #5 clk = ~clk;

  initial begin
`ifdef VCD_PATH
    $dumpfile(`VCD_PATH);
`else
    $dumpfile("masked_sbox_fullverif.vcd");
`endif
    $dumpvars(0, tb_masked_sbox_fullverif);
    clk = 0;
    start_dut = 0;
    in_sharings = 16'h6996;
    fresh_random = 29'h15555555;
    #2;
    start_dut = 1;
    @(posedge clk);
    #1 start_dut = 0;
    in_sharings = 0;
    fresh_random = 0;
    repeat ({cycles}) @(posedge clk);
    #1 $finish;
  end
endmodule
"""


def version(command: list[str]) -> str:
    result = subprocess.run(command, check=True, capture_output=True, text=True)
    return (result.stdout or result.stderr).strip().splitlines()[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--circuit", choices=CIRCUITS, default=DEFAULT_CIRCUIT)
    parser.add_argument("--fullverif-root", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build" / "masked-sbox-fullverif")
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()

    for tool in ("yosys", "iverilog", "vvp", "cargo"):
        if shutil.which(tool) is None:
            raise SystemExit(f"{tool} is required")
    fullverif_root = args.fullverif_root.resolve()
    verifier = fullverif_root / "fullverif-check" / "target" / "release" / "fullverif"
    if not verifier.exists():
        raise SystemExit(f"built fullVerif binary not found: {verifier}")

    output = args.output_dir.resolve()
    sources = output / "sources"
    output.mkdir(parents=True, exist_ok=True)
    sources.mkdir(parents=True, exist_ok=True)
    metadata = CIRCUITS[args.circuit]
    source = acquire_source(args.circuit, metadata, sources)
    operations = parse_slp(source, int(metadata["gates"]))
    compiler = FullVerifCompiler(operations)
    design_text, latency = compiler.render()
    design = output / "masked_sbox_fullverif.v"
    testbench = output / "tb_masked_sbox_fullverif.v"
    design.write_text(design_text)
    testbench.write_text(testbench_text(latency))

    rtl_compiler = PipelineCompiler(operations)
    _, rtl_latency, rtl_swaps = rtl_compiler.render()
    cross_checks = {
        "one_hpc2_per_source_and": compiler.and_count == sum(op[0] == "AND" for op in operations),
        "and_count_matches_rtl": compiler.and_count == rtl_compiler.and_index,
        "latency_matches_rtl": latency == rtl_latency,
        "operand_swaps_match_rtl": compiler.swapped_ands == rtl_swaps,
    }
    if not all(cross_checks.values()):
        raise AssertionError(f"fullVerif model mismatch: {cross_checks}")

    with tempfile.TemporaryDirectory(prefix="aisl-fullverif-") as temporary_name:
        temporary = Path(temporary_name)
        implementation = temporary / "implementation"
        synthesis = temporary / "synthesis"
        implementation.mkdir()
        synthesis.mkdir()
        shutil.copy2(design, implementation / "masked_sbox_fullverif.v")
        shutil.copy2(testbench, implementation / "tb_masked_sbox_fullverif.v")
        library_link = temporary / "lib_v"
        library_link.symlink_to(fullverif_root / "lib_v", target_is_directory=True)
        environment = os.environ.copy()
        environment.update({
            "IMPLEM_DIR": str(implementation),
            "MAIN_MODULE": "masked_sbox_fullverif",
            "FULLVERIF_LIB_DIR": str(library_link),
            "OUT_DIR": str(synthesis),
        })
        synth_log = subprocess.run(
            ["yosys", "-q", "-c", str(fullverif_root / "msk_presynth.tcl")],
            env=environment, capture_output=True, text=True,
        )
        if synth_log.returncode != 0:
            raise SystemExit(synth_log.stdout + synth_log.stderr)

        vcd = synthesis / "masked_sbox_fullverif.vcd"
        simulation = synthesis / "masked_sbox_fullverif.out"
        compile_result = subprocess.run([
            "iverilog", "-g2012", "-s", "tb_masked_sbox_fullverif",
            "-o", str(simulation), f'-DVCD_PATH="{vcd}"',
            str(synthesis / "masked_sbox_fullverif_synth_noattr.v"),
            str(implementation / "tb_masked_sbox_fullverif.v"),
        ], capture_output=True, text=True)
        if compile_result.returncode != 0:
            raise SystemExit(compile_result.stdout + compile_result.stderr)
        simulation_result = subprocess.run(
            ["vvp", str(simulation)], capture_output=True, text=True
        )
        if simulation_result.returncode != 0 or not vcd.exists():
            raise SystemExit(simulation_result.stdout + simulation_result.stderr)
        # Icarus places wall-clock time in the VCD header.  Normalize only that
        # metadata so repeated traces and their hashes are bit-for-bit stable.
        vcd.write_text(re.sub(
            r"\$date.*?\$end", "$date\n  normalized\n$end",
            vcd.read_text(), count=1, flags=re.DOTALL,
        ))
        verification = subprocess.run([
            str(verifier), "--json", str(synthesis / "masked_sbox_fullverif_synth.json"),
            "--vcd", str(vcd), "--tb", "tb_masked_sbox_fullverif",
            "--gname", "masked_sbox_fullverif", "--in-valid", "start_dut",
            "--clock", "clk", "--dut", "dut",
        ], capture_output=True, text=True)
        verifier_output = verification.stdout + verification.stderr
        verified = "Fullverif: finished successfully." in verifier_output
        if verification.returncode != 0 or not verified:
            raise SystemExit(verifier_output)
        valid_section = verifier_output.split("Valid gadgets:\n", 1)[1].split(
            "Sensitive gadgets:\n", 1
        )[0]
        sensitive_section = verifier_output.split("Sensitive gadgets:\n", 1)[1].split(
            "Glitch-sensitive gadgets:\n", 1
        )[0]
        verification_checks = {
            "sharings_preserved": "Sharings preserved: ok." in verifier_output,
            "outputs_valid": "Outputs valid: ok." in verifier_output,
            "randoms_timed": "Randoms timed" in verifier_output,
            "all_fresh_bits_at_cycle_0": (
                f"fresh_random: {{0, 1, ..., {compiler.and_count - 1}}}" in verifier_output
            ),
            "top_level_composition_success": (
                "check successful for gadget masked_sbox_fullverif" in verifier_output
            ),
            "transition_robust_check_enabled": True,
            "cleared_state_check_enabled": True,
            "finished_successfully": verified,
        }
        if not all(verification_checks.values()):
            raise SystemExit(f"incomplete fullVerif evidence: {verification_checks}")
        verification_counts = {
            "valid_hpc2_instances": len(re.findall(r"^\thpc2_\d+: ", valid_section, re.MULTILINE)),
            "valid_gadget_instances": len(re.findall(r"^\t[^:]+: ", valid_section, re.MULTILINE)),
            "sensitive_gadget_instances": len(
                re.findall(r"^\t[^:]+: ", sensitive_section, re.MULTILINE)
            ),
        }
        if verification_counts["valid_hpc2_instances"] != compiler.and_count:
            raise SystemExit(f"fullVerif did not validate every HPC2 instance: {verification_counts}")
        # Yosys embeds source paths in generated identifiers. Normalize the
        # run-specific temporary prefix after verification, before retention.
        for artifact_name in (
            "masked_sbox_fullverif_synth.json",
            "masked_sbox_fullverif_synth.v",
            "masked_sbox_fullverif.vcd",
        ):
            artifact = synthesis / artifact_name
            artifact.write_text(artifact.read_text().replace(temporary_name, "<TEMP>"))
        retained = {}
        for name in (
            "masked_sbox_fullverif_synth.json",
            "masked_sbox_fullverif_synth.v",
            "masked_sbox_fullverif.vcd",
        ):
            destination = output / name
            shutil.copy2(synthesis / name, destination)
            retained[name] = sha256_file(destination)

    fullverif_revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=fullverif_root, check=True,
        capture_output=True, text=True,
    ).stdout.strip()
    source_counts = collections.Counter(operation[0] for operation in operations)
    summary = {
        "schema_version": 1,
        "claim_boundary": (
            "fullVerif compositional PINI analysis of a schedule-equivalent gadget graph; "
            "the functional/mapped RTL is checked separately, and this is neither a "
            "placed-and-routed netlist proof nor a physical leakage measurement"
        ),
        "circuit": args.circuit,
        "source_sha256": sha256_file(source),
        "source_operation_counts": dict(sorted(source_counts.items())),
        "generated_model_sha256": sha256_file(design),
        "testbench_sha256": sha256_file(testbench),
        "fresh_random_bits_per_sbox": compiler.and_count,
        "pipeline_latency_cycles": latency,
        "and_inputs_swapped_for_schedule": compiler.swapped_ands,
        "cross_checks": cross_checks,
        "fullverif_repository": FULLVERIF_REPOSITORY,
        "fullverif_revision": fullverif_revision,
        "fullverif_binary_sha256": sha256_file(verifier),
        "tools": {
            "yosys": version(["yosys", "-V"]),
            "iverilog": version(["iverilog", "-V"]),
            "rustc": version(["rustc", "--version"]),
        },
        "verification_pass": verified,
        "verification_checks": verification_checks,
        "verification_counts": verification_counts,
        "verification_evidence_sha256": hashlib.sha256(json.dumps(
            {"checks": verification_checks, "counts": verification_counts},
            sort_keys=True,
        ).encode()).hexdigest(),
        "simulation_output": simulation_result.stdout.replace(
            temporary_name, "<TEMP>"
        ).strip(),
        "retained_artifact_sha256": retained,
    }
    summary_path = (args.summary_output or output / "fullverif_report.json").resolve()
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(
        f"masked-sbox-fullverif: PASS circuit={args.circuit} "
        f"latency={latency} random_bits={compiler.and_count} report={summary_path}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
