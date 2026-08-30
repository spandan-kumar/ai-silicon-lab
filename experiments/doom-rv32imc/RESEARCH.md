# DOOM computer research record

This is the source record for Experiment 001. The protected evaluator and
ground truth in `lab/` and `ground_truth/` remain the authoritative local
correctness boundary; these links provide external context and versioned
references, not permission to weaken that boundary.

Research date: 2026-08-29

Physical-target research update: 2026-08-30

## Primary sources

- [id Software DOOM source repository](https://github.com/id-Software/DOOM)
  provides the historical source context for the game. The experiment's
  shipped workload and assets are still governed by the repository's pinned
  local oracle and evaluator, so a source-tree comparison alone is not a
  passing result.
- [Verilator user guide — overview](https://verilator.org/guide/latest/overview.html)
  documents the cycle-based Verilog/SystemVerilog simulation model used by the
  current host flow. Tool version and invocation are recorded with each run;
  simulation speed is not treated as hardware performance.
- [OrangeCrab r0.2 hardware documentation](https://github.com/orangecrab-fpga/orangecrab-hardware/blob/main/documentation/hugo-files/content/docs/r0.2.md)
  identifies the ECP5 device options, 128 MiB DDR3L, 48 MHz oscillator, and
  USB DFU interface used by the physical target profile.
- [nextpnr](https://github.com/YosysHQ/nextpnr) and
  [Project Trellis](https://github.com/YosysHQ/prjtrellis) document the open
  ECP5 place-and-route and bitstream flow selected for strict target timing.
- [LiteDRAM](https://github.com/enjoy-digital/litedram) supplies the ECP5 DDR3
  PHY/controller and BIOS training/memory-test path. The target exposes its
  BIOS-written initialization result to the host rather than assuming DDR is
  usable after configuration.
- [LiteX boards](https://github.com/litex-hub/litex-boards) supplies the pinned
  OrangeCrab r0.2 pin, clock, DDR, and DFU definitions used by the target.

## Local evidence boundary

- `./lab/status` is the capability and protected-state inventory.
- `./lab/evaluate` is the canonical Doom benchmark.
- `ground_truth/` contains protected reference material and must not be
  changed to make a candidate pass.
- Supplemental workloads may increase coverage, but they cannot replace the
  canonical evaluator or silently change its expected outputs.

## Research rules for this experiment

- Record the exact DOOM source/assets revision when changing the workload or
  interpreting a result.
- Distinguish cycle-accurate simulation results, host-wall-clock results,
  inferred architectural explanations, and unverified hypotheses.
- A visual frame match is evidence only when it is produced by the evaluator's
  comparison against its explicit oracle; screenshots or candidate-reported
  success are not sufficient.
