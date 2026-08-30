# Experiment 002 result: simulation-complete AES-256-GCM

Profile `aes-256-gcm-64-v1` reached the simulation-complete gate on clean
candidate commit `9afd0b63e4d85b35a48013ef1bc97414e3e9852a`. The retained local
evaluator run is `runs/aes-gcm-9afd0b6-simulation-complete/run.json`; its run
record passes `./tools/experiment validate-run`.

## Correctness and reproducibility

Both hardware organizations pass:

- 5 direct AES-256 key schedules, all 15 round keys each;
- 5 NIST AES-256 primitive vectors in both encrypt and decrypt directions;
- 1,038 full GCM operations per architecture: 120 pinned NIST directional
  vectors, both directions of 384 deterministic positive vectors, and 150
  negative authentication operations;
- empty, partial, block-boundary, maximum-length, 96-bit-IV, and 8-bit-IV
  cases from the frozen matrix;
- 32 deterministic backpressured replays per architecture;
- no-key and overflow rejection, warm reuse, key replacement, reset across
  key/input/tag/output/result/error phases, zeroize during payload input,
  failure-to-success reuse, and explicit zeroization after success;
- Verilator `-Wall` lint and generic Yosys synthesis; and
- byte-identical outputs and cycle traces across two complete repeated runs.

The candidate RTL does not link host crypto or consume expected outputs. The
C++ testbench alone owns the expected-value scoreboard. The independent Python
model is additionally differential-tested against OpenSSL 3.6.3.

## Pareto comparison

The representative performance point below is a warm-key 64-byte encryption
with a 96-bit IV, no AAD, no injected stalls, and the common serialized 8-bit
interface. Cold latency includes the measured key setup.

| Organization | AES/GHASH work per cycle | Generic cells | Key setup | Warm cycles | Cold cycles | Cycles/byte | Bytes/cycle |
|---|---:|---:|---:|---:|---:|---:|---:|
| `iterative-1r1b` | 1 round / 1 bit | 36,843 | 8 | 887 | 895 | 13.859375 | 0.072153326 |
| `unrolled-2r8b` | 2 rounds / 8 bits | 73,782 | 5 | 285 | 290 | 4.453125 | 0.224561404 |

Across all 1,038 corpus operations, mean transaction latency is 941.276 cycles
for the folded design and 229.596 cycles for the faster design, a 4.10× cycle
reduction. At the representative 64-byte point, the faster organization uses
2.003× as many generic cells and delivers 3.112× the throughput, or 1.554× the
bytes/cycle per generic cell. Both candidates are therefore nondominated: the
folded design minimizes this experiment's area proxy, while the unrolled design
minimizes latency and cycles/byte and maximizes throughput.

The software baseline measures OpenSSL EVP cold-key wall time on the Apple M4
host. Its 64-byte/no-AAD median is 589.04 ns across five 100,000-operation
repeats. That host-specific number is retained as a software reference, not
converted into or directly ranked against targetless RTL cycles.

## Claim boundary

The complete measurement matrix and generic cell-type counts are in
`workspace/aes-256-gcm/reports/results.json`; the software measurements are in
`workspace/aes-256-gcm/reports/software_baseline.json`. The threat model and
cycle-control evidence are in `workspace/aes-256-gcm/SECURITY.md`.

No FPGA/ASIC target, implementation clock, timing library, physical board,
power model, or leakage/fault instrument is configured. Accordingly, target
MHz/Gbps, slack, routed resources, power, energy, physical leakage, and fault
resistance remain unavailable (`null`). This result makes no FIPS/CMVP/ACVP
validation claim and does not name a universal best architecture without a
target and objective weights.
