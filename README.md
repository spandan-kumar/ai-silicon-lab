# AI Silicon Lab

AI Silicon Lab is an open-ended hardware/software research workspace for
computer architecture, RTL, simulation, verification, synthesis, and
hardware/software co-design experiments.

The lab supplies capabilities and trusted measurements. It does not prescribe
a CPU, ISA, renderer, memory system, simulator, or implementation sequence.
The first eventual objective is to build a computer capable of running DOOM;
this repository establishes the laboratory for that experiment and does not
contain that computer.

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
