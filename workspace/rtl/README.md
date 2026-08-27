# AI Silicon Lab RTL

`aisl_soc.v` is a synthesizable RV32IM SoC wrapper around the pinned upstream
[YosysHQ PicoRV32](https://github.com/YosysHQ/picorv32/tree/a473fc8fca393771d83b0ffcf0b14db3393339d8)
core. The exact source revision, file hashes, and ISC license are preserved in
`vendor/picorv32/`.

The core configuration is deliberately fixed for the Doom workload:

- RV32I registers and 64-bit `cycle`/`instret` counters;
- 32-bit instructions (`COMPRESSED_ISA=0`), selected by measured Doom cycles;
- single-cycle barrel shifter (`BARREL_SHIFTER=1`);
- fast multiply and iterative divide (`ENABLE_FAST_MUL=1`, `ENABLE_DIV=1`);
- native PicoRV32 trace and synthesizable RVFI retirement trace;
- reset PC `0x00000000`, initial stack pointer `0x01fff000` (below the WAD).

The register file does not rely on Verilog initial-state synthesis
(`REGS_INIT_ZERO=0`); firmware is responsible for initializing every register
and memory object it uses.

## External memory interface

Addresses `0x00000000` through `0x03ffffff` are routed to the external native
PicoRV32 valid/ready bus. It is a 64 MiB byte-addressed memory window. The SoC
does not infer an internal 64 MiB array. `mem_valid` and all request fields stay
stable until `mem_ready`; reads return the aligned 32-bit word in `mem_rdata`,
and writes use byte enables in `mem_wstrb`.

The integration memory layout is:

| Address | Content |
| --- | --- |
| `0x00000000` | flat firmware image and runtime memory |
| `0x02000000` | WAD bytes |
| `0x03c00000` | input records, each three little-endian `uint32_t` words: `{tic, keycode, pressed}` |

## MMIO ABI

All registers are 32-bit and based at `0x10000000`. `RW`, `RO`, and `WO` are
from the firmware's perspective.

| Offset | Access | Meaning |
| --- | --- | --- |
| `+0x00` | WO | UART byte in bits 7:0; pulses `uart_tx_valid` |
| `+0x04` | WO | control/event command; pulses `event_valid` |
| `+0x08` | RW | 32-bit RGB framebuffer base address |
| `+0x0c` | RW | zero-based output frame index |
| `+0x10` | RO | required output frame count |
| `+0x14` | RO | warmup frame count |
| `+0x18` | RO | input-record count |
| `+0x1c` | RO | WAD byte size |
| `+0x20` | RO | Doom skill |
| `+0x24` | RO | Doom episode |
| `+0x28` | RO | Doom map |
| `+0x2c` | - | reserved; reads zero |
| `+0x30` | WO | firmware-reported simulated frame count |
| `+0x34` | WO | firmware-reported game tic count |
| `+0x38` | WO | firmware-reported captured frame count |
| `+0x3c` | WO | firmware exit code |

Control commands are values, not bit fields: `1` means booted, `2` means Doom
started, `3` requests capture using the current frame address/index, `4` means
finished, and `0x0000dead` means failed. Status outputs latch until cold reset;
UART, event, and frame-capture valid outputs are one-clock pulses.

The framebuffer contains one little-endian `0x00RRGGBB` word per pixel in row
major order. Firmware must only issue command `3` after all stores for that
frame have completed.

## Synthesis

From the repository root:

```sh
make -C workspace/rtl synth
```

This performs a generic Yosys synthesis and writes the full report under
`workspace/rtl/build/`.
