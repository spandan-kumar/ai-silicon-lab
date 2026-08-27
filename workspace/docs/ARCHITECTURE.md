# AI Silicon Lab computer architecture

## Decision

The simulation-complete computer is a custom SoC around the synthesizable
OpenHW Group CV32E40P core, configured without optional PULP or floating-point
extensions and executing RV32IMC firmware. The CPU, deterministic OBI memory
bridge, and SoC/MMIO decode are synthesizable SystemVerilog. Verilator
evaluates that RTL on every clock edge; there is no instruction-set emulator
and no host Doom engine in the candidate.

The selected upstream core is tag `cv32e40p_v1.8.3`, revision
`360d272898d81806be3377193870dbf83a3ea79f`, under its Solderpad/Apache-2.0
license. Selection was empirical. PicoRV32 first established correctness and
produced the complete byte-identical protected frame stream, but measured
about 400 seconds for the official workload. On an identical 19,313,265-
instruction benchmark, the CV32E40P integration reduced architectural cycles
by about 65 percent and host wall time by about 30 percent. The final
CV32E40P/RV32IMC/LTO Doom run then satisfied the real gate: all 120 protected
frames were exact after 744,664,922 cycles and 581,003,386 retired
instructions, with a measured 259.33-second simulator wall interval.

## Hardware and testbench boundary

Synthesizable RTL contains:

- the RV32IMC CPU and deterministic diagnostic retirement projection;
- external-memory request/response wiring;
- address decode and MMIO configuration/status registers;
- UART, boot, Doom-start, frame-capture, finish, and failure event outputs; and
- firmware-visible performance/status registers.

The Verilator testbench supplies deterministic external SRAM and pins. It
preloads a firmware image, the legally redistributable WAD, and parsed input
events; clocks/reset the RTL; services valid/ready transfers; captures the
CPU-written framebuffer only after a hardware MMIO event; and records outputs.
It does not render pixels, read an oracle, or execute reference/engine code.
Exact comparison is a separate post-process after simulation exits.

The external-memory design is deliberate: synthesizing 64 MiB as flip-flops
would not describe a realistic chip. The synthesis boundary is the SoC plus
its external SRAM interface; memory capacity is reported separately and never
misrepresented as on-chip BRAM.

## Address map

| Address/range | Direction | Meaning |
| --- | --- | --- |
| `0x00000000..0x01ffffff` | memory | firmware, data, 6 MiB Doom zone heap, stack |
| `0x02000000..` | memory | read-only preloaded Freedoom WAD |
| `0x03c00000..` | memory | 12-byte input records: LE `u32 tic,key,pressed` |
| `0x00000000..0x03ffffff` | bus | complete 64 MiB external-memory window |
| `0x10000000` | write | UART byte |
| `0x10000004` | write | control event: boot=1, Doom-start=2, capture=3, finish=4, fail=`0xdead` |
| `0x10000008` | read/write | framebuffer address |
| `0x1000000c` | read/write | capture frame index |
| `0x10000010` | read | requested capture-frame count |
| `0x10000014` | read | requested warmup-frame count |
| `0x10000018` | read | input-record count |
| `0x1000001c` | read | WAD byte size |
| `0x10000020` | read | skill argument |
| `0x10000024` | read | episode argument |
| `0x10000028` | read | map argument |
| `0x10000030` | write | simulated drawn-frame count |
| `0x10000034` | write | Doom game tic count |
| `0x10000038` | write | captured-frame count |
| `0x1000003c` | write | firmware exit code |

CPU reset begins at address zero. Startup assembly establishes the stack,
zeros `.bss`, initializes newlib, and calls the target adapter. A boot marker
is emitted only by firmware running on the RTL CPU.

## Proof obligations

Simulation-complete requires all of the following evidence, not merely a lab
pass:

1. reset/ISA/memory/MMIO tests execute in RTL and match explicit signatures;
2. the RV32 firmware ELF contains the pinned Doom engine and boots from reset;
3. the protected 64-warmup/120-capture benchmark is byte-identical;
4. supplemental idle, movement/combat, alternate map/skill, and overlapping-
   input stress workloads are byte-identical to twice-reproduced native-
   reference oracles;
5. repeated RTL runs have identical frame, trace, cycle, and end-state hashes;
6. logs, bounded traces, sampled retirement-stream digests, cycle/retire counts,
   firmware/map/disassembly, and file hashes are retained;
7. Yosys successfully synthesizes the exact RTL configuration and records
   machine-readable cell statistics/netlist hashes; and
8. the committed candidate passes `lab/evaluate` and `lab/reproduce` from a
   clean worktree.
