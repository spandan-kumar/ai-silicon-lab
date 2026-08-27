# Toolchain bootstrap

The measured host uses xPack GNU RISC-V Embedded GCC 14.2.0-3 because its
`rv32imc/ilp32` multilib includes newlib. Homebrew's `riscv64-elf-gcc` formula
is built `--without-headers` and is therefore insufficient for the Doom port.

`bootstrap-riscv-toolchain` downloads the official Darwin arm64 archive into
the ignored `.aisl/` cache and verifies its pinned SHA-256 before extraction.
It never downloads during evaluation unless invoked explicitly.

`riscv-prefix` resolves, in order, an explicit `RISCV_PREFIX`, an installed
`riscv-none-elf-gcc`, or the pinned cache associated with Git's common
directory. The common-directory lookup lets `lab/reproduce` worktrees reuse
the same verified toolchain without embedding a machine-specific absolute
path in tracked build files.
