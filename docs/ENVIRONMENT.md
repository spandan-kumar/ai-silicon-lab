# Environment snapshot

Captured during laboratory setup on 2026-08-26 in Asia/Kolkata.

## Host

- OS: macOS 26.5.2, Darwin 25.5.0
- architecture: arm64
- hardware model: Mac16,12 / Apple M4
- CPU cores: 10
- memory: 16 GiB
- storage: 245.1 GB SSD; approximately 21 GiB free at capture time
- virtualization: Apple Hypervisor support detected; Docker Engine 29.4.0
  available through the `orbstack` context
- GPU: integrated Apple M4 GPU, 8 cores, Metal 4
- FPGA hardware: none detected on USB4/Thunderbolt during setup
- network: HTTPS and GitHub access worked; one GitHub release-asset path was
  reset, so the Freedoom asset was built from its official source tag

## Installed tools

| Tool | Version/observed path |
| --- | --- |
| Git | system Git; repository initialized on `main` |
| Clang | Apple Clang 17.0.0 |
| GCC | `/usr/bin/gcc` (Apple compiler alias) |
| Make | GNU Make 3.81 |
| Python | 3.14.6 at `/opt/homebrew/bin/python3` |
| Node/npm | v26.4.0 / 11.17.0 |
| Verilator | 5.050 |
| Yosys | 0.68+post |
| Docker | 29.4.0 client/server |
| Homebrew | 6.0.19 |

## Not installed/detected

No Icarus Verilog, GTKWave, nextpnr, OpenLane, OpenROAD, vendor FPGA tools,
QEMU system binaries, RISC-V GCC, ARM embedded GCC, Rust toolchain, or
physically attached FPGA were detected. `./lab/status` reports these as
optional unavailable capabilities; it does not turn them into fake zeros or
successes.

The trusted machine-readable copy is `ground_truth/environment.json`.

