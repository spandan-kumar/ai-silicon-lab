# Experiment records

The lab is a collection of independently specified hardware experiments. The
catalogue and machine-readable contracts live under
[`experiments/`](experiments/); this file explains how their results relate to
the existing evaluator records.

## Directory model

```text
experiments/
    registry.json
    schema/
    <experiment-id>/
        experiment.json          # the frozen question and acceptance contract
        harness.json             # how this repository currently executes it
        PLAN.md
        PROFILE.md               # when a conformance profile has been frozen
        RESEARCH.md              # when the experiment has dated research notes
experiments/examples/            # validated provenance examples/templates
runs/<run-id>/                    # evaluator output; ignored by Git
workspace/<experiment-candidate>/ # candidate source and harness
```

An experiment specification defines the question, target/profile, workload,
oracle, correctness gates, metrics, evidence, and claim limits. It does not
claim that a candidate exists. A run record links that specification to a
particular agent attempt and implementation result.

## Run record shape

The common run-record contract is described by
[`experiments/schema/run-record.schema.json`](experiments/schema/run-record.schema.json)
and validated with `./tools/experiment validate-run PATH`.

Each record keeps these identities distinct:

- **Experiment:** ID and revision, including the workload/vector contract.
- **Agent:** model ID/alias, harness/version, reasoning effort/mode, public
  instruction hashes, subagents, token usage, time, and cost.
- **Implementation:** Git commit, RTL/firmware, simulator/synthesis/board,
  inputs, outputs, metrics, and artifact hashes.

Token and time fields carry a source such as `measured`, `reported`,
`estimated`, or `unavailable`. A value like “approximately 2.6M tokens” is
valid historical context when labeled as a report; it is not silently promoted
to billing telemetry. The examples at
[`experiments/examples/agent-run-reported.example.json`](experiments/examples/agent-run-reported.example.json)
and
[`experiments/examples/doom-baseline-run-record.example.json`](experiments/examples/doom-baseline-run-record.example.json)
show this distinction for the initial Doom agent run and its evaluator result.

## Existing Doom records

The protected Doom evaluator continues to write its detailed records under
`runs/<run-id>/`, including commands, logs, Git state, frame comparisons,
cycles, traces, and integrity checks. The Doom experiment plan maps those
records to the simulation-complete and future physical-verification gates.

## New experiments

The AES-256-GCM experiment has its own correctness vectors, interface contract,
performance metrics, target profile, and security-claim boundary. Its candidate
and evaluator are not forced through the Doom frame evaluator. It reuses the
common provenance model and preserves failed and rejected designs as evidence.

An experiment joins the autonomous harness by adding `harness.json` next to its
`experiment.json`, plus a plugin implementing the reference and candidate
sides. The two files are kept separate on purpose: `experiment.json` is what
the experiment promised, and `harness.json` is how the repository runs it
today. `harness.json` also maps each prose gate criterion to the check IDs that
would demonstrate it, so a criterion nobody wired up reports as unevaluated
rather than quietly disappearing from the gate.
