# Pinned sources and tool research

## Hardware and ISA

- OpenHW Group CV32E40P repository:
  <https://github.com/openhwgroup/cv32e40p>
  - pinned tag/revision: `cv32e40p_v1.8.3` /
    `360d272898d81806be3377193870dbf83a3ea79f`
  - upstream synthesis guidance:
    <https://docs.openhwgroup.org/projects/cv32e40p-user-manual/en/latest/intro.html#synthesis-guidelines>
  - verified facts: four-stage in-order RV32IMC pipeline, independent OBI
    instruction/data interfaces, synthesizable ASIC/FPGA design, and required
    integrator-provided clock-gating cell
  - license: Solderpad Hardware License with the upstream Apache-2.0 option
- PicoRV32 repository: <https://github.com/YosysHQ/picorv32>
  - pinned revision: `a473fc8fca393771d83b0ffcf0b14db3393339d8`
  - verified facts: synthesizable RV32IM configurations, native valid/ready
    memory interface, optional fast multiply/divide, and retirement trace
  - license: ISC (`COPYING` and the notice in `picorv32.v`)
- RISC-V unprivileged ISA specification:
  <https://github.com/riscv/riscv-isa-manual>

## Software and data

- DoomGeneric repository: <https://github.com/ozkl/doomgeneric>
  - pinned revision: `dcb7a8dbc7a16ce3dda29382ac9aae9d77d21284`
  - candidate vendors this revision and does not compile from protected
    reference paths; `workspace/firmware/doom/SOURCE.json` records the narrow
    local renderer compatibility modification
  - license: GNU GPL v2
- Original Linux Doom renderer:
  <https://github.com/id-Software/DOOM/blob/master/linuxdoom-1.10/r_draw.c>
- Current Chocolate Doom renderer and masked-sprite path:
  <https://github.com/chocolate-doom/chocolate-doom/blob/master/src/doom/r_draw.c>
  and
  <https://github.com/chocolate-doom/chocolate-doom/blob/master/src/doom/r_things.c>
  - verified fact: both the original and compatibility-focused descendant
    retain the vanilla 128-byte column wrap without an allocation-bound check
  - measured candidate policy: preserve wrapped reads inside the owning sprite
    patch lump, but map a read beyond that allocation from palette index zero;
    this removes target/native allocator dependence without embedding pixels
- Freedoom repository: <https://github.com/freedoom/freedoom>
  - pinned lab asset: official `v0.13.0` Phase 1 build
  - WAD SHA-256:
    `7e3d5dbc1b11ed55c2c8aa44d4843ba1bb64780b4066f96898158d99b93fdf0f`
  - the candidate-owned copy, source metadata, and full license are under
    `workspace/assets/`; the protected copy remains the evaluator authority

## Toolchain

- xPack RISC-V Embedded GCC release:
  <https://github.com/xpack-dev-tools/riscv-none-elf-gcc-xpack/releases/tag/v14.2.0-3>
  - archive: `xpack-riscv-none-elf-gcc-14.2.0-3-darwin-arm64.tar.gz`
  - SHA-256:
    `e76e86b8c500f8e92b3b4ff7b0444cfbf3b218515f322929e0744ec3b9ed80a8`
  - measured compiler: GCC 14.2.0, binutils 2.43.1
  - measured multilib selection for both `-march=rv32imc -mabi=ilp32` and
    `-march=rv32im -mabi=ilp32`, including newlib
- Homebrew `riscv64-elf-gcc` formula:
  <https://github.com/Homebrew/homebrew-core/blob/HEAD/Formula/r/riscv64-elf-gcc.rb>
  - inspected 2026-08-27; it configures GCC with `--without-headers`, so it is
    not the libc-bearing target toolchain used here
- Verilator: <https://verilator.org/guide/latest/>
  - measured host version: 5.050
  - optimization guidance used here:
    <https://verilator.org/guide/latest/simulating.html#benchmarking-optimization>
  - measured changes include Verilator `-O3`, Clang `-O3 -march=native`, LTO,
    and removal of the simulation-only clock-gate model; exact output was
    rechecked after each change
- Yosys: <https://yosyshq.readthedocs.io/>
  - measured host version: 0.68+post
- sv2v: <https://github.com/zachjs/sv2v>
  - measured host version: 0.0.13 (Homebrew bottle)
  - all SystemVerilog inputs are converted together, with `SYNTHESIS` defined,
    before target-neutral Yosys synthesis

## Determinism finding

The protected adapter's 64-frame warmup is necessary. Two fresh native runs
capturing from frame zero produced different concatenated hashes; the exact
failed values and disposition are retained in `EXPERIMENT_LOG.md`. All
supplemental pixel oracles therefore preserve a 64-frame warmup. Boot/reset
determinism is checked at the RTL trace level instead.
