# Experiment plan: AES-256-GCM hardware accelerator

## Question

What hardware organization gives the best measured tradeoff for AES-256-GCM
under a stated target and workload? “Most optimized” is not a complete
question: a design can minimize area, maximize throughput, minimize latency,
minimize energy, or balance several of them. This experiment therefore seeks a
Pareto frontier and only uses a scalar score when the target owner explicitly
freezes its weights.

The first deliverable is a correct, synthesizable, cycle-accurate simulation
candidate. Physical implementation and security claims are later phases, not
assumptions hidden in the first RTL result.

## Normative profile to freeze before RTL

The experiment must pin the revision and interpretation of:

- AES-256 as specified by NIST FIPS 197: a 256-bit key and 128-bit block;
- GCM as specified by NIST SP 800-38D;
- the selected NIST/ACVP-compatible vector format and response semantics;
- any optional RISC-V scalar/vector crypto extension profile used as a
  comparison, never as an implicit requirement.

NIST has announced a revision of SP 800-38D. The experiment must record the
revision actually used and revisit the profile if the revision changes before
the experiment is frozen. The primary references are recorded in
`experiment.json`.

## Profile decisions that cannot remain implicit

Before comparing designs, freeze:

- encryption, decryption, or both;
- supported tag lengths and whether tag truncation is exposed;
- supported IV lengths, including 96-bit IVs and non-96-bit IV processing;
- maximum plaintext, AAD, and invocation lengths;
- whether messages may be empty or zero-length in either channel;
- whether plaintext is released during decryption or only after tag
  verification;
- behavior on an invalid tag: status, output validity, state clearing, and
  whether partial plaintext is discarded;
- key load, key expansion, key change, and zeroization behavior;
- byte order and bit order at the API, bus, AES state, counter, GHASH, and tag;
- streaming packet framing, `valid/ready` backpressure, and message-boundary
  markers;
- reset behavior during idle, key setup, AAD, payload, tag, and error states;
- counter exhaustion and length overflow behavior;
- whether nonce/IV uniqueness is the caller’s responsibility or enforced by a
  separate wrapper;
- whether constant-latency/data-independent timing is a required claim or an
  optional measured property.

A vector that is ambiguous about any of these is not a stable benchmark.

## Threat model and claim boundaries

Functional correctness and security are separate axes.

The baseline security review should inspect for:

- secret-dependent branches, stalls, memory accesses, or early exits;
- secret-dependent table lookups or unmasked S-box structures;
- tag comparison behavior and failure timing;
- key and GHASH-state lifetime after completion, error, reset, and key change;
- accidental exposure through debug/status ports or traces;
- fault handling and whether an error can leave authenticated data marked valid.

Simulation can show a fixed-cycle property for selected traces and can support
RTL assertions, but it cannot prove resistance to power, EM, cache, fault, or
glitch attacks. Any physical leakage claim needs a stated threat model and
appropriate instrumentation such as a later board-level leakage study. Do not
call the result FIPS 140 validated merely because NIST vectors pass.

## Architecture branches

The agent is free to choose and may explore several materially different
organizations:

1. **Software baseline:** portable AES-256-GCM on the selected CPU, with no
   accelerator. This establishes a useful cycles/byte baseline but is not a
   hardware-accelerator result.
2. **Memory-mapped iterative engine:** a narrow register or streaming
   interface with a folded AES round datapath and serialized GHASH multiplier.
3. **Partially unrolled engine:** several AES rounds or GHASH operations per
   cycle, with buffering and a wider interface.
4. **Pipelined engine:** one or more blocks in flight, with explicit key
   schedule and counter handling.
5. **CPU extension/coprocessor:** a named instruction or tightly coupled
   interface, measured against the same software API and message corpus.
6. **Vector/extension comparison:** only if the toolchain and core support are
   real and pinned; a standard extension is a comparison point, not a shortcut
   to claiming a novel accelerator.

For each candidate record whether the key schedule is on-the-fly or cached,
whether AES and GHASH share datapath resources, the multiplier structure,
interface width, buffering, DMA policy, and how setup cost is amortized.

## Reference and vector strategy

Use at least two independently reasoned layers:

- a simple software reference used to generate deterministic expected outputs;
- a pinned public validation corpus, preferably NIST/ACVP-compatible, whose
  source and license are recorded.

The vector generator must record its version, input seed, profile, corpus hash,
and reference implementation identity. The candidate must receive keys, IVs,
AAD, plaintext/ciphertext, and expected results through the declared harness;
it must not read expected outputs or oracle verdicts.

The corpus should include:

- AES-256 block encryption and decryption known-answer tests;
- key-schedule and, when useful, intermediate-round checks;
- full GCM encryption and decryption vectors;
- empty plaintext, empty AAD, both empty, and one-byte inputs;
- lengths around every 128-bit boundary: 0, 1, 15, 16, 17, 31, 32, and larger;
- AAD lengths independent of plaintext lengths and large AAD-only messages;
- 96-bit IVs plus supported non-96-bit IVs;
- every supported tag length and exact tag ordering;
- modified ciphertext, AAD, IV, key, and tag negative cases;
- randomized vectors with a committed generator seed;
- backpressure and reset scenarios around legal transaction boundaries;
- repeated key/message operations to detect stale state;
- maximum supported lengths and explicit overflow/rejection tests.

Do not assume a library’s default IV length, tag length, endian convention, or
decryption behavior matches the frozen profile. Normalize inputs explicitly.

## RTL harness contract

The harness should expose a small, architecture-independent transaction model
even if the candidate internally uses a CPU bus:

- clock and reset;
- key load and key-ready status;
- IV/message/AAD stream with valid/ready and explicit boundaries;
- encrypt/decrypt mode and tag input/output;
- result status, authentication success/failure, and error codes;
- optional cycle and byte counters observed by the harness;
- trace/checksum output that is generated by RTL, not by the oracle.

The harness must test arbitrary legal stalls, input fragmentation, output
backpressure, and message interleaving policy. It must state whether channels
are independent or serialized. A candidate that drops or reorders bytes under
stall is incorrect even if an unstalled happy-path vector passes.

## Correctness gates

### Profile gate

- normative documents and revisions are pinned;
- supported IV/tag/length/mode behavior is documented;
- byte/bit ordering is tested with asymmetric patterns;
- target and objective function are explicit.

### Simulation gate

- primitive and full-GCM positive vectors pass exactly;
- every negative tag/ciphertext/AAD case rejects correctly;
- empty, partial, aligned, maximum, and overflow cases are covered;
- reset, key change, stalls, and transaction boundaries pass assertions;
- candidate RTL is lint-clean enough for the selected flow and synthesizes;
- repeated runs produce identical output and cycle traces;
- no host crypto implementation participates in the measured candidate path;
- all unavailable metrics remain null and all security limitations are stated.

### Physical gate

- the exact RTL configuration is synthesized and implemented for a named
  target;
- clock and I/O constraints are explicit and timing closure is measured;
- the same vector corpus runs on the target;
- hardware results or checksums match RTL simulation;
- resource, frequency, power, and energy data identify their measurement
  method and confidence.

### Security-review gate

- each claim names a threat model and claim strength;
- constant-latency/data-independent behavior has trace/assertion evidence;
- key/state clearing is tested after success, failure, reset, and replacement;
- any side-channel or fault result comes from appropriate physical evidence;
- unsupported certification claims are explicitly excluded.

## Metrics and formulas

Record raw values as well as derived values:

- setup latency in cycles, separated into cold-key and warm-key cases;
- total latency in cycles for each message/AAD size;
- steady-state throughput in bytes/cycle and, only for a named clock, bits/s;
- cycles/byte with and without key setup amortization;
- input/output interface utilization and stall cycles;
- LUT/FF/BRAM/DSP or ASIC cell/area results;
- target frequency, worst slack, critical path, and achieved timing;
- power or energy/byte with a named measurement or estimation method;
- security observations and unproven properties as separate fields.

Never compare a small-message latency result with a large-stream throughput
result without labeling the difference. Never compare FPGA LUTs with ASIC
standard cells as though they were the same unit. A Pareto table should keep
dominated designs visible when they explain an architectural tradeoff.

## Fairness and baselines

Every comparison freezes the same algorithm profile, vectors, compiler flags,
clock assumption, interface width, target, synthesis constraints, and setup
amortization rule. At least one software baseline and one simple hardware
baseline should be retained before optimizing.

If an agent changes its prompt, model, reasoning effort, subagent strategy, or
tool access, that is a new agent run record. Do not attribute a later design to
the first session merely because the Git branch is shared.

## Physical follow-up

The current host has Verilator and Yosys but no detected FPGA board or ASIC
implementation flow. When one becomes available, add a target profile with
board/tool versions, clock constraints, memory technology, I/O capture method,
bitstream/netlist hash, and power instrumentation. If no physical target is
available, finish the simulation/synthesis stages and mark physical metrics
unavailable; do not downgrade the claim silently.

## Repository layout for the future candidate

Keep the experiment contract separate from any one architecture:

```text
experiments/aes-256-gcm/
    experiment.json       # machine-readable contract
    PLAN.md               # decisions, gates, and edge cases
    RESEARCH.md           # future dated research notes and revisions
workspace/aes-256-gcm/   # candidate RTL/firmware/harness when implementation starts
runs/<run-id>/            # immutable-in-practice run evidence, ignored by Git
```

The implementation may choose a different layout if the manifest and run
record make the boundary unambiguous.
