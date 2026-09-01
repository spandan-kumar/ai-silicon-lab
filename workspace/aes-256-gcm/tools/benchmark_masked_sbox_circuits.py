#!/usr/bin/env python3
"""Compile public AES S-box SLPs to first-order HPC2 pipelines and map them."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path

from benchmark_sbox_circuits import (
    CIRCUITS,
    CONSTRAINTS,
    DEFAULT_LIBERTY,
    LOGICAL_LOG_HASH_RE,
    NANGATE45_SHA256,
    PINNED_NIST_REVISION,
    ROOT,
    TIMING_RE,
    acquire_source,
    parse_slp,
    relative,
    sha256_file,
)


HPC2_SOURCE = "https://www.eng.biu.ac.il/leviita2/files/2020/12/Hardware-Private-Circuits-From-Trivial-Composition-to-Full-Verification.pdf"
FUNCTIONAL_MASK_TRIALS = 16
FUNCTIONAL_VECTORS = 256 * FUNCTIONAL_MASK_TRIALS


def sanitize(name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_]", "_", name)


class PipelineCompiler:
    """Schedule an XOR/AND SLP using the asymmetric two-stage HPC2 gadget."""

    def __init__(self, operations: list[tuple[str, str, str, str]]) -> None:
        self.operations = operations
        self.arrival = {f"U{index}": 0 for index in range(8)}
        self.declarations: list[str] = []
        self.assignments: list[str] = []
        self.vector_registers: list[tuple[str, str]] = []
        self.scalar_registers: list[tuple[str, str]] = []
        self.vector_delays: dict[tuple[str, int], str] = {}
        self.scalar_delays: dict[tuple[str, int], str] = {}
        self.and_index = 0
        self.swapped_ands = 0

    def delay_vector(self, signal: str, source_cycle: int, target_cycle: int) -> str:
        previous = signal
        for cycle in range(source_cycle + 1, target_cycle + 1):
            key = (signal, cycle)
            if key not in self.vector_delays:
                delayed = f"delay_{sanitize(signal)}_{cycle}"
                self.declarations.append(f"  logic [1:0] {delayed};")
                self.vector_registers.append((delayed, previous))
                self.vector_delays[key] = delayed
            previous = self.vector_delays[key]
        return previous

    def delay_scalar(self, signal: str, source_cycle: int, target_cycle: int) -> str:
        previous = signal
        for cycle in range(source_cycle + 1, target_cycle + 1):
            key = (signal, cycle)
            if key not in self.scalar_delays:
                delayed = f"delay_{sanitize(signal)}_{cycle}"
                self.declarations.append(f"  logic {delayed};")
                self.scalar_registers.append((delayed, previous))
                self.scalar_delays[key] = delayed
            previous = self.scalar_delays[key]
        return previous

    def compile_operation(self, operation: str, output: str, left: str, right: str) -> None:
        self.declarations.append(f"  logic [1:0] {output};")
        if operation in {"XOR", "XNOR"}:
            output_cycle = max(self.arrival[left], self.arrival[right])
            left_aligned = self.delay_vector(left, self.arrival[left], output_cycle)
            right_aligned = self.delay_vector(right, self.arrival[right], output_cycle)
            share0 = f"{left_aligned}[0] ^ {right_aligned}[0]"
            share1 = f"{left_aligned}[1] ^ {right_aligned}[1]"
            if operation == "XNOR":
                share0 = f"~({share0})"
            self.assignments.append(f"  assign {output}[0] = {share0};")
            self.assignments.append(f"  assign {output}[1] = {share1};")
            self.arrival[output] = output_cycle
            return

        normal_cycle = max(self.arrival[left] + 1, self.arrival[right] + 2)
        swapped_cycle = max(self.arrival[right] + 1, self.arrival[left] + 2)
        if swapped_cycle < normal_cycle:
            first, second = right, left
            output_cycle = swapped_cycle
            self.swapped_ands += 1
        else:
            first, second = left, right
            output_cycle = normal_cycle
        first_aligned = self.delay_vector(
            first, self.arrival[first], output_cycle - 1
        )
        second_aligned = self.delay_vector(
            second, self.arrival[second], output_cycle - 2
        )
        random_name = f"random_{self.and_index}"
        self.declarations.append(f"  wire {random_name} = fresh_random[{self.and_index}];")
        random_aligned = self.delay_scalar(random_name, 0, output_cycle - 2)
        self.assignments.append(
            f"  hpc2_and_first_order hpc2_{self.and_index} ("
            f".clk, .rst, .a({first_aligned}), .b({second_aligned}), "
            f".r({random_aligned}), .c({output}));"
        )
        self.and_index += 1
        self.arrival[output] = output_cycle

    def render(self) -> tuple[str, int, int]:
        for index in range(8):
            self.declarations.append(f"  wire [1:0] U{index};")
            self.assignments.append(
                f"  assign U{index} = {{in_share1[{7 - index}], in_share0[{7 - index}]}};"
            )
        for operation in self.operations:
            self.compile_operation(*operation)
        latency = max(self.arrival[f"S{index}"] for index in range(8))
        output_signals = [
            self.delay_vector(f"S{index}", self.arrival[f"S{index}"], latency)
            for index in range(8)
        ]
        output_assignments: list[str] = []
        for index, signal in enumerate(output_signals):
            output_assignments.append(
                f"  assign out_share0[{7 - index}] = {signal}[0];"
            )
            output_assignments.append(
                f"  assign out_share1[{7 - index}] = {signal}[1];"
            )
        register_body = [
            "  always_ff @(posedge clk) begin",
            "    if (rst) begin",
            *(f"      {destination} <= '0;" for destination, _ in self.vector_registers),
            *(f"      {destination} <= 1'b0;" for destination, _ in self.scalar_registers),
            "      valid_pipeline <= '0;",
            "    end else begin",
            *(f"      {destination} <= {source};" for destination, source in self.vector_registers),
            *(f"      {destination} <= {source};" for destination, source in self.scalar_registers),
            "      valid_pipeline <= {valid_pipeline[LATENCY-2:0], in_valid};",
            "    end",
            "  end",
        ]
        text = f"""// Generated research artifact; see tools/benchmark_masked_sbox_circuits.py.
module hpc2_and_first_order (
    input logic clk,
    input logic rst,
    input logic [1:0] a,
    input logic [1:0] b,
    input logic r,
    output logic [1:0] c
);
  logic [1:0] b_stage1;
  logic [1:0] b_cross_masked_stage1;
  logic r_stage1;
  logic [1:0] same_domain_stage2;
  logic [1:0] complement_mask_stage2;
  logic [1:0] cross_domain_stage2;

  always_ff @(posedge clk) begin
    if (rst) begin
      b_stage1 <= '0;
      b_cross_masked_stage1 <= '0;
      r_stage1 <= 1'b0;
      same_domain_stage2 <= '0;
      complement_mask_stage2 <= '0;
      cross_domain_stage2 <= '0;
    end else begin
      b_stage1 <= b;
      b_cross_masked_stage1[0] <= b[1] ^ r;
      b_cross_masked_stage1[1] <= b[0] ^ r;
      r_stage1 <= r;
      same_domain_stage2 <= a & b_stage1;
      complement_mask_stage2 <= (~a) & {{2{{r_stage1}}}};
      cross_domain_stage2 <= a & b_cross_masked_stage1;
    end
  end

  assign c = same_domain_stage2 ^ complement_mask_stage2 ^ cross_domain_stage2;
endmodule

module masked_sbox_pipeline #(
    parameter integer LATENCY = {latency},
    parameter integer RANDOM_BITS = {self.and_index}
) (
    input logic clk,
    input logic rst,
    input logic in_valid,
    input logic [7:0] in_share0,
    input logic [7:0] in_share1,
    input logic [RANDOM_BITS-1:0] fresh_random,
    output logic out_valid,
    output logic [7:0] out_share0,
    output logic [7:0] out_share1
);
  logic [LATENCY-1:0] valid_pipeline;
{chr(10).join(self.declarations)}

{chr(10).join(self.assignments)}

{chr(10).join(register_body)}

  assign out_valid = valid_pipeline[LATENCY-1];
{chr(10).join(output_assignments)}
endmodule
"""
        return text, latency, self.swapped_ands


def harness_text(latency: int) -> str:
    return f"""#include <array>
#include <cstdint>
#include <cstdio>
#include "Vmasked_sbox_pipeline.h"
#include "verilated.h"

static constexpr std::array<uint8_t, 256> kSbox = {{
  0x63,0x7c,0x77,0x7b,0xf2,0x6b,0x6f,0xc5,0x30,0x01,0x67,0x2b,0xfe,0xd7,0xab,0x76,
  0xca,0x82,0xc9,0x7d,0xfa,0x59,0x47,0xf0,0xad,0xd4,0xa2,0xaf,0x9c,0xa4,0x72,0xc0,
  0xb7,0xfd,0x93,0x26,0x36,0x3f,0xf7,0xcc,0x34,0xa5,0xe5,0xf1,0x71,0xd8,0x31,0x15,
  0x04,0xc7,0x23,0xc3,0x18,0x96,0x05,0x9a,0x07,0x12,0x80,0xe2,0xeb,0x27,0xb2,0x75,
  0x09,0x83,0x2c,0x1a,0x1b,0x6e,0x5a,0xa0,0x52,0x3b,0xd6,0xb3,0x29,0xe3,0x2f,0x84,
  0x53,0xd1,0x00,0xed,0x20,0xfc,0xb1,0x5b,0x6a,0xcb,0xbe,0x39,0x4a,0x4c,0x58,0xcf,
  0xd0,0xef,0xaa,0xfb,0x43,0x4d,0x33,0x85,0x45,0xf9,0x02,0x7f,0x50,0x3c,0x9f,0xa8,
  0x51,0xa3,0x40,0x8f,0x92,0x9d,0x38,0xf5,0xbc,0xb6,0xda,0x21,0x10,0xff,0xf3,0xd2,
  0xcd,0x0c,0x13,0xec,0x5f,0x97,0x44,0x17,0xc4,0xa7,0x7e,0x3d,0x64,0x5d,0x19,0x73,
  0x60,0x81,0x4f,0xdc,0x22,0x2a,0x90,0x88,0x46,0xee,0xb8,0x14,0xde,0x5e,0x0b,0xdb,
  0xe0,0x32,0x3a,0x0a,0x49,0x06,0x24,0x5c,0xc2,0xd3,0xac,0x62,0x91,0x95,0xe4,0x79,
  0xe7,0xc8,0x37,0x6d,0x8d,0xd5,0x4e,0xa9,0x6c,0x56,0xf4,0xea,0x65,0x7a,0xae,0x08,
  0xba,0x78,0x25,0x2e,0x1c,0xa6,0xb4,0xc6,0xe8,0xdd,0x74,0x1f,0x4b,0xbd,0x8b,0x8a,
  0x70,0x3e,0xb5,0x66,0x48,0x03,0xf6,0x0e,0x61,0x35,0x57,0xb9,0x86,0xc1,0x1d,0x9e,
  0xe1,0xf8,0x98,0x11,0x69,0xd9,0x8e,0x94,0x9b,0x1e,0x87,0xe9,0xce,0x55,0x28,0xdf,
  0x8c,0xa1,0x89,0x0d,0xbf,0xe6,0x42,0x68,0x41,0x99,0x2d,0x0f,0xb0,0x54,0xbb,0x16
}};

static void tick(Vmasked_sbox_pipeline& dut) {{
  dut.clk = 0; dut.eval();
  dut.clk = 1; dut.eval();
}}

int main(int argc, char** argv) {{
  Verilated::commandArgs(argc, argv);
  Vmasked_sbox_pipeline dut;
  dut.rst = 1; dut.in_valid = 0; tick(dut); tick(dut);
  dut.rst = 0;
  static constexpr unsigned kMaskTrials = {FUNCTIONAL_MASK_TRIALS};
  static constexpr unsigned kVectorCount = 256 * kMaskTrials;
  std::array<uint8_t, kVectorCount> expected{{}};
  unsigned produced = 0;
  for (unsigned cycle = 0; cycle < kVectorCount + {latency} + 2; ++cycle) {{
    if (cycle < kVectorCount) {{
      const uint8_t value = static_cast<uint8_t>(cycle & 0xffu);
      const unsigned trial = cycle >> 8;
      const uint8_t mask = static_cast<uint8_t>(
          cycle * 73u + trial * 151u + 41u);
      dut.in_valid = 1;
      dut.in_share0 = mask;
      dut.in_share1 = mask ^ value;
      dut.fresh_random = 0x9e3779b9u * (cycle + 1u) ^
                         0x85ebca6bu * (trial + 1u);
      expected[cycle] = kSbox[value];
    }} else {{
      dut.in_valid = 0;
      dut.in_share0 = 0;
      dut.in_share1 = 0;
      dut.fresh_random = 0;
    }}
    tick(dut);
    if (dut.out_valid) {{
      if (produced >= expected.size()) return 2;
      const uint8_t actual = dut.out_share0 ^ dut.out_share1;
      if (actual != expected[produced]) {{
        std::fprintf(stderr, "mismatch index=%u expected=%02x actual=%02x\\n",
                     produced, expected[produced], actual);
        return 1;
      }}
      ++produced;
    }}
  }}
  if (produced != expected.size()) {{
    std::fprintf(stderr, "expected %u outputs, got %u\\n", kVectorCount, produced);
    return 3;
  }}
  std::printf("masked-sbox-functional: PASS vectors=%u latency={latency}\\n",
              kVectorCount);
  return 0;
}}
"""


def verify_rtl(name: str, rtl: Path, latency: int, output: Path) -> str:
    harness = output / f"{name}-harness.cpp"
    harness.write_text(harness_text(latency))
    object_dir = (
        Path(tempfile.gettempdir()) /
        f"aisl-masked-sbox-verilator-{os.getuid()}" /
        f"{name}-{sha256_file(rtl)[:16]}"
    )
    object_dir.mkdir(parents=True, exist_ok=True)
    local_rtl = object_dir / "masked_sbox_pipeline.sv"
    local_harness = object_dir / "harness.cpp"
    shutil.copy2(rtl, local_rtl)
    shutil.copy2(harness, local_harness)
    command = [
        "verilator", "--cc", "--exe", "--build", "--sv", "-Wall",
        "-Wno-DECLFILENAME",
        "--top-module", "masked_sbox_pipeline", "--Mdir", str(object_dir),
        "-CFLAGS", "-O3", str(local_rtl), str(local_harness),
    ]
    build = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if build.returncode != 0:
        raise SystemExit(build.stdout + build.stderr)
    result = subprocess.run(
        [str(object_dir / "Vmasked_sbox_pipeline")],
        check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def formal_gadget_wrapper_text() -> str:
    return """module hpc2_and_formal (
    input wire clk,
    input wire rst,
    input wire [1:0] a,
    input wire [1:0] b,
    input wire r
);
  wire [1:0] c;
  logic [1:0] b_reference_stage1;
  logic expected_stage2;

  hpc2_and_first_order dut (.clk, .rst, .a, .b, .r, .c);

  always @(posedge clk) begin
    if (rst) begin
      b_reference_stage1 <= 2'b00;
      expected_stage2 <= 1'b0;
    end else begin
      b_reference_stage1 <= b;
      expected_stage2 <= (a[0] ^ a[1]) &
                         (b_reference_stage1[0] ^ b_reference_stage1[1]);
    end
  end

  always @* begin
    if (!rst) assert ((c[0] ^ c[1]) == expected_stage2);
  end
endmodule
"""


def verify_gadget_formally(name: str, rtl: Path, output: Path) -> dict[str, object]:
    wrapper = output / f"{name}-hpc2-formal.sv"
    log = output / f"{name}-hpc2-formal.log"
    wrapper.write_text(formal_gadget_wrapper_text())
    script = (
        f"read_verilog -formal -sv {relative(rtl)} {relative(wrapper)}; "
        "prep -top hpc2_and_formal -flatten; "
        "chformal -lower; "
        "sat -seq 4 -prove-asserts -set-init-zero "
        "-set rst 0 -set-at 1 rst 1"
    )
    result = subprocess.run(
        ["yosys", "-q", "-l", str(log), "-p", script],
        cwd=ROOT, capture_output=True, text=True,
    )
    if result.returncode != 0:
        raise SystemExit(result.stdout + result.stderr + log.read_text())
    log_text = log.read_text()
    if "SAT proof finished - no model found: SUCCESS!" not in log_text:
        raise SystemExit(f"HPC2 gadget proof did not report success for {name}")
    logical_hash = LOGICAL_LOG_HASH_RE.findall(log_text)
    if len(logical_hash) != 1:
        raise SystemExit(f"formal log hash missing for {name}")
    return {
        "formal_hpc2_gadget_functional_pass": True,
        "formal_hpc2_sequence_steps": 4,
        "formal_hpc2_yosys_logical_log_hash": logical_hash[0],
    }


def map_rtl(name: str, rtl: Path, liberty: Path, output: Path) -> dict[str, object]:
    stat_path = output / f"{name}-stat.json"
    netlist_path = output / f"{name}-netlist.v"
    log_path = output / f"{name}.log"
    script = (
        f"read_verilog -sv {relative(rtl)}; hierarchy -top masked_sbox_pipeline; "
        "synth -top masked_sbox_pipeline -flatten; "
        f"dfflibmap -liberty {relative(liberty)}; "
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
    logical_hash = LOGICAL_LOG_HASH_RE.findall(log_text)
    if len(timing) != 1 or len(logical_hash) != 1:
        raise SystemExit(f"incomplete Yosys evidence for {name}")
    _, delay_ps = map(float, timing[0])
    internal_types = sorted(
        cell for cell in statistics["num_cells_by_type"]
        if cell.startswith("$") and cell != "$scopeinfo"
    )
    if internal_types:
        raise SystemExit(f"unmapped internal cells for {name}: {internal_types}")
    return {
        "mapped_cell_count": (
            statistics["num_cells"] -
            statistics["num_cells_by_type"].get("$scopeinfo", 0)
        ),
        "mapped_cell_types": {
            key: value for key, value in statistics["num_cells_by_type"].items()
            if key != "$scopeinfo"
        },
        "total_cell_area_um2": statistics["area"],
        "sequential_cell_area_um2": statistics["sequential_area"],
        "critical_combinational_delay_ps": delay_ps,
        "stat_sha256": sha256_file(stat_path),
        "netlist_sha256": sha256_file(netlist_path),
        "yosys_logical_log_hash": logical_hash[0],
    }


def create_functional_cell_model(liberty: Path, output: Path) -> Path:
    cell_model = output / "nangate45-functional-cells.v"
    script = (
        f"read_liberty -ignore_miss_func -ignore_miss_data_latch {relative(liberty)}; "
        f"write_verilog -noattr {relative(cell_model)}"
    )
    subprocess.run(["yosys", "-q", "-p", script], check=True, cwd=ROOT)
    return cell_model


def verify_mapped_netlist(
    name: str,
    netlist: Path,
    cell_model: Path,
    latency: int,
    output: Path,
) -> dict[str, object]:
    harness = output / f"{name}-mapped-harness.cpp"
    harness.write_text(harness_text(latency))
    object_dir = (
        Path(tempfile.gettempdir()) /
        f"aisl-masked-sbox-gate-verilator-{os.getuid()}" /
        f"{name}-{sha256_file(netlist)[:16]}"
    )
    object_dir.mkdir(parents=True, exist_ok=True)
    local_netlist = object_dir / "masked_sbox_pipeline-netlist.v"
    local_cells = object_dir / "nangate45-functional-cells.v"
    local_harness = object_dir / "harness.cpp"
    shutil.copy2(netlist, local_netlist)
    shutil.copy2(cell_model, local_cells)
    shutil.copy2(harness, local_harness)
    command = [
        "verilator", "--cc", "--exe", "--build", "--sv", "-Wall",
        "-Wno-DECLFILENAME", "-Wno-UNUSEDSIGNAL", "-Wno-UNDRIVEN",
        "--top-module", "masked_sbox_pipeline", "--Mdir", str(object_dir),
        "-CFLAGS", "-O3", str(local_netlist), str(local_cells), str(local_harness),
    ]
    build = subprocess.run(command, cwd=ROOT, capture_output=True, text=True)
    if build.returncode != 0:
        raise SystemExit(build.stdout + build.stderr)
    result = subprocess.run(
        [str(object_dir / "Vmasked_sbox_pipeline")],
        check=True, capture_output=True, text=True,
    )
    return {
        "mapped_netlist_functional_pass": True,
        "mapped_netlist_functional_vectors": FUNCTIONAL_VECTORS,
        "mapped_netlist_functional_output": result.stdout.strip(),
        "functional_cell_model_sha256": sha256_file(cell_model),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output-dir", type=Path, default=ROOT / "build" / "masked-sbox-study")
    parser.add_argument("--summary-output", type=Path)
    parser.add_argument("--liberty", type=Path, default=DEFAULT_LIBERTY)
    parser.add_argument("--circuit", action="append", choices=CIRCUITS)
    args = parser.parse_args()
    for tool in ("yosys", "verilator"):
        if shutil.which(tool) is None:
            raise SystemExit(f"{tool} is required")
    liberty = args.liberty.resolve()
    if not liberty.exists() or sha256_file(liberty) != NANGATE45_SHA256:
        raise SystemExit("pinned Nangate45 Liberty file missing or corrupt")
    output = args.output_dir.resolve()
    sources = output / "sources"
    generated = output / "generated"
    sources.mkdir(parents=True, exist_ok=True)
    generated.mkdir(parents=True, exist_ok=True)
    cell_model = create_functional_cell_model(liberty, output)
    selected = set(args.circuit or CIRCUITS)
    summary: dict[str, object] = {
        "schema_version": 1,
        "study": "first-order-hpc2-public-aes-sbox-circuits-v1",
        "claim_boundary": (
            "all 256 input values under 16 deterministic mask/random trials pass at RTL "
            "and mapped-netlist level, and the implemented HPC2 gadget passes a universal "
            "functional SAT proof; the complete generated netlists have not passed an "
            "independent formal leakage verifier or physical leakage test"
        ),
        "hpc2_primary_source": HPC2_SOURCE,
        "nist_revision": PINNED_NIST_REVISION,
        "tools": {
            "yosys": subprocess.run(
                ["yosys", "-V"], check=True, capture_output=True, text=True
            ).stdout.strip(),
            "verilator": subprocess.run(
                ["verilator", "--version"], check=True, capture_output=True, text=True
            ).stdout.strip(),
        },
        "library_sha256": NANGATE45_SHA256,
        "constraints_sha256": sha256_file(CONSTRAINTS),
        "circuits": {},
    }
    for name, metadata in CIRCUITS.items():
        if name not in selected:
            continue
        source = acquire_source(name, metadata, sources)
        operations = parse_slp(source, int(metadata["gates"]))
        compiler = PipelineCompiler(operations)
        rtl_text, latency, swaps = compiler.render()
        rtl = generated / f"{name}.sv"
        rtl.write_text(rtl_text)
        functional_output = verify_rtl(name, rtl, latency, output)
        formal = verify_gadget_formally(name, rtl, output)
        mapped = map_rtl(name, rtl, liberty, output)
        gate_functional = verify_mapped_netlist(
            name, output / f"{name}-netlist.v", cell_model, latency, output
        )
        result = {
            **metadata,
            "source_sha256": sha256_file(source),
            "generated_rtl_sha256": hashlib.sha256(rtl_text.encode()).hexdigest(),
            "masking_scheme": "first-order HPC2",
            "shares": 2,
            "fresh_random_bits_per_sbox": compiler.and_index,
            "pipeline_latency_cycles": latency,
            "and_inputs_swapped_for_schedule": swaps,
            "functional_vectors": FUNCTIONAL_VECTORS,
            "functional_mask_trials_per_input": FUNCTIONAL_MASK_TRIALS,
            "functional_pass": True,
            "functional_output": functional_output,
            **formal,
            **mapped,
            **gate_functional,
        }
        result["area_latency_um2_cycles"] = round(
            float(result["total_cell_area_um2"]) * latency, 6
        )
        summary["circuits"][name] = result
        print(
            f"masked-sbox-study: PASS circuit={name} latency={latency} "
            f"random_bits={compiler.and_index} area_um2={result['total_cell_area_um2']:.3f} "
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
