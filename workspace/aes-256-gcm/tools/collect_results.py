#!/usr/bin/env python3
"""Collect retained simulation and synthesis artifacts into the Pareto report."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

from run_synthesis import CONFIGURATIONS


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parents[1]
ORGANIZATIONS = {
    "iterative-1r1b": "one AES round/cycle; one GHASH bit/cycle",
    "unrolled-2r8b": "two AES rounds/cycle; eight GHASH bits/cycle",
    "balanced-1r8b": "one AES round/cycle; eight GHASH bits/cycle",
    "wide-2r16b": "two AES rounds/cycle; sixteen GHASH bits/cycle",
    "ultrawide-2r32b": "two AES rounds/cycle; thirty-two GHASH bits/cycle",
    "balanced-wide-1r16b": "one AES round/cycle; sixteen GHASH bits/cycle",
    "balanced-ultrawide-1r32b": "one AES round/cycle; thirty-two GHASH bits/cycle",
    "balanced-xwide-1r64b": "one AES round/cycle; sixty-four GHASH bits/cycle",
}


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(line: str) -> dict[str, str]:
    return dict(token.split("=", 1) for token in line.strip().split()[1:] if "=" in token)


def metric_value(name: str, value: str) -> object:
    if value == "null":
        return None
    if name in {"architecture", "case", "mode", "implementation"}:
        return value
    if "." in value:
        return float(value)
    return int(value)


def parse_gcm(path: Path) -> dict[str, object]:
    metrics = []
    summary = None
    for line in path.read_text().splitlines():
        if line.startswith("METRIC "):
            metrics.append({key: metric_value(key, value) for key, value in fields(line).items()})
        elif line.startswith("GCM RTL: PASS "):
            summary = {key: metric_value(key, value) for key, value in fields(line).items()}
    if summary is None or len(metrics) != 96:
        raise SystemExit(f"incomplete GCM evidence in {path}: summary={summary is not None}, metrics={len(metrics)}")
    return {"summary": summary, "throughput_sweep": metrics, "log_sha256": sha256(path)}


def parse_primitive(path: Path) -> dict[str, object]:
    lines = [line for line in path.read_text().splitlines() if line.startswith("primitive RTL: PASS ")]
    if len(lines) != 1:
        raise SystemExit(f"incomplete primitive evidence in {path}")
    return {
        **{key: metric_value(key, value) for key, value in fields(lines[0]).items()},
        "log_sha256": sha256(path),
    }


def pareto_names(points: dict[str, tuple[float, float]]) -> list[str]:
    result = []
    for candidate, (area, latency) in points.items():
        dominated = any(
            other != candidate
            and other_area <= area
            and other_latency <= latency
            and (other_area < area or other_latency < latency)
            for other, (other_area, other_latency) in points.items()
        )
        if not dominated:
            result.append(candidate)
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs", type=Path, default=ROOT / "build" / "logs")
    parser.add_argument("--synthesis", type=Path, default=ROOT / "build" / "synth")
    parser.add_argument("--asic-synthesis", type=Path, default=ROOT / "build" / "asic-synth")
    parser.add_argument("--gate-verification", type=Path, default=ROOT / "build" / "gate-verify" / "summary.json")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY, check=True, capture_output=True, text=True
    ).stdout.strip()
    nist = json.loads((ROOT / "vectors" / "nist_subset.json").read_text())
    generated = json.loads((ROOT / "vectors" / "generated.json").read_text())
    software = json.loads((ROOT / "reports" / "software_baseline.json").read_text())
    asic_summary = json.loads((args.asic_synthesis / "summary.json").read_text())
    gate_verification = json.loads(args.gate_verification.read_text())
    key_schedule_log = args.logs / "key-schedule.txt"
    if key_schedule_log.read_text().strip() != "key schedule RTL: PASS vectors=5 round_keys_per_vector=15":
        raise SystemExit("incomplete key-schedule evidence")
    sbox_log = args.logs / "sbox.txt"
    if "S-box RTL: PASS forward=256 inverse=256" not in sbox_log.read_text():
        raise SystemExit("incomplete exhaustive S-box evidence")

    primitive_cache = {
        "iterative": parse_primitive(args.logs / "primitive-iterative.txt"),
        "parallel": parse_primitive(args.logs / "primitive-parallel.txt"),
    }
    architectures: dict[str, object] = {}
    pareto_points: dict[str, tuple[float, float]] = {}
    for name, configuration in CONFIGURATIONS.items():
        stem = str(configuration["stem"])
        stat_path = args.synthesis / f"{stem}-stat.json"
        statistics = json.loads(stat_path.read_text())
        gcm = parse_gcm(args.logs / f"gcm-{stem}.txt")
        primitive_kind = "iterative" if "1r" in name else "parallel"
        primitive = primitive_cache[primitive_kind]
        repeat_a = ROOT / "build" / "repeatability" / f"{stem}-a.txt"
        repeat_b = ROOT / "build" / "repeatability" / f"{stem}-b.txt"
        if repeat_a.read_bytes() != repeat_b.read_bytes():
            raise SystemExit(f"repeatability mismatch for {name}")
        representative = next(
            item for item in gcm["throughput_sweep"]
            if item["case"] == "perf-iv12-aad0-data64-encrypt"
        )
        asic = asic_summary["architectures"][name]
        latency_ns = representative["warm_cycles"] * asic["critical_combinational_delay_ps"] / 1000.0
        throughput_gbps = representative["bytes_per_cycle"] * asic["prelayout_fmax_mhz"] * 8.0 / 1000.0
        pareto_points[name] = (asic["total_cell_area_um2"], latency_ns)
        architectures[name] = {
            "organization": ORGANIZATIONS[name],
            "correctness": {
                "status": "pass",
                "primitive": primitive,
                "gcm": gcm["summary"],
                "negative_authentication_cases": len(generated["negative"]),
                "stalled_replays": 32,
                "lifecycle_and_error_scenarios": [
                    "no-key rejection", "unsupported lengths", "warm-key repeat",
                    "key replacement", "reset during key setup/AAD/tag/output/result/error",
                    "zeroize during payload input", "authentication failure then reuse",
                    "explicit zeroize after success",
                ],
            },
            "performance": {
                "representative_96bit_iv_0aad_64byte_encrypt": representative,
                "representative_prelayout_latency_ns_estimated": round(latency_ns, 6),
                "representative_prelayout_throughput_gbps_estimated": round(throughput_gbps, 6),
                "derivation": "warm cycles multiplied by ABC critical combinational delay; throughput assumes its reciprocal as the clock and excludes routing/clock uncertainty",
                "sweep": gcm["throughput_sweep"],
            },
            "synthesis": {
                "generic": {
                    "target": "generic Yosys Boolean-cell netlist; no technology mapping",
                    "generic_cell_count": statistics["design"]["num_cells"],
                    "generic_cell_types": statistics["design"]["num_cells_by_type"],
                    "stat_sha256": sha256(stat_path),
                },
                "nangate45_typical": asic,
                "timing_scope": asic_summary["scope"],
                "worst_slack": None,
                "power_watts": None,
                "energy_per_byte": None,
            },
            "repeatability": {"identical": True, "output_sha256": sha256(repeat_a)},
            "evidence": {
                "gcm_log_sha256": gcm["log_sha256"],
                "primitive_log_sha256": primitive["log_sha256"],
            },
        }

    frontier = pareto_names(pareto_points)
    for name in architectures:
        architectures[name]["pareto_nangate45_area_vs_representative_latency"] = name in frontier
    openssl_64 = next(
        item for item in software["baselines"]["openssl_evp_aes_256_gcm"]
        if item["payload_bytes"] == 64 and item["aad_bytes"] == 0
    )
    report = {
        "schema_version": 2,
        "experiment_id": "aes-256-gcm",
        "profile_id": "aes-256-gcm-64-v1",
        "candidate_commit": commit,
        "gate": "simulation-complete-plus-standard-cell-synthesis",
        "gate_status": "pass",
        "corpus": {
            "nist_aes_vectors": len(nist["aes_block"]),
            "nist_directional_gcm_vectors": len(nist["gcm"]),
            "generated_positive_vectors": len(generated["positive"]),
            "generated_negative_vectors": len(generated["negative"]),
            "gcm_operations_per_architecture": len(nist["gcm"]) + 2 * len(generated["positive"]) + len(generated["negative"]),
            "nist_sha256": sha256(ROOT / "vectors" / "nist_subset.json"),
            "generated_sha256": sha256(ROOT / "vectors" / "generated.json"),
            "seed": generated["seed"],
        },
        "sbox": {
            "status": "pass", "forward_inputs": 256, "inverse_inputs": 256,
            "implementation": "NIST circuit-complexity SLP g113 forward / g121 inverse",
            "log_sha256": sha256(sbox_log),
        },
        "key_schedule": {
            "status": "pass", "vectors": 5, "round_keys_per_vector": 15,
            "log_sha256": sha256(key_schedule_log),
        },
        "software_baseline": {
            "report": "reports/software_baseline.json",
            "openssl_64byte_0aad_cold_median_ns": openssl_64["median_ns_per_transaction"],
            "linked_openssl": software["tools"]["linked_openssl"],
            "measurement_scope": "host-specific cold-key wall time; not directly ranked against prelayout ASIC estimates",
        },
        "architectures": architectures,
        "pareto": {
            "objectives": ["Nangate45 mapped total cell area", "estimated representative prelayout warm latency"],
            "nondominated": frontier,
            "dominated": [name for name in architectures if name not in frontier],
            "universal_winner": None,
            "reason": "Power, routed timing, clock uncertainty, and scalar objective weights are not available.",
        },
        "mapped_netlist_verification": gate_verification,
        "unavailable": {
            "routed_timing_slack": None,
            "power": None,
            "energy_per_byte": None,
            "physical_leakage": None,
            "fault_resistance": None,
            "fips_validation": None,
            "reason": "This run performs named-library synthesis and prelayout ABC timing, but not floorplanning, placement, routing, parasitic extraction, clock-tree synthesis, power analysis, or physical security measurement.",
        },
        "security_review": "SECURITY.md",
        "reproduce": [
            "make -C workspace/aes-256-gcm check",
            "make -C workspace/aes-256-gcm asic-synthesis gate-verify",
            "make -C workspace/aes-256-gcm results",
            "workspace/aes-256-gcm/evaluate --run-id <unique-run-id>",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"results: PASS architectures={len(architectures)} pareto={len(frontier)} output={args.output} sha256={sha256(args.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
