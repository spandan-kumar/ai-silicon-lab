# Experiment 002 result: technology-aware AES-256-GCM frontier

Profile `aes-256-gcm-64-v1` now includes a Boolean-circuit S-box, an
eight-point AES/GHASH architecture sweep, pinned Nangate45 standard-cell
mapping, pre-layout timing estimates, and full-corpus simulation of a mapped
netlist. The candidate commit and clean evaluator run are recorded in
`workspace/aes-256-gcm/reports/results.json` and the corresponding
`runs/<run-id>/run.json`.

## Correctness and reproducibility

Every architecture passes:

- all 256 inputs through both the forward and inverse NIST S-box circuits;
- 5 direct AES-256 key schedules, all 15 round keys each;
- 5 NIST AES-256 primitive vectors in both encrypt and decrypt directions;
- 1,038 full GCM operations: 120 pinned NIST directional vectors, both
  directions of 384 deterministic positive vectors, and 150 negative
  authentication operations;
- 32 deterministic backpressured replays and 38 fixed-length/value-varied
  cycle comparisons;
- empty, partial, boundary, maximum-length, 96-bit-IV, and 8-bit-IV cases;
- rejection, warm reuse, key replacement, reset, zeroize, and
  failure-to-success lifecycle scenarios;
- Verilator `-Wall` lint, generic Yosys synthesis, and byte-identical repeated
  traces.

The selected `balanced-ultrawide-1r32b` Nangate45 mapped netlist independently
passes the same 1,038-operation GCM corpus using functional cell models
generated from the pinned Liberty file. Candidate RTL never links host crypto
or consumes expected outputs; the testbench alone owns the scoreboard.

## Measured architecture frontier

The representative point is warm-key 64-byte encryption with a 96-bit IV, no
AAD, no stalls, and the common serialized 8-bit interface. Area and critical
combinational delay come from Yosys/ABC mapping to Nangate45 typical (45 nm,
1.1 V, 25 C) with `BUF_X1` input drive and 5 fF output load. Estimated latency
is `warm cycles × ABC delay`; estimated throughput assumes the reciprocal of
that delay as the clock. Neither value includes placement, routing, clock-tree,
wire, or uncertainty effects.

| Architecture | AES/GHASH per cycle | Generic cells | Mapped area (µm²) | Delay (ns) | Warm cycles | Est. latency (ns) | Est. Gb/s | Pareto? |
|---|---:|---:|---:|---:|---:|---:|---:|:---:|
| `iterative-1r1b` | 1 round / 1 bit | 24,716 | 54,557.664 | 2.786 | 887 | 2,471.413 | 0.207 | yes |
| `unrolled-2r8b` | 2 rounds / 8 bits | 42,622 | 70,166.278 | 4.996 | 285 | 1,423.997 | 0.360 | no |
| `balanced-1r8b` | 1 round / 8 bits | 26,467 | 57,130.682 | 2.713 | 327 | 887.082 | 0.577 | yes |
| `wide-2r16b` | 2 rounds / 16 bits | 44,701 | 72,843.834 | 5.053 | 245 | 1,237.889 | 0.414 | no |
| `ultrawide-2r32b` | 2 rounds / 32 bits | 48,771 | 78,001.042 | 5.218 | 225 | 1,174.043 | 0.436 | no |
| `balanced-wide-1r16b` | 1 round / 16 bits | 28,503 | 59,662.204 | 2.714 | 287 | 778.909 | 0.657 | yes |
| `balanced-ultrawide-1r32b` | 1 round / 32 bits | 32,633 | 65,147.922 | 2.709 | 267 | 723.279 | 0.708 | yes |
| `balanced-xwide-1r64b` | 1 round / 64 bits | 40,777 | 75,700.408 | 2.726 | 257 | 700.687 | 0.731 | yes |

The central result is a cross-block co-design finding. The prior
`unrolled-2r8b` point spent area on two AES rounds per cycle, but that doubled
the critical path. `balanced-ultrawide-1r32b` instead keeps one AES round and
spends area on GHASH: it maps to 7.2% less area, cuts estimated representative
latency by 49.2%, and raises estimated throughput by 1.97× under the identical
library and constraints. The 64-bit GHASH point is the lowest estimated
latency, but gains only 3.2% throughput over 32-bit for 16.2% more area, so the
32-bit point is the stronger balanced result.

The Pareto set is `iterative-1r1b`, `balanced-1r8b`,
`balanced-wide-1r16b`, `balanced-ultrawide-1r32b`, and
`balanced-xwide-1r64b`. The three two-round variants remain in the report as
measured dominated designs. There is no universal winner without power,
routed timing, and objective weights.

## Claim boundary

The full sweep, generic cell-type counts, mapped-cell counts, hashes, cycle
matrix, and derivations are in
`workspace/aes-256-gcm/reports/results.json`. These results establish
synthesizability and comparative pre-layout technology mapping. They do not
establish routed timing closure, power, energy, physical leakage, fault
resistance, fabrication readiness, or FIPS/CMVP validation; those values remain
explicitly unavailable.
