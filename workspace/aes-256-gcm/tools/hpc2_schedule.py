"""Validate and emit explicit schedules for the fixed two-share HPC2 gadget."""

from __future__ import annotations

import json
from pathlib import Path

from benchmark_masked_sbox_circuits import PipelineCompiler
from benchmark_sbox_circuits import ROOT, parse_slp, sha256_file


Operation = tuple[str, str, str, str]
Edge = tuple[str, str, int]


def graph(operations: list[Operation]) -> tuple[dict[str, int], list[Edge], list[Operation]]:
    """Return the original greedy schedule and its oriented dependency edges."""
    times = {f"U{i}": 0 for i in range(8)}
    edges: list[Edge] = []
    oriented: list[Operation] = []
    for operation, output, left, right in operations:
        if output in times or left not in times or right not in times:
            raise ValueError(f"SLP is not a single-assignment topological graph at {output}")
        if operation == "AND":
            if max(times[right] + 1, times[left] + 2) < max(times[left] + 1, times[right] + 2):
                left, right = right, left
            times[output] = max(times[left] + 1, times[right] + 2)
            edges.extend([(left, output, 1), (right, output, 2)])
        elif operation in {"XOR", "XNOR"}:
            times[output] = max(times[left], times[right])
            edges.extend([(left, output, 0), (right, output, 0)])
        else:
            raise ValueError(f"unsupported operation: {operation}")
        oriented.append((operation, output, left, right))
    if not all(f"S{i}" in times for i in range(8)):
        raise ValueError("SLP must define all eight S-box outputs")
    return times, edges, oriented


def cost(times: dict[str, int], edges: list[Edge], operations: list[Operation], latency: int) -> int:
    """Count alignment bits; exclude fixed gadget and valid-pipeline registers."""
    last = dict(times)
    for source, destination, lag in edges:
        last[source] = max(last[source], times[destination] - lag)
    for index in range(8):
        last[f"S{index}"] = latency
    return 2 * sum(last[node] - times[node] for node in times) + sum(
        times[output] - 2 for operation, output, _, _ in operations if operation == "AND"
    )


def validate_operations(original: list[Operation], oriented: list[Operation]) -> int:
    """Reject any topology change except exchanging operands of an AND."""
    if len(original) != len(oriented):
        raise ValueError("schedule and source operation counts differ")
    swaps = 0
    for source, scheduled in zip(original, oriented):
        operation, output, left, right = source
        if len(scheduled) != 4 or source[:2] != scheduled[:2]:
            raise ValueError(f"schedule changes operation or output at {output}")
        if source[2:] != scheduled[2:]:
            if operation != "AND" or (right, left) != scheduled[2:]:
                raise ValueError(f"schedule changes source operands at {output}")
            swaps += 1
    return swaps


def validate_cycles(operations: list[Operation], times: dict[str, int], latency: int) -> list[Edge]:
    """Check all producer/consumer lags independently of the RTL emitter."""
    nodes, _, _ = graph(operations)
    if type(latency) is not int or latency < 2:
        raise ValueError("pipeline latency must be an integer of at least two cycles")
    if set(times) != set(nodes):
        raise ValueError("schedule must assign exactly the source inputs and operation outputs")
    if any(type(cycle) is not int or not 0 <= cycle <= latency for cycle in times.values()):
        raise ValueError("schedule cycles must be integers between zero and latency")
    if any(times[f"U{i}"] != 0 for i in range(8)):
        raise ValueError("all input sharings must arrive in cycle zero")
    if max(times[f"S{i}"] for i in range(8)) != latency:
        raise ValueError("declared latency does not match the latest S-box output")
    edges = []
    for operation, output, left, right in operations:
        lags = (1, 2) if operation == "AND" else (0, 0)
        for source, lag in zip((left, right), lags):
            if times[output] < times[source] + lag:
                raise ValueError(f"invalid dependency timing: {source} -> {output}, lag {lag}")
            edges.append((source, output, lag))
    return edges


def load_schedule(path: Path, source: Path | None = None) -> dict:
    """Load a record and authenticate its source, topology, timing, and cost.

    Historical relative source paths are relative to the experiment workspace.
    An explicit source override supports relocated source archives, but must
    still match the record's SHA-256 fingerprint.
    """
    record = json.loads(path.read_text())
    source = source or Path(record["source"])
    source = source if source.is_absolute() else ROOT / source
    if sha256_file(source) != record["source_sha256"]:
        raise ValueError(f"schedule source SHA-256 mismatch: {source}")
    operations = [tuple(operation) for operation in record["oriented_operations"]]
    original = parse_slp(source, len(operations))
    validate_operations(original, operations)
    edges = validate_cycles(operations, record["schedule"], record["latency"])
    random_bits = sum(operation[0] == "AND" for operation in operations)
    if type(record["random_bits"]) is not int or record["random_bits"] != random_bits:
        raise ValueError("recorded random-bit count differs from source AND count")
    measured_cost = cost(record["schedule"], edges, operations, record["latency"])
    if record["scheduled_alignment_register_bits"] != measured_cost:
        raise ValueError("recorded alignment-register cost differs from the schedule")
    return record


class ScheduledCompiler(PipelineCompiler):
    """Emit the existing HPC2 RTL with validated, explicitly chosen cycles."""

    def __init__(self, operations: list[Operation], times: dict[str, int]) -> None:
        validate_cycles(operations, times, max(times[f"S{i}"] for i in range(8)))
        super().__init__(operations)
        self.schedule = dict(times)

    def compile_operation(self, operation: str, output: str, left: str, right: str) -> None:
        cycle = self.schedule[output]
        self.declarations.append(f"  logic [1:0] {output};")
        if operation in {"XOR", "XNOR"}:
            lhs = self.delay_vector(left, self.arrival[left], cycle)
            rhs = self.delay_vector(right, self.arrival[right], cycle)
            expression = f"{lhs}[0] ^ {rhs}[0]"
            if operation == "XNOR":
                expression = f"~({expression})"
            self.assignments.extend([
                f"  assign {output}[0] = {expression};",
                f"  assign {output}[1] = {lhs}[1] ^ {rhs}[1];",
            ])
        else:
            lhs = self.delay_vector(left, self.arrival[left], cycle - 1)
            rhs = self.delay_vector(right, self.arrival[right], cycle - 2)
            random = f"random_{self.and_index}"
            self.declarations.append(f"  wire {random} = fresh_random[{self.and_index}];")
            aligned = self.delay_scalar(random, 0, cycle - 2)
            self.assignments.append(
                f"  hpc2_and_first_order hpc2_{self.and_index} "
                f"(.clk, .rst, .a({lhs}), .b({rhs}), .r({aligned}), .c({output}));"
            )
            self.and_index += 1
        self.arrival[output] = cycle


def validate_rtl(record: dict, path: Path) -> None:
    """Require measurements to consume exactly the RTL implied by the record."""
    operations = [tuple(operation) for operation in record["oriented_operations"]]
    compiler = ScheduledCompiler(operations, record["schedule"])
    rtl, latency, _ = compiler.render()
    if path.read_bytes() != rtl.encode() or latency != record["latency"]:
        raise ValueError(f"scheduled RTL does not match the validated schedule: {path}")
