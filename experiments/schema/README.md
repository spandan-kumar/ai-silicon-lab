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
all six fields must be present and unknown fields remain `null`. Do not infer
hidden reasoning tokens from wall time, and do not infer cost from an unpinned
price sheet. Cost records include
their currency, source, and rate date when available.

Time is split into agent wall time, human time, build time, simulation time,
and physical-hardware time. This prevents a five-hour agent session from being
mistaken for five hours of RTL execution or five hours of human labor.

A section with `source: unavailable` must contain only `null` measurements
and a non-empty `notes` explanation. This covers token counts, time fields
ending in `_seconds` or `_hours`, and cost `amount`. Zero is a valid known
measurement, not a substitute for missing telemetry. Use `mixed` when a
section combines measured, reported, or estimated values, and explain which
source applies to each value in its notes. A partially observed section can
retain `null` for its unknown fields.

Model `identity_status` must be explicit: `exact` requires a non-empty
`canonical_id`; `alias-only` requires a non-empty `display_name` and a null
`canonical_id`; `unknown` requires a null `canonical_id`. A readable alias
must not be promoted to an exact identity without supporting harness metadata.

## Validation

```sh
./tools/experiment --json check
./tools/experiment --json validate-run path/to/run-record.json
./tools/experiment --json validate-run path/to/run-record.json --verify-evidence
python3 -m unittest discover -s tools -p 'test_*.py' -v
```

The JSON loader rejects duplicate keys at every nesting level and non-finite
numbers, including exponents that overflow the runtime's numeric range.
Malformed enum fields return validation issues instead of a traceback.
Unknown experiment IDs are rejected when validating against the registry.

`check` includes both examples and saved `experiments/*/records/**/*.json`
records. It does not require ignored run artifacts to exist in a fresh clone.

`validate-run --verify-evidence` also checks every non-null `evidence[].path`
against its `evidence[].sha256`. Paths are relative to the repository containing
the tool, regardless of the caller's working directory or record location.
Paths must identify regular files within that repository; absolute paths,
parent traversal, and symlinks resolving outside it are rejected. Hashes are
64 hexadecimal digits. Missing files, absent hashes, or mismatches fail with
exit 1 and structured issues. JSON output includes `artifacts_checked`, the
number of files successfully read and hashed, including any mismatches.

Entries with a null path describe reports without a file and remain unverified.
At least one file-backed entry is required for this option to succeed. Only
`evidence` entries are verified; command strings, source identities, and other
path fields are descriptive metadata. Use the recorded candidate checkout and
restore its run artifacts before verifying historical evidence.

The JSON Schemas describe the structural and measurement constraints.
The dependency-free CLI additionally checks registry membership, unique IDs,
and the JSON encoding itself; validate with the CLI before retaining a record.
Without `--verify-evidence`, a validation pass establishes record consistency
only. Matching file hashes establish artifact identity, not that the candidate
passed its experiment; that claim still requires the experiment's evaluator.

## Provenance privacy

Record hashes of public goals, repository instruction files, manifests, and
tool configurations when useful. Do not copy hidden system prompts, API keys,
private conversations, or unrelated personal data into the repository.
