# AES-256-GCM research record

This is a dated research record for Experiment 002. It identifies the sources
that define the primitive and the verification vocabulary; it is not a
certification claim. If a source changes or a successor publication becomes
normative, update this record and the experiment manifest before changing the
profile.

Research date: 2026-08-29

## Boolean S-box and technology-aware architecture sweep — 2026-08-31

- The clean retained evaluator run
  `aes-gcm-2ba718c-nangate45-breakthrough` passes at candidate commit
  `2ba718c926fb170c3223086c0cfa8b7f597c38ac`. It records separate precheck,
  build, simulation, and synthesis durations and hashes; the fresh synthesis
  phase took 1,541.114 seconds. All phase exit codes are zero.

- The original 2,048-bit lookup formulation was replaced by the NIST Circuit
  Complexity team's pinned forward `g113-a32-d27-ad6` and inverse
  `g121-a34-d21-ad4` AES S-box straight-line programs. The generator translates
  only `AND`, `XOR`, and `XNOR` gates and checks the declared gate counts. A new
  RTL harness exhaustively compares all 256 inputs in both directions before
  the existing key-schedule, primitive, and full-GCM tests run.
- Source revision `4e23832e62f490aeffd8770b1285d99056b5f8bf` and normalized file hashes
  are recorded in `workspace/aes-256-gcm/third_party/nist-circuits/SOURCE.md`.
  Primary sources are the [NIST circuit list](https://csrc.nist.gov/projects/circuit-complexity/list-of-circuits)
  and [NIST Circuits repository](https://github.com/usnistgov/Circuits).
- A Canright-style composite-field S-box was synthesized as a retained design
  exploration, motivated by [OpenTitan's documented ASIC-oriented Canright
  choice](https://opensecura.googlesource.com/3p/lowrisc/opentitan/+/refs/heads/master/hw/ip/aes/README.md),
  but the pinned NIST SLP produced the smaller complete candidates in this
  flow. The selected SLP lowered generic cells from 36,843 to about 24,700 for
  the folded baseline and from 73,782 to about 42,700 for the original
  two-round/eight-bit point. Those are same-flow comparisons, not universal
  circuit-minimality claims.
- GHASH was parameterized at 8, 16, 32, and 64 bits per cycle and crossed with
  one- and two-round AES datapaths. This exposes a crucial target-aware result:
  two-round AES reduces cycles but approximately doubles the mapped critical
  combinational path, so its real-time estimate is dominated by one-round AES
  points under the selected library and workload.
- Named mapping uses Yosys `dfflibmap` and ABC against the Nangate Open Cell
  Library typical corner (45 nm, 1.1 V, 25 C), pinned from OpenROAD Flow
  Scripts revision `be0dca0b1fd41df54792b3012350cd52bccd99bb`. The exact library
  SHA-256 and license provenance are in
  `workspace/aes-256-gcm/third_party/nangate45/SOURCE.md`. The flow applies a
  `BUF_X1` input driver and 5 fF output load, checks for unmapped internal
  cells, and retains statistics, logs, and mapped netlists.
- The mapped-netlist gate uses a functional model regenerated from that same
  Liberty file and reruns all 1,038 GCM operations. This verifies synthesis
  semantics for the selected frontier candidate; it is not formal equivalence
  or routed silicon validation.

## Simulation-complete outcome — 2026-08-30

- Candidate commit `9afd0b63e4d85b35a48013ef1bc97414e3e9852a` implements and measures two
  synthesizable organizations under the frozen profile. The evidence-backed
  comparison is recorded in `RESULTS.md` and the machine-readable workspace
  reports.
- Verilator 5.050 is the cycle/lint engine. Yosys 0.68+post
  (`c12172fbae8af5e20f6fb52e3d4e92d56ed587b6`) is the generic synthesis
  engine. The generic-cell comparison is meaningful only inside this identical
  flow and is not an FPGA LUT or ASIC-area claim.
- The host has no configured FPGA/ASIC target, physical board, timing library,
  power model, or leakage/fault instrumentation. The experiment therefore ends
  at the specified simulation-complete boundary; physical metrics remain
  unavailable rather than estimated.

## Profile-freeze verification — 2026-08-30

- The live [FIPS 197 CSRC page](https://csrc.nist.gov/pubs/fips/197/final)
  still identifies FIPS 197-upd1, updated 2023-05-09, as final and states that
  the update made no technical change to AES.
- The live [SP 800-38D CSRC page](https://csrc.nist.gov/pubs/sp/800/38/d/final)
  still identifies the November 2007 publication as final and carries the
  2024-03-06 planning note that NIST decided to revise it. No final successor
  was present on the canonical page, so profile `aes-256-gcm-64-v1` pins the
  2007 text and must be re-reviewed if NIST publishes a replacement.
- The [CAVP block-mode page](https://csrc.nist.gov/Projects/Cryptographic-Algorithm-Validation-Program/CAVP-TESTING-BLOCK-CIPHER-MODES)
  was retrieved 2026-08-30. It describes its GCM vectors as informal
  correctness checks that do not replace validation.
- `KAT_AES.zip`, retrieved from NIST on 2026-08-30, has SHA-256
  `a203b16c9246b2ebae31dee5de21a606be80cf78ceabaca37150236fa098eb60`.
- `gcmtestvectors.zip`, retrieved from NIST on 2026-08-30, has SHA-256
  `f9fc479e134cde2980b3bb7cddbcb567b2cd96fd753835243ed067699f26a023`.
- The normalized committed subset is reproduced only after both archive hashes
  match. It includes AES-256 primitive cases plus GCM encryption, successful
  decryption, and failed-authentication cases within the frozen profile.

## Normative sources

### AES

- [NIST FIPS 197 — Advanced Encryption Standard (AES)](https://csrc.nist.gov/pubs/fips/197/final)
  defines AES-128, AES-192, and AES-256 over 128-bit blocks. This experiment
  selects the AES-256 key schedule and round function; the source, rather than
  an implementation convention, is the authority for byte ordering and the
  state/key-schedule transformations.

### GCM

- [NIST SP 800-38D — Recommendation for Block Cipher Modes of Operation:
  Galois/Counter Mode (GCM) and GMAC](https://csrc.nist.gov/pubs/sp/800/38/d/final)
  defines the authenticated-encryption mode, GHASH, tag generation, IV
  processing, and the authentication failure behavior that the profile must
  make explicit. NIST currently marks the publication for revision, so the
  manifest pins the source used for each run and must be revisited if a
  successor becomes applicable.

### Validation vectors and vocabulary

- [NIST Automated Cryptographic Validation Protocol (ACVP)](https://pages.nist.gov/ACVP/)
  is the reference for machine-readable cryptographic test-vector and
  validation concepts. ACVP compatibility is a future interoperability goal,
  not a claim that this repository is an accredited validation laboratory.

## Architecture context

- [RISC-V Unprivileged ISA — Scalar Cryptography](https://docs.riscv.org/reference/isa/unpriv/scalar-crypto.html)
  is the primary source to consult if the AES implementation is exposed as
  scalar ISA instructions. Any instruction proposal or custom extension must
  separately record its encoding, architectural state, compiler/toolchain
  support, and fallback behavior.
- [RISC-V Unprivileged ISA — Vector Cryptography](https://docs.riscv.org/reference/isa/unpriv/vector-crypto)
  is the primary source to consult if the design uses vector operations. A
  vector design must state its vector length, element grouping, tail/mask
  behavior, and software ABI rather than treating “vector AES” as a single
  comparable datapoint.

## Research rules for this experiment

- Pin the URL, retrieval date, relevant section/table, and any local copy or
  checksum used to generate vectors.
- Separate normative requirements from implementation choices and hypotheses.
- Do not infer security, throughput, area, or energy from an architecture
  diagram. Attach each reported number to a simulator, synthesis, measurement
  artifact, or explicitly labeled estimate.
- Keep rejected architecture branches and failing vectors in the run record;
  they are part of the experiment history.
