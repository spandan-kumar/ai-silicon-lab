# AI Silicon Lab agent instructions

AI Silicon Lab is an open-ended hardware/software research laboratory. The
eventual objective is to attempt a computer capable of running DOOM; this
repository does not prescribe the computer's architecture or implementation.

This file is a freedom-and-evidence contract, not a prescribed playbook. Any
examples in this file, the user brief, or the repository are illustrative
context, not instructions to copy a particular architecture, toolchain, order
of steps, or solution. The explicit benchmark, security, licensing, and
repository-integrity requirements are binding; otherwise, reassess the
examples and choose what the evidence supports.

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
- You own the process. Design your own milestones, task decomposition,
  feedback loops, experiment strategy, and stopping criteria. Change the
  process whenever new evidence shows that another approach is better; no
  sequence in the surrounding documentation is mandatory.
- If your runtime supports subagents, parallel agents, reusable skills, or
  prompt workflows, you may create and reuse them whenever they improve the
  result. You may also build equivalent local scripts, harnesses, templates,
  or instruction files. Give delegated work a clear input/output contract and
  independently verify its output; do not create a delegation layer merely
  because an example mentions one.
- You may research agent design itself. Search for current prompting guides,
  AGENTS.md practices, evaluation methods, and tool-specific documentation when
  that could improve your process, then adapt the useful parts to this lab
  rather than cargo-culting a generic recipe.

Optimize for the best result supported by evidence, not for the shortest
workflow or the smallest patch. Within the actual runtime permissions and
legal/security boundaries, do not wait for the user to prescribe intermediate
steps, tools, roles, prompts, or delegation structure. If the runtime does not
support a desired capability, create a practical substitute or document the
limitation and continue making progress.

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
- evaluate your own prompts, subagents, and process using explicit success
  criteria when you change them; a plausible workflow is not evidence that it
  is effective.

If a metric cannot actually be measured, report it as unavailable or `null`
and explain why. Never fabricate a value, silently skip a failed check, or call
an unbuilt or unexecuted design correct. Preserve failed experiments so that
they remain useful evidence.

## Optional starting references

These are living references for improving prompts, agent workflows, and
repository instructions. They are not additional project rules, and the agent
should search for newer or more relevant primary sources when needed:

- [OpenAI prompt engineering](https://developers.openai.com/api/docs/guides/prompt-engineering)
- [OpenAI Codex `AGENTS.md` guidance](https://developers.openai.com/codex/guides/agents-md/)
- [Anthropic prompt engineering overview](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/overview)
- [`AGENTS.md` open format](https://agents.md/)

## Repository and trust boundary

You are authorized to maintain the repository as a whole: add, edit, move, or
delete files when that helps the design, tooling, documentation, experiments,
or laboratory itself. Work primarily in `workspace/` by default, but do not
treat the initial layout as permanent. Use Git deliberately so changes,
including removals, remain reviewable and reproducible.

During normal experiments keep `lab/` and `ground_truth/` read-only; they contain
the protected evaluator, reference, oracle, and correctness rules. If the lab
itself needs maintenance, you may change those roots as a trusted maintenance
operation, but then regenerate the trusted manifest, run the full validation,
reapply filesystem protection, and commit the new trusted state. Never change
the judge or ground truth merely to make a candidate pass.

Use `./lab/status` to discover capabilities and `./lab/evaluate` for the
machine-verifiable benchmark. Do not expose credentials, private keys, or
unrelated personal data to tools, logs, or experiment artifacts. Use Docker, a
VM, or a separate disposable environment when running code that should not be
trusted with the host.
