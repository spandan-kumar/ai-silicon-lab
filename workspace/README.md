# Simulation-complete Doom computer

The final candidate is a synthesizable RV32IMC SoC built around the pinned
OpenHW CV32E40P core. A bare-metal DoomGeneric firmware image boots from reset
and renders Freedoom entirely as instructions executed by cycle-accurate RTL
simulation. The host harness supplies deterministic dual-port external SRAM
and captures the CPU-written framebuffer; it contains no ISA emulator, Doom
engine, renderer, or oracle.

Build all candidate artifacts and run architectural bring-up checks with:

```sh
make -C workspace candidate
```

Run the authoritative protected benchmark with:

```sh
./lab/evaluate --run-id simulation-complete-final
```

The architecture and memory map are in `docs/ARCHITECTURE.md`; measured
canonical, strengthened-workload, trace, synthesis, and hash evidence is in
`docs/EVIDENCE.md`; the complete decision history is in
`docs/EXPERIMENT_LOG.md`.

The final candidate uses `rtl_cv/`, `sim_cv/`, `firmware/doom/`, the vendored
engine under `software/doomgeneric/`, and the licensed WAD under `assets/`.
The earlier PicoRV32 design under `rtl/` and `sim/` is retained as reviewable
experimental evidence but is not selected by `candidate.json`.
