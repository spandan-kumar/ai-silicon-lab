# AES-256-GCM baseline candidate

The first candidate for the `aes-256-gcm` experiment: a synthesizable
AES-256-GCM engine verified against an independent software reference through
the autonomous harness.

```sh
./harness/aisl verify aes-256-gcm
```

## Contents

| Path | Role |
| --- | --- |
| `reference/aes_gcm_ref.py` | Independent AES-256-GCM model written from FIPS 197 and SP 800-38D. No cryptographic library. This is the oracle. |
| `reference/crossvalidate.js` | Development-time cross-check of the reference against OpenSSL. Takes no part in a measured run. |
| `rtl/aes_sbox.sv` | FIPS 197 substitution box, generated from the specification table |
| `rtl/aes256_enc.sv` | Iterative AES-256 encryption, one round per cycle, on-the-fly key schedule |
| `rtl/ghash_mul.sv` | Bit-serial GF(2^128) multiplier, 128 cycles per block |
| `rtl/aes_gcm.sv` | GCM control: J0 derivation, GCTR, GHASH sequencing, tag formation and checking |
| `sim/tb_aes_gcm.cpp` | Verilator testbench for the full engine. Receives stimulus only. |
| `sim/tb_aes_core.cpp` | Verilator testbench for the block cipher alone |
| `stimulus.py` | Deterministic corpus generation shared by both sides of every comparison |
| `harness_plugin.py` | Wiring into the harness |

## Architecture

GCM needs only the forward cipher, for both directions, so there is no inverse
datapath. The AES core takes 15 cycles per block. The GHASH multiplier takes
128. That ratio is the design's defining characteristic and the obvious first
thing an exploration phase should attack.

The engine streams bytes: after `start`, the input carries the IV, then the
AAD, then the payload, with lengths latched at the start. Both streams use
`valid`/`ready` and tolerate stalls in any phase, which the interface-stress
workload exercises by running identical payloads under six different stall
patterns and requiring byte-identical results.

The frozen profile is in [`../../experiments/aes-256-gcm/PROFILE.md`](../../experiments/aes-256-gcm/PROFILE.md).

## Measured results

566 vectors across six workloads, all exact. 38,563 generic Yosys cells and
6,604 flip-flops. 11.3 cycles per byte marginal throughput; 483 cycles for a
one-byte message. No timing, power, or target-technology number exists, and the
run record carries those as null rather than as an estimate.

Two findings came out of the first verification runs and are worth keeping:

**The design leaked its computed tag on rejection.** The first run reported the
tag it had derived even when authentication failed, which hands an attacker the
value needed to forge the message. The RTL now forces the tag output to zero on
failure, and every corrupted-tag vector checks it.

**Over half the flip-flops exist to satisfy one profile rule.** Because the
profile withholds plaintext until the tag verifies, the design buffers it. At
`MAX_TEXT_BYTES` 512 that is 6,604 flip-flops; at 64 it is 3,017. The buffer,
not the cipher, dominates the area.

## Independence of the oracle

The Python reference implements the S-box, the GF(2^128) multiply, the key
schedule, and the mode logic locally. During development it was checked against
OpenSSL 3.6.3 over 215 generated cases covering empty, partial, and aligned
payloads, 96-bit and other IV lengths, and truncated tags, with every corrupted
tag rejected. That cross-check validated the reference; it does not run during
verification, and the candidate links no cryptographic library, which
`policy:no-host-crypto` checks against the built binary.
