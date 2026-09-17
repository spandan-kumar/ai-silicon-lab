# Evidence validation maintenance — 2026-09-17

The lab's central contract is freedom to explore hardware designs backed by
reproducible evidence. Its experiment, agent, and implementation identities
must stay distinct for meaningful comparisons. This change strengthens the
shared provenance tools used by the Doom baseline and future experiments.

The branch `codex/strengthen-experiment-evidence` starts at main commit
`b9beb9f5a97c6706ccb04c33f017134c3d283c0b`. Implementation commit
`fdcceb7abcc29fc07360a970dac038b48ac39f84` contains the validator, tests, and
schema documentation. The separate worktree preserves the existing AES branch
and its unfinished changes.

## Reproduced defects and changes

The original validator accepted a numeric value marked `unavailable`, an
`exact` model identity with no canonical ID, and boolean `true` as schema
version 1. Object or array status/source values raised `TypeError` instead of
returning a validation result. Duplicate JSON keys silently replaced earlier
values, and large exponents could decode to infinity.

The validator now rejects those inputs, blank experiment revisions, and
missing token-accounting fields. An explicitly empty set of known experiments
rejects every experiment ID. Unknown telemetry remains explicit `null` with
a source note, and known zero values remain valid. JSON Schemas document the
identity and measurement rules. Existing manifests and example records pass.

## Executed evidence

| Check | Observed result |
| --- | --- |
| Regression suite against original validator | Exit 1; 27 failures and 14 errors across 14 methods, including subtests |
| Final unit suite, Python 3.9.6 | 17 methods pass |
| Final unit suite, Python 3.14.7 | 17 methods pass |
| Independent JSON Schema check, jsonschema 4.25.1 | Both schemas valid; two manifests valid; 45 valid/invalid record cases match expectations |
| Registry and existing examples | Pass |
| Lab health after applying filesystem protection | Pass; 236 protected files verified |
| Known-good evaluator self-test at clean implementation commit | Pass; 120 frames, zero frame error |
| Broken evaluator self-test at clean implementation commit | Expected exit 1; frame comparison failed |

The unit suite includes malformed input through the actual CLI from a different
working directory, with spaces in the record path. The standard CLI and tests
require only Python's standard library. The independent schema check used an
isolated, ignored virtual environment.

The [run record](records/2026-09-17-evidence-validator.json) pins source hashes,
command exit statuses, timings, log hashes, and attribution. Raw logs and
reproduction scripts are retained locally in
`runs/evidence-validation-maintenance/`; evaluator artifacts are in
`runs/evidence-validator-committed-known-good/` and
`runs/evidence-validator-committed-broken/`. These generated directories are
ignored by Git. Earlier failing checks and pre-commit fixture runs are retained.

Reproduce the main checks from this branch:

```sh
python3 -m unittest discover -s tools -p 'test_*.py' -v
./tools/experiment --json check
./tools/experiment --json validate-run experiments/doom-rv32imc/records/2026-09-17-evidence-validator.json
./lab/status --json
./lab/evaluate --self-test known-good
./lab/evaluate --self-test broken  # expected exit 1: frame comparison failed
```

The evaluator runs above are fixture checks using the native reference and an
intentionally incorrect frame producer. No candidate RTL performance, area,
physical result, or new simulation-complete claim is made by this maintenance.
The protected evaluator and ground truth contents are unchanged.

## Follow-up found during this work

`./lab/trace --run-id evidence-trace-probe --label should-fail -- /usr/bin/false`
returned 0 and created no run directory. Inspection shows that
`lab/trace_command.py` defines `main()` but never invokes it. This pre-existing
protected-tool defect remains open. Its repair should include an entrypoint,
correct start-time capture, tests of child exit-status/log retention, a trusted
manifest refresh, full lab validation, and renewed filesystem protection.

For this change, an explicit subprocess capture script recorded the commands
and their stdout/stderr instead. Its source and hash are retained with the run.
