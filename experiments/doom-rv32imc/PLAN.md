# Experiment plan: Doom-capable computer

## Question

Can an autonomous hardware-design agent create a real computer architecture
that executes Doom, first in cycle-accurate RTL simulation and later on a
physical target? The experiment is about the hardware/software boundary and
the measured design tradeoffs, not about reproducing a screenshot by any
means available.

The current CV32E40P/RV32IMC design is a verified baseline. It is valuable
because it supplies a real machine, firmware, memory-mapped interfaces,
cycle-accurate execution, and an exact visual oracle. It is not the universal
answer, a claim of full commercial Doom compatibility, or a physical result.

## Claims and non-claims

The strongest simulation claim is:

> For a named RTL commit, firmware image, Freedoom asset, input schedule,
> simulator/toolchain configuration, and workload revision, the candidate
> machine boots and executes the Doom program and produces exactly the trusted
> frames.

This does not automatically claim:

- real-time performance;
- sound, networking, save-game, or complete campaign support;
- physical timing, FPGA fit, power, or side-channel behavior;
- that the host harness did not contain an accidental shortcut unless the
  candidate boundary and harness inspection support that claim.

## Baseline and immutable boundary

The current baseline is selected by `workspace/candidate.json` and uses:

- `workspace/rtl_cv/` for the synthesizable CV32E40P-based SoC;
- `workspace/firmware/doom/` for the RV32IMC bare-metal image;
- `workspace/sim_cv/` for the Verilator model and capture harness;
- `workspace/software/doomgeneric/` for the declared engine source;
- `workspace/assets/freedoom1.wad` for the redistributable game data;
- `ground_truth/` for the protected reference, inputs, and oracle.

The protected canonical evaluator and supplemental oracle generator are
services, not candidate inputs that the candidate may inspect. A future
variant may replace any design component, but it must keep the same declared
workload when claiming a fair comparison and must create a new manifest when
the workload or output contract changes.

## Workload ladder

The ladder separates fast debugging from claims of broad correctness:

1. **RTL unit/bring-up:** reset, counter, RAM, bus transactions, MMIO writes,
   framebuffer packing, and deterministic repeated execution.
2. **Canonical gate:** the protected 64-frame warmup plus 120 exact 320x200
   RGB888 frames from Freedoom Phase 1 E1M1.
3. **Strengthened suite:** idle E1M1, movement/combat E1M1, alternate E1M2 at
   skill 3, and overlap-stress E1M3 at skill 4; 736 captured frames total.
4. **Extended coverage:** pinned Doom timedemos, additional maps, longer
   trajectories, or campaign transitions. Each new workload needs an
   independently generated oracle and a reason for inclusion.
5. **Performance run:** use a fixed timedemo or trace and measure cycles,
   retired instructions, memory traffic, and simulator wall time. Do not use
   concurrent wall times as a hardware-performance claim.

The first two levels should be cheap enough to run after most changes. The
strengthened suite is the simulation-complete functional gate. Extended
coverage and timedemos improve confidence and performance analysis but must
not replace the protected gate.

## Candidate boundary

The host is allowed to:

- load firmware, WAD data, and declared input events;
- model external memory and declared peripherals;
- clock the RTL and collect its output;
- store logs, traces, frames, and result metadata;
- compare output after the candidate exits.

The host must not:

- execute the Doom engine or an ISA emulator in place of the candidate CPU;
- read the trusted frame archive and feed expected frames back into the design;
- render frames and pass them off as framebuffer writes from RTL;
- alter input events, frame counts, oracle files, or the evaluator.

If a candidate intentionally chooses an accelerator or co-processor, document
exactly which work is performed in RTL and which is performed by firmware. A
CPU plus a hardware renderer is valid; a native host renderer with a decorative
RTL wrapper is not evidence for this experiment.

## Architecture exploration

The agent may investigate different CPUs, memories, bus protocols, caches,
accelerators, and software splits. To make comparisons meaningful:

- preserve a functional baseline before changing performance-critical logic;
- keep the same WAD, input events, framebuffer format, and output protocol;
- record compiler flags, linker layout, clock assumptions, and memory model;
- separate cold-start, warm-start, and steady-state measurements;
- report area and throughput together so an area-for-speed tradeoff is visible;
- retain rejected variants and explain whether they failed correctness, cost,
  resource, timing, or maintainability criteria.

Potential variants include an iterative CPU, a pipelined CPU, a custom
fixed-function rasterizer, a cache/memory redesign, a framebuffer blitter,
specialized fixed-point units, or a heterogeneous CPU/accelerator system. None
is required or preferred in advance.

## Simulation-complete gate

The design may claim this gate only when all of the following are true from a
clean committed revision:

- the candidate is synthesizable RTL and the chosen firmware executes on that
  RTL;
- reset, boot, Doom start, normal completion, and failure/trap signals are
  observed from the run;
- the canonical 120 frames match exactly;
- all 736 strengthened-suite frames match exactly;
- no frames are missing, extra, truncated, or silently substituted;
- repeated runs reproduce deterministic frame and trace identities;
- Verilator lint, generic synthesis, and relevant unit checks pass;
- synthesis warnings are investigated and documented;
- input, WAD, firmware, RTL, simulator, compiler, and result identities are
  recorded;
- a detached clean-worktree reproduction passes;
- host-side shortcuts have been ruled out by design inspection and harness
  boundaries.

The current baseline has passed this gate at the defined workload scope. A
future change must not inherit that status merely because it descends from the
same commit; it needs its own run evidence.

## Physical follow-up

When a board or ASIC flow becomes available, add a target profile rather than
changing the simulation contract. Freeze clock/reset, memory initialization,
video capture, input wiring, constraints, bitstream or netlist identity, and
measurement instrumentation. Compare hardware-visible frames or a hardware
checksum stream against the same RTL workload. A board that only runs a demo
image without a reproducible capture path is not enough for the final claim.

## Known edge cases

- Generated Verilator dependencies must work in the repository's space-bearing
  path and in detached worktrees.
- Temporary build paths must not become embedded in firmware or simulator
  identities.
- WAD and firmware changes require new hashes and oracle review.
- A simulator timeout is a failure, not evidence of slow success.
- Candidate-reported cycle counts are useful but remain untrusted unless the
  harness independently observes them.
- Generic synthesis may omit external RAM; report that boundary instead of
  pretending it is on-chip memory.
- An exact visual match validates the tested trajectory only; it does not
  prove untested game systems.
- A physical board may expose clock, reset, memory-init, or I/O bugs that RTL
  simulation cannot see.
