# Experiment and run-record schema

The lab stores specifications and provenance as inspectable JSON. The schema
files are machine-readable documentation; `tools/experiment check` is the
repository's dependency-free validator and also enforces invariants that are
awkward to express in a portable JSON Schema implementation.

There are two different objects:

- An **experiment specification** says what is being designed, what workload
  and oracle define correctness, what measurements matter, and what must be
  true at each phase.
- An **experiment run record** says which agent/model/harness attempted it and
  which candidate, tools, measurements, and artifacts resulted.

## Measurement semantics

Every usage, time, and cost value must be labeled as one of:

- `measured`: emitted by a trusted or directly observed telemetry source;
- `reported`: supplied by a person or tool but not independently verified;
- `estimated`: calculated from an explicit method and inputs; or
- `unavailable`: represented by `null`, never by a guessed zero.

An alias such as `Sol` is useful for readability but is not a reproducible
model identity. Record the canonical model identifier when the harness exposes
it, and retain `identity_status: alias-only` when it does not. Record both
`reasoning_effort` and `reasoning_mode` because they are independent controls
when the platform exposes both.

Token accounting is deliberately split into input, cached input, cache-write,
output, reasoning, and total fields. A harness may expose only some of them;
unknown fields remain `null`. Do not infer hidden reasoning tokens from wall
time, and do not infer cost from an unpinned price sheet. Cost records include
their currency, source, and rate date when available.

Time is split into agent wall time, human time, build time, simulation time,
and physical-hardware time. This prevents a five-hour agent session from being
mistaken for five hours of RTL execution or five hours of human labor.

## Provenance privacy

Record hashes of public goals, repository instruction files, manifests, and
tool configurations when useful. Do not copy hidden system prompts, API keys,
private conversations, or unrelated personal data into the repository.
