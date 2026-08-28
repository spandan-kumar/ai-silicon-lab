# RV32IM/RV32IMC Doom firmware

This directory builds the pinned `ozkl/doomgeneric` engine as a bare-metal
RV32 ELF and flat image. Three renderer files carry one documented local
compatibility change: sprite columns record the bounds of their cached patch
lump, and a wrapped sample uses palette index zero only if it would leave that
allocation. This removes allocator- and architecture-dependent undefined
behavior while preserving vanilla reads elsewhere inside the lump and leaving
ordinary wrapping wall columns unchanged. Exact source provenance and the
modified-file list are in `SOURCE.json`.

The build links newlib and libm from the xPack GNU RISC-V Embedded GCC
14.2.0-3 multilib while supplying only the system-call surface required by
this headless workload.

Run:

```sh
make -C workspace/firmware/doom
```

The measured CV32E40P candidate configuration enables compressed instructions
and link-time optimization in an isolated build directory:

```sh
make -C workspace/firmware/doom -j8 \
  BUILD=build-candidate ARCH=rv32imc LTO_FLAGS=-flto
```

Set `CROSS_PREFIX=/path/to/riscv-none-elf-` when the toolchain is not on
`PATH` and the repository-local cache is unavailable.

The generated evidence is under the selected build directory: `doom.elf`,
`doom.bin`, `doom.map`, `doom.dis`, `doom.sections`, and `SHA256SUMS`. The link
fails if the image and heap overlap the reserved stack or if the stack reaches
the read-only WAD at `0x02000000`. DWARF compilation-directory paths are mapped
to the repository-relative `workspace/firmware/doom`, so debug-bearing ELF and
derived evidence hashes are stable across linked reproduction worktrees.

## Runtime contract

- Program, BSS, heap, and descending 1 MiB stack occupy addresses below
  `0x02000000`.
- `freedoom1.wad` is mapped read-only at `0x02000000`; its byte length is read
  from MMIO `0x1000001c`. The engine's patch parser assumes the pinned,
  hash-verified Freedoom WAD is structurally valid; the sprite sampling bound
  is a determinism fix, not a hostile-WAD parser sandbox.
- Parsed input starts at `0x03c00000`. Each little-endian record is three
  32-bit words: tic, translated Doom keycode, and pressed (zero or one). The
  record count is read from MMIO `0x10000018`.
- External RAM ends at `0x04000000`.
- The firmware publishes the address of the CPU-rendered 320x200
  little-endian `0x00RRGGBB` framebuffer and its index, then writes control
  code 3. The capture peripheral performs the protocol's mechanical RGB888
  byte packing (`R`, `G`, `B`); game rendering remains entirely in RTL-executed
  firmware.
- Control codes 1, 2, 3, 4, and `0xdead` mean booted, Doom started, capture,
  successful finish, and failure respectively.

The adapter intentionally mirrors the trusted headless workload's singletics,
fake tick, input polling, warmup-before-capture, and RGB conversion ordering.
The simulator supplies skill, episode, map, frame count, warmup, input count,
and WAD size through the documented MMIO registers.
