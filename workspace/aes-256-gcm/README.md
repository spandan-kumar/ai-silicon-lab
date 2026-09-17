# AES-256-GCM experiment workspace

This workspace implements the frozen `aes-256-gcm-64-v1` profile documented in
`experiments/aes-256-gcm/PROFILE.md`. It contains an independent Python oracle,
pinned NIST-derived and deterministic generated vectors, an OpenSSL software
baseline, eight synthesizable RTL organizations, and an
architecture-independent cycle harness.

An additional exploratory `ARCH=8` branch (`karatsuba-1r2c`) implements a
two-stage Karatsuba GHASH multiplier. It is intentionally outside the frozen
eight-point Pareto sweep; reproduce it with the commands recorded in
`reports/karatsuba_exploration.json`.

Exploratory `ARCH=9` and `ARCH=10` branches overlap the next AES-CTR block
with the current payload GHASH multiply (`overlap-1r64b` and
`overlap-karatsuba-1r2c`). They are outside the frozen sweep; reproduce them
with `reports/overlap_exploration.json`.

The implementation is intentionally separate from the protected Doom
evaluator.

The candidates use the same 8-bit serialized ready/valid wrapper and cached
AES-256 round keys. The sweep independently varies one versus two AES rounds
per cycle and 1, 8, 16, 32, or 64 GHASH bits per cycle. Its named points are:

- `iterative-1r1b`: one AES round and one GHASH bit per cycle;
- `unrolled-2r8b`, `wide-2r16b`, and `ultrawide-2r32b`: two AES rounds
  with 8/16/32 GHASH bits per cycle; and
- `balanced-1r8b`, `balanced-wide-1r16b`,
  `balanced-ultrawide-1r32b`, and `balanced-xwide-1r64b`: one AES round
  with 8/16/32/64 GHASH bits per cycle.

AES forward and inverse S-boxes are generated from pinned NIST Circuit
Complexity Boolean straight-line programs and exhaustively checked over all
256 inputs in each direction.

Both buffer decryption until a complete 128-bit tag succeeds. Neither RTL path
calls a host crypto implementation or reads an expected output; expected values
exist only in the C++ scoreboard.

## Reproduction

From the repository root:

```sh
make -C workspace/aes-256-gcm check
make -C workspace/aes-256-gcm synthesis
make -C workspace/aes-256-gcm asic-synthesis gate-verify
make -C workspace/aes-256-gcm results
workspace/aes-256-gcm/evaluate --run-id aes-gcm-<unique-id>
```

`make check` regenerates and compares auditable headers, tests the Python and
OpenSSL layers, runs Verilator lint, executes primitive and full-GCM workloads,
and compares two complete deterministic simulation traces per organization.
`make synthesis` runs the identical generic Yosys flow on all candidates.
`make asic-synthesis` maps them to a pinned Nangate45 typical Liberty library
with explicit input-driver and output-load constraints. `make gate-verify`
executes the entire 1,038-operation GCM corpus against the selected mapped
standard-cell netlist. These are pre-layout synthesis results, not placed,
routed, or signoff timing claims.
The evaluator requires a clean committed tree by default and retains phase
logs, hashes, exit codes, durations, and a schema-validated run record under
`runs/<run-id>/`.

`reports/results.json` is the retained Pareto report and
`reports/software_baseline.json` is the host-specific software measurement.
See `SECURITY.md` for the threat model and the exact boundary of the timing and
zeroization evidence.
