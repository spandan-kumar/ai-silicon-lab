# Frozen profile: AES-256-GCM-64

Profile identifier: `aes-256-gcm-64-v1`

Frozen on: 2026-08-30

This document resolves the choices left open by the experiment specification.
Changing any normative or interface choice below creates a new profile and
invalidates direct cycle/area comparisons with this one.

## Normative basis

- AES is AES-256 from **NIST FIPS 197-upd1**, published 2001 and updated
  2023-05-09. The update makes no technical change to the AES algorithm.
- GCM is **NIST SP 800-38D**, published 2007-11. On the freeze date NIST still
  labels this publication as planned for revision; no final successor is
  published on its canonical CSRC page.
- Public known-answer vectors are from the NIST CAVP AES KAT and GCM archives
  linked in `vectors/SOURCES.json`. Passing them is informal correctness
  evidence, not CAVP, ACVP, CMVP, or FIPS 140 validation.

## Algorithm and limits

- AES key length: exactly 256 bits. AES block size: exactly 128 bits.
- Operations: authenticated encryption and authenticated decryption.
- Authentication tag: exactly 128 bits. Truncation is not supported.
- IV lengths: exactly 96 bits (the SP 800-38D fast path) or 8 bits (the general
  GHASH-derived `J0` path represented in the official CAVP corpus).
- AAD length: 0 through 64 bytes, inclusive.
- Payload/ciphertext length: 0 through 64 bytes, inclusive.
- Empty IV is not supported. Empty AAD and empty payload are supported.
- The wrapper rejects unsupported IV/tag/length values before accepting body
  bytes. At this bounded size the GCM 32-bit counter cannot exhaust; the
  length limit is therefore the enforced overflow boundary.
- Nonce uniqueness is the caller's responsibility. The accelerator does not
  generate, remember, or police IVs.

## Authentication and output policy

- Encryption buffers the complete transaction, produces ciphertext, then a
  tag and success status.
- Decryption buffers the complete ciphertext and supplied tag. It emits no
  plaintext until a constant-work 128-bit tag comparison succeeds.
- On tag failure no plaintext byte is valid, `auth_ok` is false, an
  authentication error is reported, and message, GHASH, and temporary AES
  state are cleared before the next command.
- Tag comparison work does not exit early. This is a limited control/latency
  claim, not a physical side-channel-resistance claim.

## Byte, bit, and counter ordering

- Hex strings and byte streams are in network order: the first byte is the
  most-significant byte of the 128-bit AES/GHASH value.
- AES state byte `4*c+r` is row `r`, column `c`, matching FIPS 197.
- GHASH interprets a 128-bit block as the polynomial bit string specified by
  SP 800-38D, with the leftmost bit processed first. Partial blocks are padded
  with zero bits on the right.
- The GHASH length block is `len(AAD)*8 || len(ciphertext)*8`, two unsigned
  64-bit big-endian integers.
- For a 96-bit IV, `J0 = IV || 0x00000001`. Otherwise `J0` is the SP 800-38D
  GHASH of the padded IV and its 64-bit length encoding.
- `inc32` increments only the rightmost 32 bits, modulo 2^32, in big-endian
  order.

## Transaction interface

The common RTL wrapper uses a single serialized byte input and byte output.
Channels are not independent and messages may not interleave.

1. Load or retain a 256-bit key through `key_valid/key_ready`.
2. Submit a command containing mode and byte lengths through
   `cmd_valid/cmd_ready`.
3. Send exactly `iv_len`, then `aad_len`, then `data_len` bytes through
   `in_valid/in_ready`. Zero-length phases are skipped automatically.
4. For decryption, submit the 128-bit expected tag after the data phase.
5. Receive exactly `data_len` output bytes through `out_valid/out_ready`, then
   a 128-bit tag (encryption) or authentication verdict (decryption), status,
   and cycle counters.

Every transfer occurs only when `valid && ready`. The producer may fragment or
stall any input phase and the consumer may stall output arbitrarily. A new
command is refused until the prior result has been acknowledged.

## Key lifecycle and reset

- Loading a key replaces the old key and cached round keys before a command is
  accepted. Cold-key and warm-key measurements are reported separately.
- An explicit zeroize request clears key material, expanded keys, message
  buffers, GHASH/AES temporaries, tags, and status.
- Synchronous reset has the same clearing effect and aborts any in-flight
  transaction without producing output.
- Transaction temporaries are cleared after success, failure, reset, or error.
  The key is retained after an ordinary successful transaction for warm-key
  operation, and is cleared only by reset, zeroize, or replacement.

## Comparison target and objective

- Simulation: Verilator cycle simulation with the same testbench, vectors,
  stalls, compiler flags, and interface for every candidate.
- Synthesis: Yosys generic `synth`/`stat` using the same version and top-level
  constraints. Generic cells are comparable only within this experiment.
- Objective: retain the Pareto set minimizing generic synthesized cell area,
  cold/warm latency, and cycles/byte while maximizing sustained bytes/cycle.
  No scalar weights are frozen and no universal winner is claimed.
- FPGA/ASIC timing, target frequency, Gbps, power, energy, and physical
  leakage/fault resistance are unavailable until a named implementation flow
  and physical target exist.
