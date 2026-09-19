#!/usr/bin/env python3
"""Run independent fullVerif composition checks for a validated HPC2 schedule."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys

from benchmark_sbox_circuits import CIRCUITS, sha256_file
from hpc2_schedule import ScheduledCompiler, load_schedule, validate_operations, validate_rtl
import verify_masked_sbox_fullverif as verify


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--schedule", type=Path, required=True, help="schedule.json with adjacent scheduled.sv")
    parser.add_argument("--source", type=Path, help="relocated SLP source; must match the recorded hash")
    parser.add_argument("--circuit", choices=CIRCUITS, required=True, help="pinned source matching the schedule")
    parser.add_argument("--fullverif-root", type=Path, required=True, help="built fullVerif checkout")
    parser.add_argument("--output-dir", type=Path, required=True, help="new composition-evidence directory")
    parser.add_argument("--summary-output", type=Path)
    args = parser.parse_args()
    schedule = load_schedule(args.schedule, args.source)
    source_rtl = args.schedule.resolve().parent / "scheduled.sv"
    validate_rtl(schedule, source_rtl)
    if CIRCUITS[args.circuit]["sha256"] != schedule["source_sha256"]:
        parser.error("--circuit does not match the schedule's pinned source hash")
    if args.output_dir.exists():
        parser.error(f"output directory already exists: {args.output_dir}")
    if args.summary_output and args.summary_output.exists():
        parser.error(f"summary already exists: {args.summary_output}")
    operations = [tuple(operation) for operation in schedule["oriented_operations"]]
    cycles = schedule["schedule"]

    class GraphCompiler(verify.FullVerifCompiler):
        def __init__(self, original):
            super().__init__(operations)
            self.swapped_ands = validate_operations(original, operations)

        def compile_operation(self, operation, output, left, right):
            cycle = cycles[output]
            if operation in {"XOR", "XNOR"}:
                lhs = self.delay_vector(self.signals[left], self.arrival[left], cycle)
                rhs = self.delay_vector(self.signals[right], self.arrival[right], cycle)
                result = self.new_wire(output + "_xor")
                self.instances.append(
                    f"  MSKxor #(.d(2)) xor_{self.instance_index} "
                    f"(.ina({lhs}), .inb({rhs}), .out({result}));"
                )
                if operation == "XNOR":
                    previous = result
                    result = self.new_wire(output)
                    self.instances.append(
                        f"  MSKinv #(.d(2)) inv_{self.instance_index} "
                        f"(.in({previous}), .out({result}));"
                    )
            else:
                lhs = self.delay_vector(self.signals[left], self.arrival[left], cycle - 1)
                rhs = self.delay_vector(self.signals[right], self.arrival[right], cycle - 2)
                random = f"random_{self.and_count}"
                self.declarations.append(f"  wire {random} = fresh_random[{self.and_count}];")
                aligned = self.delay_random(random, 0, cycle - 2)
                result = self.new_wire(output)
                self.instances.append(
                    f"  MSKand_HPC2 #(.d(2)) hpc2_{self.and_count} "
                    f"(.ina({lhs}), .inb({rhs}), .rnd({aligned}), .clk(clk), .out({result}));"
                )
                self.and_count += 1
            self.signals[output] = result
            self.arrival[output] = cycle

    class RTLCompiler(ScheduledCompiler):
        def __init__(self, original):
            super().__init__(operations, cycles)
            self.swapped_ands = validate_operations(original, operations)

    original_testbench = verify.testbench_text

    def sized_testbench(latency):
        bits = schedule["random_bits"]
        return original_testbench(latency).replace("[28:0]", f"[{bits - 1}:0]").replace(
            "29'h15555555", f"{bits}'h15555555"
        )

    # The existing verifier exposes only a CLI. Temporarily inject schedule
    # emitters and argv while retaining its synthesis, trace, cross-checks, and
    # independent fullVerif calls. Restore all injected state even on failure.
    original_graph, original_rtl, original_argv = verify.FullVerifCompiler, verify.PipelineCompiler, sys.argv
    verify.FullVerifCompiler = GraphCompiler
    verify.PipelineCompiler = RTLCompiler
    verify.testbench_text = sized_testbench
    sys.argv = [
        str(Path(verify.__file__)), "--circuit", args.circuit,
        "--fullverif-root", str(args.fullverif_root), "--output-dir", str(args.output_dir),
    ]
    if args.summary_output:
        sys.argv.extend(["--summary-output", str(args.summary_output)])
    try:
        status = verify.main()
    finally:
        verify.FullVerifCompiler = original_graph
        verify.PipelineCompiler = original_rtl
        verify.testbench_text = original_testbench
        sys.argv = original_argv
    summary_path = args.summary_output or args.output_dir / "fullverif_report.json"
    summary = json.loads(summary_path.read_text())
    summary["schedule_sha256"] = sha256_file(args.schedule)
    summary["scheduled_rtl_sha256"] = sha256_file(source_rtl)
    summary["security_boundary"] = (
        "Composition graph using the library's assumed-PINI HPC2 gadget; "
        "not a leakage proof of the mapped netlist. Cleared-state checks concern "
        "sharing validity after pipeline flush, not reset zeroization."
    )
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
