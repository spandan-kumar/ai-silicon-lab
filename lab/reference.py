#!/usr/bin/env python3
"""Run the trusted headless DOOM reference with a controlled framebuffer."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import subprocess
import sys


ROOT = Path(__file__).resolve().parents[1]
BENCHMARK = ROOT / "ground_truth" / "benchmark" / "benchmark.json"
PREBUILT = ROOT / "ground_truth" / "reference" / "bin" / "doomgeneric-headless"


def build_reference() -> Path:
    output = ROOT / ".aisl" / "reference-build" / "doomgeneric-headless"
    output.parent.mkdir(parents=True, exist_ok=True)
    completed = subprocess.run(
        ["make", "-C", str(ROOT / "ground_truth" / "reference"), f"OUTPUT={output}"],
        cwd=ROOT,
        check=False,
    )
    if completed.returncode != 0 or not output.is_file():
        raise SystemExit("reference build failed")
    return output


def main() -> int:
    benchmark = json.loads(BENCHMARK.read_text(encoding="utf-8"))
    parser = argparse.ArgumentParser(description="run the AI Silicon Lab reference")
    parser.add_argument("--output", required=True, help="directory for captured RGB frames")
    parser.add_argument("--input", default=str(ROOT / benchmark["input_file"]))
    parser.add_argument("--frames", type=int, default=int(benchmark["execution"]["capture_frames"]))
    parser.add_argument("--warmup", type=int, default=int(benchmark["execution"]["warmup_frames"]))
    parser.add_argument("--build", action="store_true", help="rebuild the portable reference binary")
    parser.add_argument("engine_args", nargs=argparse.REMAINDER)
    args = parser.parse_args()

    output = Path(args.output).expanduser().resolve()
    output.mkdir(parents=True, exist_ok=True)
    binary = build_reference() if args.build or not PREBUILT.is_file() else PREBUILT
    engine_args = list(args.engine_args)
    if engine_args and engine_args[0] == "--":
        engine_args = engine_args[1:]
    if not engine_args:
        engine_args = [
            "-iwad", str(ROOT / benchmark["asset"]),
            *[str(item) for item in benchmark["reference_args"]],
        ]

    result_file = output.parent / "reference-result.json"
    env = os.environ.copy()
    env.update(
        {
            "AISL_INPUT_FILE": str(Path(args.input).expanduser().resolve()),
            "AISL_FRAME_DIR": str(output),
            "AISL_RESULT_FILE": str(result_file),
            "AISL_FRAME_COUNT": str(args.frames),
            "AISL_FRAME_WARMUP": str(args.warmup),
            "AISL_FRAME_WIDTH": str(benchmark["video"]["width"]),
            "AISL_FRAME_HEIGHT": str(benchmark["video"]["height"]),
            "AISL_FRAME_FORMAT": str(benchmark["video"]["format"]),
        }
    )
    return subprocess.run([str(binary), *engine_args], cwd=ROOT, env=env, check=False).returncode


if __name__ == "__main__":
    raise SystemExit(main())
