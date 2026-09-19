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

Exploratory `ARCH=11–14` also test overlapping authentication of the current
ciphertext with its AES counter block during decryption. `ARCH=13` combines
both encrypt and decrypt schedules; `ARCH=14` adds Karatsuba GHASH. Preliminary
measurements are retained in `reports/dual_overlap_pre_hardening.json` and are
superseded for security and implementation recommendations: a subsequent
review found and fixed raw output-port exposures described in `SECURITY.md`.
The clean, hardened five-configuration comparison is retained in
`reports/dual_overlap_hardened.json`; it supersedes the preliminary ranking.
Use `tools/evaluate_exploration.py --help` to reproduce selected architectures
with retained command logs, source snapshots, repeatability and mapped checks.

The masked S-box follow-up, `reports/masked_sbox_schedule_study.json`, reports
exact register-cost scheduling for nine public circuits. None of the eight
29-AND circuits beats the equally optimized classic circuit in both mapped
area and delay; their lower random-bit count remains a separate tradeoff.
The retained run record is `runs/aes-masked-schedule-20260918/run.json`.

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

### Scheduled masked S-box reproduction

From `workspace/aes-256-gcm`, after obtaining the pinned sources/library with
the existing `make masked-sbox-study` flow:

```sh
python3 -m venv build/schedule-venv
build/schedule-venv/bin/pip install -r tools/requirements-hpc2-schedule.txt
build/schedule-venv/bin/python tools/optimize_masked_sbox_schedule.py \
  --source build/masked-sbox-study/sources/aes-sbox-fwd-a29-ad5-g161-gd24-xx132-1.ncff.txt \
  --gates 161 --output build/scheduled-candidate --seconds 60
python3 tools/measure_scheduled_sbox.py \
  --schedule build/scheduled-candidate/schedule.json \
  --output-dir build/scheduled-candidate-mapping
python3 tools/verify_scheduled_sbox.py \
  --schedule build/scheduled-candidate/schedule.json \
  --circuit a29-ad5-g161-d24 \
  --fullverif-root build/research-tools/fullverif \
  --output-dir build/scheduled-candidate-fullverif
```

The last command requires a built fullVerif checkout at the revision recorded
in the report. Each output directory must be new. The solver environment was
tested with Python 3.13.5 and OR-Tools 9.14.6206. Source hashes, schedule
dependencies, emitted RTL identity, and the pinned Liberty hash are checked
before measurement. `--source` permits a relocated, hash-identical SLP archive.
The optimizer minimizes alignment-register bits, not mapped area or delay.
Composition verification assumes the library's HPC2 security contract and
does not prove leakage security of the mapped netlist.
