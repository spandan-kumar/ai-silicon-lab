# Frozen conformance profile: AES-256-GCM baseline

`experiment.json` requires that a set of decisions be explicit before any two
designs can be compared. This file records the decisions actually taken for the
baseline candidate in `workspace/aes256gcm/`. It is the document the
`profile-frozen` gate's reviewed criteria refer to.

## Normative sources

| Element | Source | How it was used |
| --- | --- | --- |
| AES-256 block cipher and key schedule | NIST FIPS 197 | S-box, round structure, and Nk=8/Nr=14 key expansion implemented directly |
| GCM construction | NIST SP 800-38D | GHASH bit convention, J0 derivation, GCTR, tag formation |
| Independent confirmation | OpenSSL 3.6.3 via Node.js v26.7.0 | 215 generated cases cross-checked against the Python reference |

The reference model implements the algorithm from the specifications rather
than calling a library, so agreement with the RTL is agreement between two
independent constructions. The OpenSSL cross-check is a third construction and
was used during development to validate the reference; it takes no part in a
measured run, and the candidate links no cryptographic library.

**Revision caveat.** `experiment.json` notes that a revision of SP 800-38D was
announced. The baseline was built against the GCM construction as described in
the published SP 800-38D and confirmed against OpenSSL. If a revision changes
any behaviour in the table below, this profile must be re-frozen and the
corpora regenerated. This has not been re-checked against a newer revision.

## Frozen decisions

| Decision | Value |
| --- | --- |
| Operations | Encryption and decryption |
| Key size | 256 bits only |
| IV lengths | 96-bit fast path, plus the GHASH path for any other length; both exercised |
| Tag lengths | 1 to 16 bytes; truncation keeps the leftmost bytes |
| Maximum payload | 512 bytes (`MAX_TEXT_BYTES`), set by the plaintext-hold buffer |
| Maximum AAD | Bounded only by the 32-bit length counter |
| Empty messages | Permitted in both channels, including empty payload with empty AAD |
| Plaintext release | Only after the tag verifies; never streamed ahead of verification |
| Tag-failure output | No plaintext, `tag_ok` low, and the tag output is forced to zero |
| Key/state clearing | GHASH accumulator and keystream registers cleared on completion and on failure |
| Byte order | Byte 0 of every block, key, IV, and tag is the most significant byte |
| Framing | One input byte stream carrying IV, then AAD, then payload, with lengths latched at `start` |
| Backpressure | `valid`/`ready` on both streams; stalls permitted in any phase |
| Reset | Asynchronous, active low; applied between operations, so no state crosses a message boundary |
| Nonce uniqueness | The caller's responsibility; not enforced by this block |
| Counter exhaustion | Not handled; the 512-byte bound makes 2^32 block overflow unreachable |

### Why the tag is suppressed on failure

Publishing the tag a design computed after rejecting a message hands an
attacker the value needed to forge it. The first verification run exposed this:
the RTL reported its computed tag on every negative case. The profile now
requires zeros, and `gcm-edge-cases` checks it on every corrupted-tag vector.

## Threat model and claim boundary

The security claims this baseline supports, and only these:

- **Claimed.** For the 24 probe cases in `security-latency-probe`, operations of
  identical length took an identical number of cycles regardless of key and
  data values. The AES core showed a constant 15 cycles per block across 128
  key/plaintext combinations.
- **Claimed.** A corrupted tag is rejected, no plaintext byte is emitted, and
  no tag value is published.

- **Not claimed.** Resistance to power, electromagnetic, timing-cache, fault, or
  glitch attacks. The S-box is an unmasked lookup table. Simulation cannot
  establish any of these properties, and no leakage instrumentation exists on
  this host.
- **Not claimed.** FIPS 140 validation of any kind. Passing algorithm vectors is
  not certification.
- **Not claimed.** Any timing, power, or target-technology figure. No FPGA or
  ASIC flow is installed; those metrics are recorded as null.

## Target profile and objective function

**Deliberately not frozen.** No physical target has been selected, so no
objective function over area, throughput, latency, and power is meaningful yet.
The `target-implemented` gate is therefore unevaluated rather than failed, and
the `profile-frozen` criterion covering the objective function stays open. The
generic Yosys cell counts below are technology-independent and must not be read
as area on any real process.

## Measured baseline

Measurements from run `second-pass`; the run record carries the full detail.

| Metric | Value | Source |
| --- | --- | --- |
| Algorithm correctness | 566 of 566 vectors exact across six workloads | measured |
| AES block latency | 15 cycles, constant over 128 cases | measured |
| Setup cost (96-bit IV, 16-byte AAD) | ~467 cycles before the first payload block | measured |
| Steady-state throughput | 11.3 cycles/byte marginal, 0.088 bytes/cycle | measured |
| Cycles per byte, 1 byte | 483.0 | measured |
| Cycles per byte, 512 bytes | 12.0 | measured |
| Synthesized area | 38,563 generic cells, 6,604 flip-flops, no inferred memory | measured |
| Timing / fmax | null | unavailable: no target library |
| Energy | null | unavailable: no power model |

The dominant cost is the bit-serial GHASH at 128 cycles per block against the
AES datapath's 15. The dominant area term is the plaintext-hold buffer: at
`MAX_TEXT_BYTES` 512 the design is 38,563 cells and 6,604 flip-flops, and at 64
it is 26,122 and 3,017. Roughly 54% of the flip-flops exist to satisfy the
release-after-verification rule. Both are consequences of frozen profile
choices, and both are the natural first targets for architecture exploration.
