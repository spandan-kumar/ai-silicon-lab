# AI Silicon Lab experiment program

This directory turns the repository from a single Doom attempt into a
collection of reproducible hardware-research experiments. Doom remains the
first verified end-to-end computer experiment. AES-256-GCM is the first
cryptographic-accelerator experiment. Future work can add other experiments
without changing the meaning of an existing oracle.

The registry is [`registry.json`](registry.json). Validate it with:

```sh
./tools/experiment list
./tools/experiment check
./tools/experiment show doom-rv32imc
./tools/experiment show aes-256-gcm
```

## What is versioned

Each experiment has a machine-readable `experiment.json` and a human-readable
`PLAN.md`. The manifest freezes the purpose, scope, design freedom, workload,
oracle, metrics, phase gates, artifacts, provenance requirements, and research
references. The plan explains why those choices exist and how an agent should
extend them without treating an example implementation as mandatory.

An experiment specification is not a result. Results live in the existing
`runs/<run-id>/` records and in candidate-specific artifacts. A candidate may
be successful for one experiment and irrelevant to another; never compare
numbers across experiments without a declared normalization and target.

## Three identities that must not be conflated

1. **Experiment identity** — what question is being asked and which revision
   of the workload/acceptance contract applies.
2. **Agent identity** — which model, harness, prompt/configuration, reasoning
   settings, subagents, and measured or reported resources produced an attempt.
3. **Implementation identity** — which Git commit, RTL/firmware, toolchain,
   target, input corpus, and evaluator produced the hardware result.

The same experiment can have many agent attempts and many candidate designs.
The same candidate can be re-evaluated by more than one harness. Run records
must link all three identities rather than putting the information in a prose
paragraph that cannot be queried.

## Standard lifecycle

1. **Specify:** freeze the objective, target profile, correctness oracle,
   workload matrix, metrics, and claim boundaries.
2. **Research:** use primary standards, papers, source repositories, and tool
   documentation. Record the URL, revision/date, and the fact it supports.
3. **Reference:** build or obtain an independent software/reference model;
   pin its source and generate deterministic vectors or output archives.
4. **Baseline:** implement the smallest credible software and synthesizable RTL
   baselines. Establish correctness before optimizing.
5. **Explore:** let the agent choose architectures and tools. Every materially
   different candidate gets a commit, configuration, run ID, and evidence.
6. **Simulate:** execute real candidate RTL, compare exact outputs, and record
   cycles and protocol traces. Host code may orchestrate and compare, but may
   not silently replace the hardware algorithm.
7. **Synthesize:** measure generic or target resource use and investigate every
   warning. Do not call a design optimized without a stated target and
   objective.
8. **Implement physically:** when hardware access exists, run synthesis/P&R,
   close timing, execute the same workload on the board or chip, and compare
   its output with RTL simulation.
9. **Report:** separate measured facts, derived metrics, hypotheses, and
   unavailable values. Preserve failures and rejected designs.

## Agent and model provenance

For every agent attempt, create or retain a run record based on
[`schema/run-record.schema.json`](schema/run-record.schema.json). At minimum,
record:

- canonical model ID and readable alias, with `alias-only` when exact identity
  is unavailable;
- harness name/version, operating environment, and relevant skills/tools;
- reasoning effort, reasoning mode, context/compaction mode, and goal/config
  hashes when available;
- parent/child relationships for subagents and the work each child owned;
- input, cached-input, cache-write, output, reasoning, and total tokens when
  exposed by the harness;
- agent wall time, human time, build time, RTL-simulation time, synthesis time,
  and physical-hardware time as separate fields;
- cost, currency, rate source/date, and whether the number is measured,
  reported, estimated, or unavailable;
- candidate commit, experiment revision, evaluator run IDs, and artifact
  hashes.

Do not copy hidden prompts, credentials, private conversations, or unrelated
personal data into a record. If the harness does not expose a field, use
`null` plus a source/notes field. A reported approximation is useful history,
but it is not billing telemetry or an experimental measurement.

## Fair comparisons

When comparing models or agent workflows, freeze the experiment revision,
benchmark corpus, target profile, tool versions, repository starting commit,
allowed external access, and human-intervention policy. Vary only the factor
under study where possible. Report at least:

- correctness and required evidence;
- hardware quality metrics for the stated target;
- agent token/time/cost metrics;
- number and type of human interventions;
- failed attempts, retries, and subagent work;
- reproducibility status.

Lower token use, fewer turns, or shorter wall time is not an improvement if the
hardware result or evidence quality regresses. Keep quality and agent-resource
metrics as separate axes; do not hide a tradeoff in one arbitrary score.

## Experiment-specific truth

The protected `lab/evaluate` entry point remains the canonical Doom evaluator.
It is intentionally not generalized by this change. New experiments should
provide their own candidate adapter, oracle, vectors, and evaluator under an
experiment-specific workspace while reusing the provenance and evidence
contract. This avoids weakening a trusted existing benchmark merely to make a
new algorithm fit it.
