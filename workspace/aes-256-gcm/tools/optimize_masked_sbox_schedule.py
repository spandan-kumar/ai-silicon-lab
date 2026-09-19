#!/usr/bin/env python3
"""Minimize HPC2 alignment-register bits for a fixed S-box topology/latency."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from hpc2_schedule import PipelineCompiler, ScheduledCompiler, cost, graph, load_schedule
from benchmark_sbox_circuits import parse_slp, sha256_file


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True, help="input SLP source file")
    parser.add_argument("--gates", type=int, required=True, help="expected source operation count")
    parser.add_argument("--output", type=Path, required=True, help="new evidence directory (must not exist)")
    parser.add_argument("--seconds", type=float, default=60, help="CP-SAT time limit (default: 60)")
    args = parser.parse_args()
    if args.seconds <= 0 or args.gates <= 0:
        parser.error("--seconds and --gates must be positive")
    if args.output.exists():
        parser.error(f"output directory already exists: {args.output}")

    # Keep --help usable without the optional solver environment.
    import ortools
    from ortools.sat.python import cp_model

    operations = parse_slp(args.source, args.gates)
    initial, _, _ = graph(operations)
    latency = max(initial[f"S{i}"] for i in range(8))
    model = cp_model.CpModel()
    times = {node: model.NewIntVar(0, latency, "cycle_" + node) for node in initial}
    last = {node: model.NewIntVar(0, latency, "last_" + node) for node in initial}
    swaps = {}
    random_delays = []
    for node in times:
        model.Add(last[node] >= times[node])
        model.AddHint(times[node], initial[node])
        if node in {f"U{i}" for i in range(8)}:
            model.Add(times[node] == 0)
    for operation, output, left, right in operations:
        if operation == "AND":
            swap = model.NewBoolVar("swap_" + output)
            swaps[output] = swap
            for source, lag in ((left, 1 + swap), (right, 2 - swap)):
                model.Add(times[output] >= times[source] + lag)
                model.Add(last[source] >= times[output] - lag)
            random_delays.append(times[output] - 2)
        else:
            for source in (left, right):
                model.Add(times[output] >= times[source])
                model.Add(last[source] >= times[output])
    for index in range(8):
        model.Add(last[f"S{index}"] == latency)
    model.AddMaxEquality(latency, [times[f"S{i}"] for i in range(8)])
    model.Minimize(2 * sum(last[node] - times[node] for node in times) + sum(random_delays))
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = args.seconds
    solver.parameters.num_search_workers = 1
    solver.parameters.random_seed = 20260918
    solver.parameters.log_search_progress = True
    status = solver.Solve(model)
    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        raise SystemExit("no candidate: " + solver.StatusName(status))
    scheduled = {node: solver.Value(cycle) for node, cycle in times.items()}
    oriented = []
    edges = []
    for operation, output, left, right in operations:
        if operation == "AND" and solver.Value(swaps[output]):
            left, right = right, left
        oriented.append((operation, output, left, right))
        edges.extend([
            (left, output, 1 if operation == "AND" else 0),
            (right, output, 2 if operation == "AND" else 0),
        ])
    compiler = ScheduledCompiler(oriented, scheduled)
    rtl, new_latency, _ = compiler.render()
    measured = 2 * len(compiler.vector_registers) + len(compiler.scalar_registers)
    if new_latency != latency or not (
        measured == round(solver.ObjectiveValue()) == cost(scheduled, edges, oriented, latency)
    ):
        raise RuntimeError("solver objective, independent cost, and generated RTL disagree")
    baseline = PipelineCompiler(operations)
    baseline.render()
    record = {
        "source": str(args.source.resolve()), "source_sha256": sha256_file(args.source),
        "ortools_version": ortools.__version__, "solver_status": solver.StatusName(status),
        "best_bound": solver.BestObjectiveBound(), "solver_wall_seconds": solver.WallTime(),
        "solver_time_limit_seconds": args.seconds, "solver_random_seed": 20260918,
        "solver_search_workers": 1, "schedule": scheduled, "oriented_operations": oriented,
        "latency": latency, "random_bits": compiler.and_index,
        "baseline_alignment_register_bits": 2 * len(baseline.vector_registers) + len(baseline.scalar_registers),
        "scheduled_alignment_register_bits": measured,
        "claim": "Minimum alignment-register bits only if solver_status OPTIMAL; fixed topology and HPC2 gadget. No area, timing, security or novelty inference.",
    }
    args.output.mkdir(parents=True, exist_ok=False)
    (args.output / "scheduled.sv").write_text(rtl)
    (args.output / "model.pbtxt").write_text(str(model.Proto()))
    record_path = args.output / "schedule.json"
    record_path.write_text(json.dumps(record, indent=2) + "\n")
    load_schedule(record_path)
    print(json.dumps({key: value for key, value in record.items() if key not in {"schedule", "oriented_operations"}}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
