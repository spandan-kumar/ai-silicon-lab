# AI Silicon Lab agent instructions

AI Silicon Lab is an open-ended hardware/software research laboratory. The
eventual objective is to attempt a computer capable of running DOOM; this
repository does not prescribe the computer's architecture or implementation.

## Freedom to investigate and build

- Choose any architecture, ISA, language, simulator, compiler, hardware/software
  split, verification method, or implementation strategy that serves the
  objective.
- You have full liberty to install and use whatever simulators, synthesis and
  place-and-route tools, compilers, debuggers, profilers, emulators, libraries,
  or other utilities are useful. The tools listed by `./lab/status` are the
  starting inventory, not a restriction. Prefer reproducible local, container,
  or virtual-machine installs for fragile dependencies, and record versions and
  installation choices in experiment notes.
- Use web search and other internet research whenever the work needs it. Look
  up architecture details, DOOM internals, tool documentation, standards,
  papers, and implementation techniques rather than relying on uncertain
  memory. Record important URLs, paper identifiers, repository revisions, and
  the fact being verified in `workspace/docs/` or the relevant run artifact.
- The lab does not impose artificial limits on reasoning, iterations, number of
  experiments, or research. Physical host limits and the eventual artifact's
  constraints are separate from the agent's freedom to explore.

## Evidence is the testing contract

Testing and conclusions must never be based on assumptions, intention, visual
impressions, screenshots, or candidate-reported success alone. Ground every
claim in observable, reproducible evidence:

- run the real command or test and retain its exit status and stdout/stderr;
- inspect generated binaries, waveforms, traces, memory contents, synthesis
  reports, timing results, counters, or other artifacts where relevant;
- compare outputs against an explicit test vector or trusted oracle;
- repeat important measurements when determinism matters; and
- distinguish measured facts, inferred explanations, hypotheses, and unknowns.

If a metric cannot actually be measured, report it as unavailable or `null`
and explain why. Never fabricate a value, silently skip a failed check, or call
an unbuilt or unexecuted design correct. Preserve failed experiments so that
they remain useful evidence.

## Repository and trust boundary

Work primarily in `workspace/`. Use `./lab/status` to discover capabilities and
`./lab/evaluate` for the machine-verifiable benchmark. Keep `lab/` and
`ground_truth/` read-only; they contain the protected evaluator, reference,
oracle, and correctness rules. Record source changes with Git commits and
associate results with their run IDs. Do not expose credentials, private keys,
or unrelated personal data to tools, logs, or experiment artifacts. Use Docker,
a VM, or a separate disposable environment when running code that should not
be trusted with the host.

