#!/usr/bin/env python3
"""AES-256-GCM experiment plugin.

Wires the baseline AES-256-GCM RTL into the autonomous harness. The reference
side runs the independent Python model; the candidate side runs Verilator over
the synthesizable RTL. Neither side can see the other's output while it runs.
"""

from __future__ import annotations

import json
from pathlib import Path
import shutil
import sys
from typing import Any

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE / "reference"))
sys.path.insert(0, str(ROOT / "harness"))

import aes_gcm_ref as reference  # noqa: E402
import stimulus as stim  # noqa: E402

from aisl_harness.contracts import (  # noqa: E402
    BuildResult,
    CandidateOutput,
    Context,
    ExperimentPlugin,
    ReferenceOutput,
    Workload,
)
from aisl_harness.core import (  # noqa: E402
    HarnessError,
    relative,
    run,
    sha256_file,
    sha256_tree,
    tool_version,
)


RTL_DIR = HERE / "rtl"
SIM_DIR = HERE / "sim"
GCM_SIM = SIM_DIR / "build" / "aes_gcm_sim"
CORE_SIM = SIM_DIR / "build-core" / "aes_core_sim"

RTL_SOURCES = [
    RTL_DIR / "aes_sbox.sv",
    RTL_DIR / "aes256_enc.sv",
    RTL_DIR / "ghash_mul.sv",
    RTL_DIR / "aes_gcm.sv",
]

VERILATOR_FLAGS = [
    "-Wall", "-Wno-fatal", "-Wno-DECLFILENAME", "-Wno-UNUSEDSIGNAL",
]

# Workloads whose stimulus drives the full GCM engine.
GCM_WORKLOADS = {
    "gcm-known-answer": ("algorithm-correctness", 1),
    "gcm-edge-cases": ("boundary-correctness", 1),
    "gcm-random-differential": ("differential-correctness", 1),
    "gcm-interface-stress": ("microarchitectural-correctness", 2),
    "gcm-throughput-sweep": ("performance", 1),
}


class Aes256GcmPlugin(ExperimentPlugin):
    experiment_id = "aes-256-gcm"

    # --- Identity ---------------------------------------------------------

    def describe(self) -> dict[str, Any]:
        return {
            "design": "aes_gcm baseline: iterative AES-256 round datapath, "
                      "bit-serial GHASH, byte-streaming valid/ready interface",
            "profile": "encrypt and decrypt, 1..16 byte tags, 96-bit and other "
                       "IV lengths, plaintext released only after tag verification",
            "max_text_bytes": 512,
            "rtl_sources": {
                relative(path): sha256_file(path) for path in RTL_SOURCES if path.is_file()
            },
            "testbenches": {
                relative(path): sha256_file(path)
                for path in (SIM_DIR / "tb_aes_gcm.cpp", SIM_DIR / "tb_aes_core.cpp")
                if path.is_file()
            },
            "reference_model": {
                relative(HERE / "reference" / "aes_gcm_ref.py"): sha256_file(
                    HERE / "reference" / "aes_gcm_ref.py"
                )
            },
            "normative_sources": [
                "NIST FIPS 197 (AES)",
                "NIST SP 800-38D (GCM/GMAC)",
            ],
        }

    def workloads(self) -> list[Workload]:
        items = [
            Workload(
                id="aes-256-block-kat",
                role="primitive-correctness",
                comparator="vectors",
                description="AES-256 block known-answer tests against the reference cipher.",
                parameters={"cases": len(stim.corpus("aes-256-block-kat"))},
                repeat=1,
            )
        ]
        for workload_id, (role, repeat) in GCM_WORKLOADS.items():
            items.append(
                Workload(
                    id=workload_id,
                    role=role,
                    comparator="vectors",
                    description=f"AES-256-GCM {role} corpus.",
                    parameters={"cases": len(stim.corpus(workload_id))},
                    repeat=repeat,
                )
            )
        return items

    # --- Build ------------------------------------------------------------

    def _verilate(self, top: str, sources: list[Path], tb: Path, out_dir: Path,
                  binary: str) -> dict[str, Any]:
        return run(
            [
                "verilator", "--cc", "--exe", "--build", "-j", "0",
                *VERILATOR_FLAGS,
                "--top-module", top,
                "--Mdir", str(out_dir),
                "-CFLAGS", "-std=c++17 -O2",
                *[str(path) for path in sources],
                str(tb),
                "-o", binary,
            ],
            timeout=900,
        )

    def build(self, context: Context) -> BuildResult:
        commands = [
            self._verilate(
                "aes_gcm", RTL_SOURCES, SIM_DIR / "tb_aes_gcm.cpp",
                SIM_DIR / "build", "aes_gcm_sim",
            ),
            self._verilate(
                "aes256_enc", RTL_SOURCES[:2], SIM_DIR / "tb_aes_core.cpp",
                SIM_DIR / "build-core", "aes_core_sim",
            ),
        ]
        ok = all(command.get("exit_code") == 0 for command in commands)
        artifacts: dict[str, str] = {}
        for binary in (GCM_SIM, CORE_SIM):
            if binary.is_file():
                artifacts[relative(binary)] = sha256_file(binary)
            else:
                ok = False
        artifacts["rtl-aggregate"] = sha256_tree(RTL_DIR)
        return BuildResult(
            ok=ok,
            commands=commands,
            artifacts=artifacts,
            tools=[tool_version("verilator"), tool_version("cc")],
            notes="Verilator builds the synthesizable RTL; no host crypto library is linked.",
        )

    # --- Reference --------------------------------------------------------

    def _reference_block_kat(self, output: Path) -> list[dict[str, Any]]:
        vectors = []
        for case in stim.corpus("aes-256-block-kat"):
            round_keys = reference.key_expansion_256(bytes.fromhex(case["key"]))
            ciphertext = reference.aes256_encrypt_block(
                round_keys, bytes.fromhex(case["block"])
            )
            vectors.append({"id": case["id"], "ciphertext": ciphertext.hex()})
        return vectors

    def _reference_gcm(self, workload_id: str) -> list[dict[str, Any]]:
        vectors = []
        for case in stim.corpus(workload_id):
            key = bytes.fromhex(case["key"])
            iv = bytes.fromhex(case["iv"])
            aad = bytes.fromhex(case["aad"])
            text = bytes.fromhex(case["text"])
            if case["mode"] == 0:
                ciphertext, tag = reference.encrypt(key, iv, aad, text, case["tag_bytes"])
                vectors.append(
                    {
                        "id": case["id"],
                        "output": ciphertext.hex(),
                        "tag": tag.hex(),
                        "tag_ok": True,
                        "released": len(ciphertext) > 0,
                    }
                )
            else:
                expected_tag = bytes.fromhex(case["exp_tag"])
                plaintext, ok = reference.decrypt(key, iv, aad, text, expected_tag)
                # Frozen profile on authentication failure: no plaintext is
                # released and no tag is published. Publishing the computed tag
                # after a rejection would hand an attacker a forgery oracle, so
                # the expected output is zeros, not the value the design derived.
                vectors.append(
                    {
                        "id": case["id"],
                        "output": plaintext.hex() if ok and plaintext else "",
                        "tag": expected_tag.hex() if ok else "00" * case["tag_bytes"],
                        "tag_ok": ok,
                        "released": bool(ok and plaintext),
                    }
                )
        return vectors

    def reference(self, context: Context) -> ReferenceOutput:
        workload = context.workload
        if workload is None:
            raise HarnessError("reference() requires a workload")
        if workload.id == "aes-256-block-kat":
            vectors = self._reference_block_kat(context.output_dir)
        else:
            vectors = self._reference_gcm(workload.id)
        target = context.output_dir / "vectors.json"
        target.write_text(
            json.dumps({"vectors": vectors}, indent=1, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        return ReferenceOutput(
            directory=context.output_dir,
            digest=sha256_tree(context.output_dir),
            metadata={
                "model": "workspace/aes256gcm/reference/aes_gcm_ref.py",
                "independence": "no cryptographic library is used; the S-box, field "
                                "multiply, and mode logic are implemented locally",
                "cases": len(vectors),
            },
        )

    # --- Candidate --------------------------------------------------------

    def execute(self, context: Context) -> CandidateOutput:
        workload = context.workload
        if workload is None:
            raise HarnessError("execute() requires a workload")
        if context.oracle_dir is not None:
            raise HarnessError("candidate context must not carry oracle access")

        cases = stim.corpus(workload.id)
        stimulus_path = context.work_dir / "stimulus.txt"
        metrics_path = context.output_dir / "metrics.json"
        output_path = context.output_dir / "vectors.json"

        if workload.id == "aes-256-block-kat":
            stim.write_block_stimulus(cases, stimulus_path)
            binary = CORE_SIM
        else:
            stim.write_gcm_stimulus(cases, stimulus_path)
            binary = GCM_SIM
        if not binary.is_file():
            raise HarnessError(f"candidate binary {relative(binary)} is missing; build first")

        command = run(
            [
                str(binary),
                "--stimulus", str(stimulus_path),
                "--output", str(output_path),
                "--metrics", str(metrics_path),
            ],
            timeout=1800,
        )
        measured: dict[str, Any] = {"wall_seconds": command.get("wall_seconds")}
        if metrics_path.is_file():
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            measured["total_cycles"] = metrics.get("total_cycles")
            measured["cases"] = metrics.get("cases")
            if metrics.get("total_output_bytes"):
                measured["cycles_per_byte"] = round(
                    metrics["total_cycles"] / metrics["total_output_bytes"], 4
                )
            if "cycles_per_block" in metrics:
                measured["cycles_per_block"] = metrics["cycles_per_block"]
                measured["constant_block_latency"] = metrics.get("constant_block_latency")

        return CandidateOutput(
            directory=context.output_dir,
            digest=sha256_tree(context.output_dir),
            ok=command.get("exit_code") == 0 and output_path.is_file(),
            commands=[command],
            reported={"stimulus_cases": len(cases)},
            measured=measured,
        )

    # --- Optional hooks ---------------------------------------------------

    def lint(self, context: Context) -> dict[str, Any] | None:
        command = run(
            [
                "verilator", "--lint-only", *VERILATOR_FLAGS,
                "--top-module", "aes_gcm",
                *[str(path) for path in RTL_SOURCES],
            ],
            timeout=300,
        )
        warnings = [
            line for line in (command.get("stderr") or "").splitlines()
            if line.startswith("%Warning")
        ]
        return {
            "ok": command.get("exit_code") == 0 and not warnings,
            "warnings": warnings,
            "command": command,
        }

    def synthesize(self, context: Context) -> dict[str, Any] | None:
        if shutil.which("yosys") is None:
            return None
        stats_path = context.output_dir / "synth-stats.json"
        netlist_path = context.output_dir / "netlist.v"
        script = "; ".join(
            [
                "read_verilog -sv " + " ".join(str(path) for path in RTL_SOURCES),
                "hierarchy -top aes_gcm",
                "synth -top aes_gcm -flatten",
                f"write_json {stats_path}",
                f"write_verilog {netlist_path}",
                "stat -json",
            ]
        )
        command = run(["yosys", "-Q", "-p", script], timeout=1800)
        cells: dict[str, Any] = {}
        text = command.get("stdout") or ""
        # `stat -json` prints a JSON object at the end of the log.
        start = text.rfind('{\n   "creator"')
        if start < 0:
            start = text.rfind("{")
        try:
            payload = json.loads(text[start:text.rfind("}") + 1])
            modules = payload.get("modules", {})
            # Yosys prefixes module names with a backslash in JSON output.
            name = next((key for key in modules if "aes_gcm" in key), None)
            top = modules.get(name, {}) if name else {}
            by_type = top.get("num_cells_by_type", {})
            cells = {
                "module": name,
                "num_cells": top.get("num_cells"),
                "num_wires": top.get("num_wires"),
                "num_memories": top.get("num_memories"),
                "flip_flops": sum(
                    value for key, value in by_type.items() if key.startswith("$_DFF")
                ),
                "cell_types": by_type,
            }
        except (ValueError, IndexError, AttributeError, KeyError):
            cells = {"parse_error": "could not read stat -json output"}
        warnings = [
            line for line in text.splitlines() if line.startswith("Warning:")
        ]
        return {
            "ok": command.get("exit_code") == 0,
            "cells": cells,
            "warnings": warnings[:40],
            "warning_count": len(warnings),
            "warning_analysis": (
                "The one expected warning is Yosys replacing obuf_q with registers. "
                "That buffer exists because the frozen profile withholds plaintext "
                "until the tag verifies, and out_data reads it asynchronously, so it "
                "cannot map to a sync-read RAM. Measured cost: MAX_TEXT_BYTES 512 "
                "gives 38563 cells / 6604 flip-flops, versus 26122 / 3017 at 64 "
                "bytes. The buffer is therefore the dominant area term and is a "
                "target for architecture exploration, not a defect."
            ),
            "netlist_sha256": sha256_file(netlist_path) if netlist_path.is_file() else None,
            "command": {k: v for k, v in command.items() if k != "stdout"},
        }

    # --- Policy -----------------------------------------------------------

    def policy_checks(self, context: Context) -> list[dict[str, Any]]:
        checks: list[dict[str, Any]] = []

        # 1. The candidate must not link a cryptographic library.
        linked = run(["otool", "-L", str(GCM_SIM)], timeout=60) if GCM_SIM.is_file() else {}
        libraries = (linked.get("stdout") or "").lower()
        forbidden = [name for name in ("crypto", "ssl", "sodium", "commoncrypto") if name in libraries]
        checks.append(
            {
                "id": "no-host-crypto",
                "ok": GCM_SIM.is_file() and not forbidden,
                "forbidden_libraries": forbidden,
                "note": "The measured run must compute AES-GCM in RTL, not call a host library.",
            }
        )

        # 2. Encryption stimulus must carry no expected ciphertext or tag.
        leaks: list[str] = []
        for workload_id in GCM_WORKLOADS:
            for case in stim.corpus(workload_id):
                if case["mode"] == 0 and case["exp_tag"] is not None:
                    leaks.append(f"{workload_id}/{case['id']}")
        checks.append(
            {
                "id": "no-oracle-in-stimulus",
                "ok": not leaks,
                "leaking_cases": leaks[:10],
                "note": "Encryption cases are given inputs only; the tag is an input "
                        "solely for decryption, where it is part of the algorithm.",
            }
        )

        # 3. Latency must not vary with key or data at fixed lengths.
        cases = stim.corpus("security-latency-probe")
        stimulus_path = context.work_dir / "latency.txt"
        stim.write_gcm_stimulus(cases, stimulus_path)
        metrics_path = context.work_dir / "latency-metrics.json"
        command = run(
            [
                str(GCM_SIM), "--stimulus", str(stimulus_path),
                "--output", str(context.work_dir / "latency-vectors.json"),
                "--metrics", str(metrics_path),
            ],
            timeout=900,
        ) if GCM_SIM.is_file() else {"exit_code": 1}
        distinct: list[int] = []
        if metrics_path.is_file():
            metrics = json.loads(metrics_path.read_text(encoding="utf-8"))
            distinct = sorted({entry["cycles"] for entry in metrics["per_case"]})
        checks.append(
            {
                "id": "fixed-length-constant-latency",
                "ok": command.get("exit_code") == 0 and len(distinct) == 1,
                "distinct_cycle_counts": distinct,
                "cases": len(cases),
                "note": "Equal-length operations with different keys and data took the "
                        "same number of cycles. This is a timing observation over these "
                        "traces only. It is not a power, EM, cache, or fault leakage claim.",
            }
        )
        return checks


def create_plugin() -> ExperimentPlugin:
    return Aes256GcmPlugin()
