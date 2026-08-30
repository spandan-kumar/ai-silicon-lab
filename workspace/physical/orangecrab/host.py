#!/usr/bin/env python3
"""Load and capture the declared Doom workload through an OrangeCrab UARTBone."""

from __future__ import annotations

import argparse
import hashlib
import json
import struct
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable


REPOSITORY = Path(__file__).resolve().parents[3]
MAIN_RAM_BASE = 0x4000_0000
CV_MEMORY_BYTES = 64 * 1024 * 1024
WAD_ADDRESS = 0x0200_0000
INPUT_ADDRESS = 0x03C0_0000
DEFAULT_FIRMWARE = REPOSITORY / "workspace/firmware/doom/build-candidate/doom.bin"
DEFAULT_WAD = REPOSITORY / "workspace/assets/freedoom1.wad"
DEFAULT_CSR_CSV = Path(__file__).resolve().parent / "build/csr.csv"
DEFAULT_BITSTREAM = Path(__file__).resolve().parent / "build/gateware/gsd_orangecrab.bit"

STATE_BOOTED = 1 << 0
STATE_DOOM_STARTED = 1 << 1
STATE_FINISHED = 1 << 2
STATE_FAILED = 1 << 3
STATE_TRAP = 1 << 4
STATE_CAPTURE_PENDING = 1 << 5

NAMED_KEYS = {
    "right": 0xAE,
    "left": 0xAC,
    "up": 0xAD,
    "down": 0xAF,
    "strafe_left": 0xA0,
    "strafe_right": 0xA1,
    "use": 0xA2,
    "fire": 0xA3,
    "shift": 0xB6,
    "escape": 27,
    "enter": 13,
    "tab": 9,
    "space": 32,
}


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def reject_protected(path: Path, purpose: str) -> Path:
    resolved = path.expanduser().resolve()
    try:
        relative = resolved.relative_to(REPOSITORY)
    except ValueError:
        return resolved
    if relative.parts and relative.parts[0] in {"ground_truth", "lab"}:
        raise ValueError(f"{purpose} may not access protected repository path: {resolved}")
    return resolved


def parse_u32(text: str, description: str) -> int:
    try:
        value = int(text, 0)
    except ValueError as error:
        raise ValueError(f"invalid {description}: {text}") from error
    if not 0 <= value <= 0xFFFF_FFFF:
        raise ValueError(f"{description} is outside uint32_t: {text}")
    return value


def keycode_for(token: str) -> int:
    token = token.lower()
    if token in NAMED_KEYS:
        return NAMED_KEYS[token]
    if len(token) == 1 and ord(token) < 0x80:
        return ord(token)
    if token and token[0].isdigit():
        return parse_u32(token, "input keycode")
    raise ValueError(f"unknown input key token: {token}")


def encode_input_events(text: str) -> tuple[bytes, int]:
    records = bytearray()
    previous_tic: int | None = None
    count = 0
    for line_number, original_line in enumerate(text.splitlines(), start=1):
        line = original_line.split("#", 1)[0]
        fields = line.split()
        if not fields:
            continue
        if len(fields) != 3:
            raise ValueError(f"malformed input event at line {line_number}")
        tic = parse_u32(fields[0], f"input tic at line {line_number}")
        keycode = keycode_for(fields[1])
        pressed = parse_u32(fields[2], f"pressed flag at line {line_number}")
        if pressed > 1:
            raise ValueError(f"pressed flag must be 0 or 1 at line {line_number}")
        if previous_tic is not None and tic < previous_tic:
            raise ValueError(f"input tics decrease at line {line_number}")
        records.extend(struct.pack("<III", tic, keycode, pressed))
        previous_tic = tic
        count += 1
    if count > 4096:
        raise ValueError("input_count exceeds firmware limit of 4096")
    return bytes(records), count


def words_from_bytes(data: bytes) -> list[int]:
    padded = data + bytes((-len(data)) % 4)
    if not padded:
        return []
    return list(struct.unpack(f"<{len(padded) // 4}I", padded))


def bytes_from_words(words: Iterable[int], length: int | None = None) -> bytes:
    values = list(words)
    data = struct.pack(f"<{len(values)}I", *values) if values else b""
    return data if length is None else data[:length]


def write_region(client: Any, address: int, data: bytes, chunk_words: int) -> None:
    for offset in range(0, len(data), chunk_words * 4):
        chunk = data[offset : offset + chunk_words * 4]
        client.write(address + offset, words_from_bytes(chunk))


def read_region(client: Any, address: int, length: int, chunk_words: int) -> bytes:
    output = bytearray()
    total_words = (length + 3) // 4
    for word_offset in range(0, total_words, chunk_words):
        count = min(chunk_words, total_words - word_offset)
        words = client.read(address + word_offset * 4, length=count)
        output.extend(bytes_from_words(words))
    return bytes(output[:length])


def load_and_verify(
    client: Any,
    name: str,
    address: int,
    data: bytes,
    chunk_words: int,
    verify: bool,
) -> dict[str, Any]:
    write_region(client, MAIN_RAM_BASE + address, data, chunk_words)
    source_hash = sha256_bytes(data)
    result: dict[str, Any] = {
        "name": name,
        "cpu_address": f"0x{address:08x}",
        "physical_address": f"0x{MAIN_RAM_BASE + address:08x}",
        "bytes": len(data),
        "source_sha256": source_hash,
        "readback_sha256": None,
        "readback_verified": False,
    }
    if verify:
        readback = read_region(client, MAIN_RAM_BASE + address, len(data), chunk_words)
        readback_hash = sha256_bytes(readback)
        result["readback_sha256"] = readback_hash
        result["readback_verified"] = readback_hash == source_hash
        if not result["readback_verified"]:
            raise RuntimeError(f"{name} DDR readback hash mismatch")
    return result


def capture_rgb888(
    client: Any,
    cpu_address: int,
    width: int,
    height: int,
    chunk_words: int,
) -> bytes:
    pixels = width * height
    source_bytes = pixels * 4
    if cpu_address & 3:
        raise RuntimeError("framebuffer address is not word aligned")
    if source_bytes > CV_MEMORY_BYTES or cpu_address > CV_MEMORY_BYTES - source_bytes:
        raise RuntimeError("framebuffer lies outside the CV32E40P memory window")
    rgb = bytearray(pixels * 3)
    output_pixel = 0
    for word_offset in range(0, pixels, chunk_words):
        count = min(chunk_words, pixels - word_offset)
        words = client.read(MAIN_RAM_BASE + cpu_address + word_offset * 4, length=count)
        for value in words:
            rgb[output_pixel * 3] = (value >> 16) & 0xFF
            rgb[output_pixel * 3 + 1] = (value >> 8) & 0xFF
            rgb[output_pixel * 3 + 2] = value & 0xFF
            output_pixel += 1
    return bytes(rgb)


def named_register(client: Any, name: str) -> Any:
    try:
        return getattr(client.regs, name)
    except AttributeError as error:
        raise RuntimeError(f"CSR map lacks {name}") from error


def register(client: Any, name: str) -> Any:
    return named_register(client, f"aisl_control_{name}")


def read_status(client: Any) -> dict[str, int]:
    return {
        "state": register(client, "state").read(),
        "frame_address": register(client, "frame_address").read(),
        "frame_index": register(client, "frame_index").read(),
        "simulation_frames": register(client, "simulation_frames").read(),
        "game_tics": register(client, "game_tics").read(),
        "captured_frames": register(client, "captured_frames").read(),
        "exit_code": register(client, "exit_code").read(),
        "uart_last": register(client, "uart_last").read(),
        "uart_count": register(client, "uart_count").read(),
        "execution_cycles": register(client, "execution_cycles").read(),
        "capture_pause_cycles": register(client, "capture_pause_cycles").read(),
    }


def wait_for_ddr(client: Any, deadline: float, poll_interval: float) -> dict[str, int]:
    """Wait for the management BIOS to train and destructively test DDR."""

    while True:
        init_done = named_register(client, "ddrctrl_init_done").read()
        init_error = named_register(client, "ddrctrl_init_error").read()
        if init_done:
            if init_error:
                raise RuntimeError("LiteDRAM BIOS training or memory test failed")
            return {"init_done": init_done, "init_error": init_error}
        if time.monotonic() >= deadline:
            raise TimeoutError("timed out waiting for LiteDRAM BIOS initialization")
        time.sleep(poll_interval)


def run_workload(client: Any, args: argparse.Namespace) -> dict[str, Any]:
    firmware_path = reject_protected(args.firmware, "firmware")
    wad_path = reject_protected(args.wad, "WAD")
    input_path = reject_protected(args.inputs, "input schedule")
    frame_dir = reject_protected(args.frames_dir, "frame output")
    result_path = reject_protected(args.result, "result output")
    csr_csv = reject_protected(args.csr_csv, "CSR map")
    bitstream = reject_protected(args.bitstream, "bitstream")

    firmware = firmware_path.read_bytes()
    wad = wad_path.read_bytes()
    input_bytes = input_path.read_bytes()
    input_text = input_bytes.decode("utf-8")
    input_records, input_count = encode_input_events(input_text)
    if not firmware or len(firmware) > WAD_ADDRESS:
        raise ValueError("firmware is empty or overlaps the WAD window")
    if len(wad) < 12 or len(wad) > INPUT_ADDRESS - WAD_ADDRESS:
        raise ValueError("WAD size is outside the firmware memory window")
    if len(input_records) > CV_MEMORY_BYTES - INPUT_ADDRESS:
        raise ValueError("input records do not fit in the CV32E40P memory window")
    if args.width <= 0 or args.height <= 0 or args.frame_count <= 0:
        raise ValueError("width, height, and frame count must be positive")

    frame_dir.mkdir(parents=True, exist_ok=True)
    result_path.parent.mkdir(parents=True, exist_ok=True)
    for old_frame in frame_dir.glob("frame-*.rgb"):
        old_frame.unlink()

    started_utc = utc_now()
    started = time.monotonic()
    frame_archive_hash = hashlib.sha256()
    framed_stream_hash = hashlib.sha256()
    frames: list[dict[str, Any]] = []
    loads: list[dict[str, Any]] = []
    booted = False
    doom_started = False
    final_status: dict[str, int] = {}

    register(client, "run").write(0)
    register(client, "memory_ready").write(0)
    deadline = started + args.timeout
    ddr_status = wait_for_ddr(client, deadline, args.poll_interval)
    register(client, "frame_count").write(args.frame_count)
    register(client, "frame_warmup").write(args.warmup)
    register(client, "input_count").write(input_count)
    register(client, "wad_size").write(len(wad))
    register(client, "skill").write(args.skill)
    register(client, "episode").write(args.episode)
    register(client, "map").write(args.map)

    loads.append(load_and_verify(client, "firmware", 0, firmware, args.chunk_words, args.verify_load))
    loads.append(load_and_verify(client, "wad", WAD_ADDRESS, wad, args.chunk_words, args.verify_load))
    loads.append(
        load_and_verify(
            client,
            "input_records",
            INPUT_ADDRESS,
            input_records,
            args.chunk_words,
            args.verify_load,
        )
    )

    register(client, "memory_ready").write(1)
    register(client, "run").write(1)
    expected_index = 0
    last_captured_index: int | None = None

    while True:
        if time.monotonic() >= deadline:
            raise TimeoutError(f"physical workload exceeded {args.timeout:.1f}s timeout")
        state = register(client, "state").read()
        booted = booted or bool(state & STATE_BOOTED)
        doom_started = doom_started or bool(state & STATE_DOOM_STARTED)
        if state & STATE_TRAP:
            raise RuntimeError("CV32E40P trap asserted")
        if state & STATE_FAILED:
            raise RuntimeError("firmware failure asserted")

        if state & STATE_CAPTURE_PENDING:
            index = register(client, "frame_index").read()
            if index == last_captured_index:
                time.sleep(args.poll_interval)
                continue
            if index != expected_index or index >= args.frame_count:
                raise RuntimeError(f"non-sequential physical frame index {index}, expected {expected_index}")
            address = register(client, "frame_address").read()
            rgb = capture_rgb888(client, address, args.width, args.height, args.chunk_words)
            frame_path = frame_dir / f"frame-{index:06d}.rgb"
            frame_path.write_bytes(rgb)
            frame_hash = sha256_bytes(rgb)
            frame_archive_hash.update(rgb)
            framed_stream_hash.update(struct.pack("<I", index))
            framed_stream_hash.update(rgb)
            frames.append(
                {
                    "index": index,
                    "path": str(frame_path.resolve()),
                    "bytes": len(rgb),
                    "sha256": frame_hash,
                    "cpu_framebuffer_address": f"0x{address:08x}",
                }
            )
            last_captured_index = index
            expected_index += 1
            register(client, "capture_ack").write(1)
            continue

        if state & STATE_FINISHED:
            final_status = read_status(client)
            break
        time.sleep(args.poll_interval)

    success = (
        booted
        and doom_started
        and bool(final_status["state"] & STATE_FINISHED)
        and not bool(final_status["state"] & (STATE_FAILED | STATE_TRAP))
        and len(frames) == args.frame_count
        and final_status["captured_frames"] == args.frame_count
        and final_status["exit_code"] == 0
    )
    if not success:
        raise RuntimeError("physical terminal state did not satisfy the workload contract")

    return {
        "schema_version": 1,
        "success": True,
        "exit_reason": "finished",
        "started_utc": started_utc,
        "finished_utc": utc_now(),
        "physical_wall_seconds": time.monotonic() - started,
        "target": {
            "board": "OrangeCrab r0.2",
            "device": "LFE5U-85F-8MG285C",
            "system_clock_hz": 48_000_000,
            "main_ram_base": f"0x{MAIN_RAM_BASE:08x}",
            "cv_memory_bytes": CV_MEMORY_BYTES,
            "power_watts": None,
            "power_source": "unavailable: requires physical measurement instrumentation",
        },
        "workload": {
            "width": args.width,
            "height": args.height,
            "format": "rgb888",
            "capture_frames": args.frame_count,
            "warmup_frames": args.warmup,
            "skill": args.skill,
            "episode": args.episode,
            "map": args.map,
            "input_count": input_count,
        },
        "status": final_status,
        "observed": {"booted": booted, "doom_started": doom_started},
        "ddr": ddr_status,
        "loads": loads,
        "hashes": {
            "firmware_sha256": sha256_bytes(firmware),
            "wad_sha256": sha256_bytes(wad),
            "input_text_sha256": sha256_bytes(input_bytes),
            "input_records_sha256": sha256_bytes(input_records),
            # The archive digest is over raw frames in index order, matching
            # workspace/verification/oracle.py's exact-comparison archive.
            "frame_archive_sha256": frame_archive_hash.hexdigest(),
            "framed_stream_sha256": framed_stream_hash.hexdigest(),
            "bitstream_sha256": sha256_file(bitstream),
            "csr_csv_sha256": sha256_file(csr_csv),
        },
        "artifacts": {
            "firmware": str(firmware_path),
            "wad": str(wad_path),
            "input": str(input_path),
            "bitstream": str(bitstream),
            "csr_csv": str(csr_csv),
            "frames": frames,
        },
    }


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--host", default="localhost", help="litex_server host")
    parser.add_argument("--port", default=1234, type=int, help="litex_server TCP port")
    parser.add_argument("--csr-csv", type=Path, default=DEFAULT_CSR_CSV)
    parser.add_argument("--bitstream", type=Path, default=DEFAULT_BITSTREAM)
    parser.add_argument("--firmware", type=Path, default=DEFAULT_FIRMWARE)
    parser.add_argument("--wad", type=Path, default=DEFAULT_WAD)
    parser.add_argument("--inputs", type=Path, required=True)
    parser.add_argument("--frames-dir", type=Path, required=True)
    parser.add_argument("--result", type=Path, required=True)
    parser.add_argument("--width", type=int, default=320)
    parser.add_argument("--height", type=int, default=200)
    parser.add_argument("--frame-count", type=int, default=120)
    parser.add_argument("--warmup", type=int, default=64)
    parser.add_argument("--skill", type=int, default=1)
    parser.add_argument("--episode", type=int, default=1)
    parser.add_argument("--map", type=int, default=1)
    parser.add_argument("--timeout", type=float, default=3600.0)
    parser.add_argument("--poll-interval", type=float, default=0.01)
    parser.add_argument("--chunk-words", type=int, default=128)
    parser.add_argument(
        "--no-verify-load",
        dest="verify_load",
        action="store_false",
        help="skip full DDR readback (not suitable for final evidence)",
    )
    parser.set_defaults(verify_load=True)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    if args.chunk_words <= 0 or args.poll_interval < 0 or args.timeout <= 0:
        raise SystemExit("chunk-words and timeout must be positive; poll-interval cannot be negative")
    result_path = reject_protected(args.result, "result output")
    result_path.parent.mkdir(parents=True, exist_ok=True)

    try:
        from litex import RemoteClient
    except ImportError as error:
        raise SystemExit("LiteX is unavailable; run this through `make run ARGS=...`") from error

    client = RemoteClient(
        host=args.host,
        port=args.port,
        csr_csv=str(args.csr_csv.resolve()),
        timeout=10.0,
        raise_on_timeout=True,
    )
    client.open()
    try:
        result = run_workload(client, args)
    except Exception as error:
        failure = {
            "schema_version": 1,
            "success": False,
            "exit_reason": "host_error",
            "finished_utc": utc_now(),
            "error": str(error),
        }
        result_path.write_text(json.dumps(failure, indent=2) + "\n", encoding="utf-8")
        raise
    finally:
        try:
            register(client, "run").write(0)
        finally:
            client.close()

    result_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(
        json.dumps(
            {
                "success": True,
                "result": str(result_path),
                "frame_archive_sha256": result["hashes"]["frame_archive_sha256"],
            }
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
