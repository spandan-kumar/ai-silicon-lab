# Deterministic cycle-accurate simulator

The Verilator harness in `sim_main.cpp` clocks the synthesizable `aisl_soc`
RTL; it is not an ISA emulator or host-side game engine. It cold-resets the
design, supplies one deterministic native-memory transaction at a time, and
stops with a non-zero status on a CPU trap, firmware fail event, protocol
error, malformed artifact, or cycle timeout.

The harness refuses to read any path that resolves beneath repository
`ground_truth/` or `lab/`. Normal runs must use a copied, legal WAD and the
evaluator-supplied `AISL_INPUT_FILE`; it never opens oracle frames or a
reference engine.

## Build and self-test

```sh
make -C workspace/sim lint
make -C workspace/sim
make -C workspace/sim test
```

The focused test boots a hand-encoded RV32IM flat binary containing
multiply/divide operations. It exercises every MMIO
status path needed by the evaluator, writes a two-pixel 32-bit framebuffer,
captures RGB888, and repeats the entire simulation to compare full-run hashes.

## Normal invocation

```sh
workspace/sim/build/aisl_sim \
  --firmware workspace/firmware/build/doom.bin \
  --wad workspace/assets/freedoom1.wad \
  --inputs /path/to/evaluator-supplied/input.events \
  --frames-dir /path/to/frames \
  --result /path/to/result.json \
  --width 320 --height 200 --frame-count 120 --warmup 64
```

The equivalent evaluator variables are `AISL_FIRMWARE_FILE`, `AISL_WAD_FILE`,
`AISL_INPUT_FILE`, `AISL_FRAME_DIR`, `AISL_RESULT_FILE`,
`AISL_FRAME_WIDTH`, `AISL_FRAME_HEIGHT`, `AISL_FRAME_COUNT`, and
`AISL_FRAME_WARMUP`. CLI options override the environment.

Firmware and WAD bytes load at `0x00000000` and `0x02000000`. Input lines are
parsed to 12-byte little-endian records at `0x03c00000`:

```text
uint32_t tic;
uint32_t keycode;
uint32_t pressed;
```

Single-character keys retain their ASCII values. Named tokens use the pinned
[doomgeneric `doomkeys.h`](https://github.com/ozkl/doomgeneric/blob/dcb7a8dbc7a16ce3dda29382ac9aae9d77d21284/doomgeneric/doomkeys.h)
values: `strafe_left=0xa0`, `strafe_right=0xa1`, `use=0xa2`, `fire=0xa3`,
`left=0xac`, `up=0xad`, `right=0xae`, and `down=0xaf`.

Each capture command reads `width*height` little-endian `0x00RRGGBB` words
from the firmware-selected framebuffer and emits tightly packed RGB888.
Indices must be unique, sequential, and in range. The default external SRAM
responds in the request cycle; `--memory-latency` adds an explicit,
deterministic number of full wait cycles for robustness tests.

The result records SHA-256 hashes for all inputs, 1,024-cycle full-state
checkpoints (plus every control event and trap), PicoRV32 native and RVFI
retirement traces, every frame, and UART output. The checkpoint stride is
explicit in the report and can be changed with `--cycle-trace-stride`.
Execution-trace hashing defaults to every event (a complete stream digest);
time-bounded evaluator runs may select a recorded sampling stride with
`--execution-trace-stride`. The report records both total events and hashed
samples. A bounded detailed RVFI prefix and the terminal retirement record
make both startup and failure locations inspectable.
