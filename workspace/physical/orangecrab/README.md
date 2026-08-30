# OrangeCrab physical Doom target

This target maps the verified synthesizable `aisl_soc_cv` computer onto an
OrangeCrab r0.2 with an ECP5-85F and 128 MiB DDR3L. Doom executes on the same
CV32E40P RTL and the same RV32IMC firmware used by the cycle-accurate
simulation. A small VexRiscv in integrated ROM is only a board-management
controller: it trains and tests DDR, then idles. It does not execute Doom,
render pixels, interpret the input schedule, or compare output.

The target implementation and strict place-and-route result are reproducible
without a board. They are not physical-execution evidence. The experiment's
physical gate remains open until a real board runs the declared workloads and
its captured frames compare exactly with the RTL/oracle evidence.

## Architecture and trust boundary

- Both CV32E40P OBI ports pass through synthesizable OBI-to-Wishbone bridges.
- CV addresses `0x00000000..0x03ffffff` map to OrangeCrab DDR addresses
  `0x40000000..0x43ffffff`.
- Firmware loads at CV address `0x00000000`, Freedoom at `0x02000000`, and
  encoded deterministic inputs at `0x03c00000`.
- The management BIOS writes LiteDRAM `init_done` and `init_error` CSRs only
  after PHY setup and a destructive memory test. The host refuses all DDR
  loads until `init_done=1` and `init_error=0`.
- The CV32E40P is held in reset while firmware, WAD, and inputs are loaded and
  read back in full. Their source and readback hashes are retained.
- At every RTL framebuffer-capture event, the CV memory ports pause while the
  host reads the stable 320x200 framebuffer. The host only converts the RTL's
  `0x00RRGGBB` words to tightly packed RGB888 and acknowledges the capture.
- The host never opens `lab/` or `ground_truth/`. Exact comparison is a
  separate post-run evaluator step.

## Reproducible build

The lock file pins every cloned source revision. On macOS, install the system
prerequisites first:

```sh
brew install cmake yosys prjtrellis dfu-util verilator
```

Then run from this directory:

```sh
make toolchain
make toolchain-check
make host-test test
make gateware
../../../.aisl/toolchains/orangecrab/venv/bin/python verify_build.py
```

`make gateware` stages all Make-sensitive inputs under a space-free, lock-hash
named directory in `/tmp`. It uses nextpnr seed 1 and strict 48 MHz timing;
timing failure is fatal. Generated build products are copied to `build/` and
are ignored by Git. The committed evidence directory records hashes and small
reports from repeated clean builds.

## Program and connect

Put the OrangeCrab DFU bootloader in programming mode, connect it by USB, and
run:

```sh
make program
```

The standard OrangeCrab LiteX platform uses DFU VID:PID `1209:5af0`, alternate
setting 0. Connect a 3.3 V USB-to-UART adapter to the Feather serial pins with
TX/RX crossed and a common ground, then start the host bridge:

```sh
PYTHONPATH="../../../.aisl/toolchains/orangecrab/src/migen:../../../.aisl/toolchains/orangecrab/src/litex" \
../../../.aisl/toolchains/orangecrab/venv/bin/python -m litex.tools.litex_server \
  --uart --uart-port /dev/cu.YOUR_ADAPTER --uart-baudrate 1000000
```

## Run and compare a declared workload

For the supplemental idle workload:

```sh
make run ARGS='\
  --inputs ../../../workspace/verification/inputs/idle.events \
  --frame-count 96 --warmup 64 --skill 1 --episode 1 --map 1 \
  --frames-dir ../../../.aisl/physical/idle-e1m1/frames \
  --result ../../../.aisl/physical/idle-e1m1/result.json'
```

Do not use `--no-verify-load` for evidence runs. After the hardware process
has exited, compare the captured files from the repository root:

```sh
python3 workspace/verification/oracle.py compare \
  idle-e1m1 .aisl/physical/idle-e1m1/frames
```

Repeat this process with each entry in `workspace/verification/workloads.json`.
For the protected canonical workload, the trusted evaluator must supply its
copied input schedule outside `ground_truth/`; the board host deliberately
rejects direct access to protected paths. Retain the host result JSON, server
and process logs, comparison JSON, exact commands and exit statuses, board and
adapter identity, bitstream/CSR hashes, and any measured power data. Power
must remain `null` when no external measurement exists.

## Sources

- [OrangeCrab r0.2 hardware documentation](https://github.com/orangecrab-fpga/orangecrab-hardware/blob/main/documentation/hugo-files/content/docs/r0.2.md)
- [nextpnr](https://github.com/YosysHQ/nextpnr)
- [Project Trellis](https://github.com/YosysHQ/prjtrellis)
- [LiteDRAM](https://github.com/enjoy-digital/litedram)
- [LiteX board definitions](https://github.com/litex-hub/litex-boards)
