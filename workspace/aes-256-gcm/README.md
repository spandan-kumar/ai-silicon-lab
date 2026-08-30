# AES-256-GCM experiment workspace

This workspace implements the frozen `aes-256-gcm-64-v1` profile documented in
`experiments/aes-256-gcm/PROFILE.md`. It contains an independent Python oracle,
pinned NIST-derived and deterministic generated vectors, an OpenSSL software
baseline, two synthesizable RTL organizations, and an architecture-independent
cycle harness.

The implementation is intentionally separate from the protected Doom
evaluator.

The two candidates use the same 8-bit serialized ready/valid wrapper and cached
AES-256 round keys:

- `iterative-1r1b`: one AES round and one GHASH bit per cycle;
- `unrolled-2r8b`: two AES rounds and eight GHASH bits per cycle.

Both buffer decryption until a complete 128-bit tag succeeds. Neither RTL path
calls a host crypto implementation or reads an expected output; expected values
exist only in the C++ scoreboard.

## Reproduction

From the repository root:

```sh
make -C workspace/aes-256-gcm check
make -C workspace/aes-256-gcm synthesis
workspace/aes-256-gcm/evaluate --run-id aes-gcm-<unique-id>
```

`make check` regenerates and compares auditable headers, tests the Python and
OpenSSL layers, runs Verilator lint, executes primitive and full-GCM workloads,
and compares two complete deterministic simulation traces per organization.
`make synthesis` runs the identical generic Yosys flow on both candidates.
The evaluator requires a clean committed tree by default and retains phase
logs, hashes, exit codes, durations, and a schema-validated run record under
`runs/<run-id>/`.

`reports/results.json` is the retained Pareto report and
`reports/software_baseline.json` is the host-specific software measurement.
See `SECURITY.md` for the threat model and the exact boundary of the timing and
zeroization evidence.
