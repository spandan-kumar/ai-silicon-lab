#!/usr/bin/env python3
"""Intentionally broken candidate used only to test evaluator rejection."""

import json
import os
from pathlib import Path


def main() -> int:
    frame_dir = Path(os.environ["AISL_FRAME_DIR"])
    result_file = Path(os.environ["AISL_RESULT_FILE"])
    count = int(os.environ["AISL_FRAME_COUNT"])
    width = int(os.environ["AISL_FRAME_WIDTH"])
    height = int(os.environ["AISL_FRAME_HEIGHT"])
    frame_dir.mkdir(parents=True, exist_ok=True)
    blank = bytes(width * height * 3)
    for index in range(count):
        (frame_dir / f"frame-{index:06d}.rgb").write_bytes(blank)
    print("AISL_BOOTED")
    print("AISL_DOOM_STARTED")
    result_file.write_text(
        json.dumps({"booted": True, "doom_started": True, "frames": count}) + "\n",
        encoding="utf-8",
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
