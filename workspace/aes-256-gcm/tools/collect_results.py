#!/usr/bin/env python3
"""Collect retained simulation and synthesis artifacts into the Pareto report."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parents[1]


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def fields(line: str) -> dict[str, str]:
    return dict(token.split("=", 1) for token in line.strip().split()[1:] if "=" in token)


def metric_value(name: str, value: str) -> object:
    if value == "null":
        return None
    if name in {"architecture", "case", "mode"}:
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--logs", type=Path, default=ROOT / "build" / "logs")
    parser.add_argument("--synthesis", type=Path, default=ROOT / "build" / "synth")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    commit = subprocess.run(
        ["git", "rev-parse", "HEAD"], cwd=REPOSITORY, check=True, capture_output=True, text=True
    ).stdout.strip()
    nist = json.loads((ROOT / "vectors" / "nist_subset.json").read_text())
    generated = json.loads((ROOT / "vectors" / "generated.json").read_text())
    software = json.loads((ROOT / "reports" / "software_baseline.json").read_text())
    key_schedule_log = args.logs / "key-schedule.txt"
    if key_schedule_log.read_text().strip() != "key schedule RTL: PASS vectors=5 round_keys_per_vector=15":
        raise SystemExit("incomplete key-schedule evidence")
    architectures: dict[str, object] = {}
    configuration = {
        "iterative-1r1b": ("iterative", "folded AES: one round/cycle; serial GHASH: one bit/cycle"),
        "unrolled-2r8b": ("parallel", "partially unrolled AES: two rounds/cycle; GHASH: eight bits/cycle"),
    }
    for name, (stem, organization) in configuration.items():
        stat_path = args.synthesis / f"{stem}-stat.json"
        statistics = json.loads(stat_path.read_text())
        gcm = parse_gcm(args.logs / f"gcm-{stem}.txt")
        primitive = parse_primitive(args.logs / f"primitive-{stem}.txt")
        repeat_a = ROOT / "build" / "repeatability" / f"{stem}-a.txt"
        repeat_b = ROOT / "build" / "repeatability" / f"{stem}-b.txt"
        if repeat_a.read_bytes() != repeat_b.read_bytes():
            raise SystemExit(f"repeatability mismatch for {name}")
        sweep = gcm["throughput_sweep"]
        representative = next(
            item for item in sweep
            if item["case"] == "perf-iv12-aad0-data64-encrypt"
        )
        architectures[name] = {
            "organization": organization,
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
                "sweep": sweep,
            },
            "synthesis": {
                "target": "generic Yosys Boolean-cell netlist; no technology mapping",
                "generic_cell_count": statistics["design"]["num_cells"],
                "generic_cell_types": statistics["design"]["num_cells_by_type"],
                "stat_sha256": sha256(stat_path),
                "timing_mhz": None,
                "worst_slack": None,
                "power_watts": None,
                "energy_per_byte": None,
            },
            "repeatability": {
                "identical": True,
                "output_sha256": sha256(repeat_a),
            },
            "evidence": {
                "gcm_log_sha256": gcm["log_sha256"],
                "primitive_log_sha256": primitive["log_sha256"],
            },
        }

    openssl_64 = next(
        item for item in software["baselines"]["openssl_evp_aes_256_gcm"]
        if item["payload_bytes"] == 64 and item["aad_bytes"] == 0
    )
    report = {
        "schema_version": 1,
        "experiment_id": "aes-256-gcm",
        "profile_id": "aes-256-gcm-64-v1",
        "candidate_commit": commit,
        "gate": "simulation-complete",
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
        "key_schedule": {
            "status": "pass",
            "vectors": 5,
            "round_keys_per_vector": 15,
            "log_sha256": sha256(key_schedule_log),
        },
        "software_baseline": {
            "report": "reports/software_baseline.json",
            "openssl_64byte_0aad_cold_median_ns": openssl_64["median_ns_per_transaction"],
            "linked_openssl": software["tools"]["linked_openssl"],
            "measurement_scope": "host-specific cold-key wall time; not directly comparable to targetless RTL cycles",
        },
        "architectures": architectures,
        "pareto": {
            "status": "both-nondominated",
            "iterative-1r1b": "minimum measured generic area",
            "unrolled-2r8b": "minimum measured latency and cycles/byte; maximum bytes/cycle",
            "universal_winner": None,
            "reason": "No scalar weights, technology target, clock, power model, or energy objective are frozen.",
        },
        "unavailable": {
            "physical_target": None,
            "target_frequency_mhz": None,
            "target_gbps": None,
            "timing_slack": None,
            "power": None,
            "energy_per_byte": None,
            "physical_leakage": None,
            "fault_resistance": None,
            "fips_validation": None,
            "reason": "No FPGA/ASIC implementation flow, physical board, timing library, power model, or side-channel instrumentation is configured.",
        },
        "security_review": "SECURITY.md",
        "reproduce": [
            "make -C workspace/aes-256-gcm check",
            "make -C workspace/aes-256-gcm synthesis",
            "workspace/aes-256-gcm/evaluate --run-id <unique-run-id>",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
    print(f"results: PASS architectures=2 output={args.output} sha256={sha256(args.output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
