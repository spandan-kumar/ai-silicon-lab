# AES-256-GCM research record

This is a dated research record for Experiment 002. It identifies the sources
that define the primitive and the verification vocabulary; it is not a
certification claim. If a source changes or a successor publication becomes
normative, update this record and the experiment manifest before changing the
profile.

Research date: 2026-08-29

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
