# Security behavior review

This review applies to profile `aes-256-gcm-64-v1` and both RTL organizations.
It supports narrow functional and cycle-control claims only. It is not FIPS
140 validation and does not establish resistance to power, EM, timing-glitch,
fault-injection, or other physical attacks.

## Threat model and claim boundary

The in-scope adversary can choose keys, IVs, AAD, payloads, ciphertexts, tags,
lengths, and legal ready/valid stalls, and can observe the external RTL ports
and transaction cycle counters. The current evidence asks whether that
adversary can obtain unauthenticated plaintext, retain stale transaction state,
or change the no-stall control schedule with secret values at fixed public
lengths and mode.

The adversary is not assumed to observe power, EM radiation, internal glitches,
placement/routing, scan state, or analog fault behavior. There is no physical
target on which to measure those effects.

## Measured and inspected properties

- Decryption is fully buffered. The state machine enters `ST_OUTPUT` only after
  the complete 128-bit tag comparison succeeds. Every one of the 150 generated
  modified-key/IV/AAD/ciphertext/tag cases rejects without a plaintext byte.
- Tag comparison is the fixed combinational reduction
  `|(expected_tag ^ computed_tag)`; there is no byte-wise early exit. The
  harness checks equal tag-verdict latency for a zero-byte message. For a
  64-byte message it checks that a valid operation differs from a rejection by
  exactly the 64 serialized authenticated output cycles, so the comparison
  phase itself has equal work while the externally visible total latency
  intentionally reveals whether plaintext is released.
- Across the frozen corpus, each architecture makes 38 comparisons between
  authenticated operations with the same public IV/AAD/payload lengths and
  mode but different values. All have identical no-stall transaction cycles.
  This is evidence for data-independent control on those traces, not a proof
  over all possible internal electrical behavior.
- Input fragmentation and output backpressure are exercised by 32 deterministic
  stalled replays per architecture. Stall cycles are reported separately and
  do not change the scored output.
- The harness tests no-key and invalid-length rejection, key replacement,
  warm-key reuse, reset during input, a failed authentication followed by a
  valid same-key transaction, and explicit zeroization after a successful
  transaction.
- RTL inspection confirms that result acknowledgement clears IV, AAD, data,
  output, tag, counter, GHASH, and transient AES state. Reset and `zeroize`
  additionally clear cached round keys and key-loaded state. Ordinary success
  retains only the expanded key, as required for the declared warm-key path.

## Explicit limitations

- The AES S-box is an unmasked data-dependent lookup synthesized into generic
  logic. No masking, hiding, duplication, parity, infective response, or fault
  detection is implemented. Secret-dependent switching activity is expected.
- Zeroization is verified by RTL behavior and source inspection, not by a
  post-route remanence or scan-chain study. Synthesis and implementation tools
  may transform clearing structures in target-specific ways.
- Authentication success is externally observable through status and through
  the presence of plaintext output; the design does not attempt to hide that
  public API result.
- Nonce uniqueness is the caller's responsibility. The accelerator neither
  generates nor tracks IVs.
- Timing frequency, power, energy, leakage, and fault-resistance metrics remain
  unavailable until a named FPGA or ASIC implementation and suitable physical
  instrumentation exist.

The supported claim is therefore: for the frozen bounded profile and simulated
ready/valid interface, the RTL rejects all tested invalid authentications,
releases no unauthenticated plaintext, clears transaction state at the declared
lifecycle boundaries, and follows a value-independent no-stall cycle schedule
for the fixed-length traces checked by the harness.
