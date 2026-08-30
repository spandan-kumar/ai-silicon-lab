import argparse
import hashlib
import json
import tempfile
import time
import unittest
from pathlib import Path

import host


class FakeRegister:
    def __init__(self, value=0, on_read=None, on_write=None):
        self.value = value
        self.on_read = on_read
        self.on_write = on_write

    def read(self):
        return self.on_read() if self.on_read else self.value

    def write(self, value):
        self.value = value
        if self.on_write:
            self.on_write(value)


class FakeClient:
    def __init__(self, frames):
        self.memory = {}
        self.frames = frames
        self.frame_index = 0
        self.finished = False
        self.regs = argparse.Namespace()
        names = [
            "run", "memory_ready", "capture_ack", "frame_count", "frame_warmup",
            "input_count", "wad_size", "skill", "episode", "map",
            "simulation_frames", "game_tics", "captured_frames", "exit_code",
            "uart_last", "uart_count", "execution_cycles", "capture_pause_cycles",
        ]
        for name in names:
            setattr(self.regs, f"aisl_control_{name}", FakeRegister())
        self.regs.ddrctrl_init_done = FakeRegister(1)
        self.regs.ddrctrl_init_error = FakeRegister(0)
        self.regs.aisl_control_state = FakeRegister(on_read=self._state)
        self.regs.aisl_control_frame_index = FakeRegister(on_read=lambda: self.frame_index)
        self.regs.aisl_control_frame_address = FakeRegister(on_read=lambda: 0x0100_0000)
        self.regs.aisl_control_capture_ack.on_write = self._ack
        self.regs.aisl_control_simulation_frames.value = 66
        self.regs.aisl_control_game_tics.value = 17
        self.regs.aisl_control_exit_code.value = 0
        self.regs.aisl_control_execution_cycles.value = 123456
        self.regs.aisl_control_capture_pause_cycles.value = 789
        self._install_frame(0)

    def _state(self):
        base = host.STATE_BOOTED | host.STATE_DOOM_STARTED
        return base | (host.STATE_FINISHED if self.finished else host.STATE_CAPTURE_PENDING)

    def _install_frame(self, index):
        for offset, word in enumerate(self.frames[index]):
            self.memory[host.MAIN_RAM_BASE + 0x0100_0000 + offset * 4] = word

    def _ack(self, _value):
        self.frame_index += 1
        self.regs.aisl_control_captured_frames.value = self.frame_index
        if self.frame_index == len(self.frames):
            self.finished = True
        else:
            self._install_frame(self.frame_index)

    def write(self, address, values, burst="incr"):
        for offset, value in enumerate(values):
            self.memory[address + offset * 4] = value

    def read(self, address, length=None, burst="incr"):
        count = 1 if length is None else length
        values = [self.memory.get(address + offset * 4, 0) for offset in range(count)]
        return values[0] if length is None else values


class HostTests(unittest.TestCase):
    def test_input_encoding_matches_declared_little_endian_abi(self):
        records, count = host.encode_input_events("0 UP 1\n0 up 0\n# ignored\n12 0xa3 1\n")
        self.assertEqual(count, 3)
        self.assertEqual(
            records.hex(),
            "00000000ad00000001000000"
            "00000000ad00000000000000"
            "0c000000a300000001000000",
        )

    def test_input_tics_must_not_decrease(self):
        with self.assertRaisesRegex(ValueError, "decrease"):
            host.encode_input_events("2 fire 1\n1 fire 0\n")

    def test_ddr_failure_is_rejected_before_loading(self):
        client = FakeClient([[0]])
        client.regs.ddrctrl_init_error.value = 1
        with self.assertRaisesRegex(RuntimeError, "LiteDRAM"):
            host.wait_for_ddr(client, time.monotonic() + 1.0, 0.0)

    def test_run_loads_readbacks_captures_and_reports(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            firmware = root / "doom.bin"
            wad = root / "freedoom1.wad"
            inputs = root / "input.events"
            csr_csv = root / "csr.csv"
            bitstream = root / "target.bit"
            frames_dir = root / "frames"
            result = root / "result.json"
            firmware.write_bytes(b"\x13\x00\x00\x00\x01")
            wad.write_bytes(b"IWAD" + bytes(20))
            inputs.write_text("0 fire 1\n1 fire 0\n", encoding="utf-8")
            csr_csv.write_text("test\n", encoding="utf-8")
            bitstream.write_bytes(b"bitstream")
            client = FakeClient(
                [
                    [0x00112233, 0x00A0B0C0],
                    [0x00FFEEDD, 0x00010203],
                ]
            )
            args = argparse.Namespace(
                firmware=firmware,
                wad=wad,
                inputs=inputs,
                frames_dir=frames_dir,
                result=result,
                csr_csv=csr_csv,
                bitstream=bitstream,
                width=2,
                height=1,
                frame_count=2,
                warmup=64,
                skill=1,
                episode=1,
                map=1,
                timeout=1.0,
                poll_interval=0.0,
                chunk_words=2,
                verify_load=True,
            )
            report = host.run_workload(client, args)
            result.write_text(json.dumps(report), encoding="utf-8")

            self.assertTrue(report["success"])
            self.assertEqual(report["ddr"], {"init_done": 1, "init_error": 0})
            self.assertEqual(report["status"]["execution_cycles"], 123456)
            self.assertTrue(all(load["readback_verified"] for load in report["loads"]))
            self.assertEqual((frames_dir / "frame-000000.rgb").read_bytes(), bytes.fromhex("112233a0b0c0"))
            self.assertEqual((frames_dir / "frame-000001.rgb").read_bytes(), bytes.fromhex("ffeedd010203"))
            self.assertEqual(
                report["hashes"]["frame_archive_sha256"],
                hashlib.sha256(bytes.fromhex("112233a0b0c0ffeedd010203")).hexdigest(),
            )
            self.assertEqual(len(report["artifacts"]["frames"]), 2)


if __name__ == "__main__":
    unittest.main()
