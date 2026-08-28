# Experiment 001 provenance handoff

The first run was described by the user as having been performed by the model
alias `Sol` in the Codex harness at maximum reasoning effort, using about
2.6 million tokens and roughly 5.5 hours of wall time. That description is
preserved in
[`../examples/agent-run-reported.example.json`](../examples/agent-run-reported.example.json)
as a `reported` record. The combined example
[`../examples/doom-baseline-run-record.example.json`](../examples/doom-baseline-run-record.example.json)
joins that attribution to the measured evaluator run, candidate commit, input
hash, and evidence paths.

It is intentionally not presented as provider telemetry: the canonical model
identifier, harness version, exact token breakdown, start/end timestamps, and
cost were not supplied as machine-readable evidence. Until those fields are
exported or independently reconstructed, downstream comparisons must treat
them as reported metadata and must not use them to claim a measured efficiency
or cost advantage.

For every future run, write a separate run record validated by
`./tools/experiment validate-run PATH` and attach the evidence manifest. At a
minimum, preserve the experiment revision, candidate commit, model alias and
canonical identifier when available, harness/version, reasoning settings,
subagent/delegation information, token fields, wall/active/tool time, cost
fields, commands, exit status, artifact paths, and hashes. Use `null` with a
reason when a value cannot be measured; do not fill gaps with estimates unless
the record labels them as estimates.
