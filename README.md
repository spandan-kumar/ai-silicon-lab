# AI Silicon Lab

AI Silicon Lab is an open-ended hardware/software research workspace for a
versioned program of computer-architecture, RTL, simulation, verification,
synthesis, and hardware/software co-design experiments.

The lab supplies capabilities and trusted measurements. It does not prescribe
a CPU, ISA, renderer, memory system, simulator, or implementation sequence.
Examples throughout the repository are illustrative rather than a solution or
required workflow.
The first experiment is a verified Doom-capable computer. The lab also now
contains the specification and research plan for an AES-256-GCM accelerator;
future experiments can use the same registry, evidence, and provenance model.

## Experiment 002: AES-256-GCM

The accelerator implementation and ongoing chip-design research live on
[`codex/experiment-2-crypto-algo`](https://github.com/spandan-kumar/ai-silicon-lab/tree/codex/experiment-2-crypto-algo).
Read the [progress and research handoff](https://github.com/spandan-kumar/ai-silicon-lab/blob/codex/experiment-2-crypto-algo/experiments/aes-256-gcm/PROGRESS.md)
for what we tried, verified results, limitations and the current open questions.
The verified accelerator baseline is separate from the still-unmet
world-first research goal.

## Getting started

Start with:

```sh
./lab/status
```

Fresh autonomous coding sessions should read [`AGENTS.md`](AGENTS.md) first.
It grants broad freedom to install tools and research the internet while
requiring every technical claim to be grounded in executed, reproducible
evidence rather than assumptions.

The primary design area is [`workspace/`](workspace/), but the agent is
authorized to maintain the repository as a whole, including adding, editing,
moving, or deleting files as needed. The evaluator and its reference data live
in [`lab/`](lab/) and [`ground_truth/`](ground_truth/), which are protected
during normal experiments. Evaluations are recorded under
[`runs/`](runs/); those files are intentionally mutable and ignored by Git.

See [`LAB.md`](LAB.md), [`EVALUATION.md`](EVALUATION.md),
[`REPRODUCIBILITY.md`](REPRODUCIBILITY.md), [`SECURITY.md`](SECURITY.md), and
[`EXPERIMENTS.md`](EXPERIMENTS.md) for the operating contract.

The experiment program is described in [`experiments/README.md`](experiments/README.md).
List and validate its manifests with:

```sh
./tools/experiment list
./tools/experiment check
```
