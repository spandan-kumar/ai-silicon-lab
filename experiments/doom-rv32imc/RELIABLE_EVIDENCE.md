# Reliable command and artifact evidence — 2026-09-17

Implementation commit: `adf5cf7b5b49510093e445f487af88e3f82a36a0`, on
`codex/reliable-lab-evidence`, based on main `6eb6988`.

## Changes

`lab/trace` now executes its command and propagates failure. Its start and
finish timestamps enclose the child process. Each attempt retains separate
stdout, stderr, and command metadata, including repeated labels and concurrent
commands. The shared index uses a Unix file lock and atomic replacement.
Launch failures and signal exits are recorded, and a damaged index is preserved
instead of being overwritten. This resolves the tracing defect documented in
[the first maintenance report](EVIDENCE_VALIDATION.md).

`tools/experiment validate-run --verify-evidence` checks file-backed evidence
against recorded SHA-256 values. Missing files or hashes, altered contents,
non-regular files, and paths escaping the repository fail. Null-path reports
remain unverified. Normal structural validation still works without historical
run artifacts; `check` now includes saved records as well as examples.

The [Lab checks workflow](../../.github/workflows/lab-checks.yml) runs the
tooling tests, comparator tests, registry validation, and protected-file checks
on pushes and pull requests, using Python 3.9 and 3.14. The integrity checker
also detects tracked protected files omitted from the manifest. CI does not
regenerate the manifest or change the trusted reference.

## Measured validation

| Check | Result |
| --- | --- |
| Original trace regression suite | 7 methods; failed with 7 assertion failures and 2 errors across subtests |
| Repaired trace regression suite | All 7 methods pass |
| Tooling suite on macOS, Python 3.9.6 and 3.14.7 | All 38 methods pass on each |
| Exact-frame comparator suite, macOS Python 3.9.6 | All 5 methods pass |
| Linux container, Python 3.14.7 | All 38 tooling and 5 comparator methods pass; registry and integrity checks pass |
| Workflow static check, actionlint 1.7.12 | Pass |
| Independent schema check, jsonschema 4.25.1 | Both schemas valid, both manifests valid, 45 record cases match expectations |
| Previous maintenance record, with file verification enabled | All 19 evidence files match their hashes |
| Original manifest checked after the intentional trace edit | Expected failure, naming only `lab/trace_command.py` |
| Regenerated manifest and local lab health | Pass; all 236 protected files verified and protection restored |
| Clean-commit known-good evaluator fixture | Pass; 120 exact frames, zero frame error |
| Clean-commit broken evaluator fixture | Expected exit 1, specifically frame comparison failed |
| Detached clean-commit known-good reproduction | Pass; 120 exact frames; protection applied to the reproduction worktree |
| Direct `/usr/bin/false` through repaired `lab/trace` | Expected exit 1 with retained command metadata |

The [run record](records/2026-09-17-reliable-lab-evidence.json) retains model and
harness attribution, explicit unavailable telemetry, source hashes, and hashes
for command records, logs, snapshots, and evaluator results. Raw artifacts are
under `runs/reliable-lab-evidence/`, plus the named evaluator and detached
reproduction directories. They remain local and Git-ignored. The original
failing tests and pre-refresh integrity failure are preserved.

Only `lab/trace_command.py` changed among protected implementation files. The
manifest was regenerated over all 236 existing tracked protected files and
reviewed: only that file's digest changed. Evaluator logic, benchmark inputs,
assets, and oracle bytes are unchanged.

## Reproduction and limits

```sh
python3 tools/verify_trusted.py --json
python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 -m unittest discover -s workspace/verification -p 'test_*.py' -v
./tools/experiment --json check
./tools/experiment --json validate-run experiments/doom-rv32imc/records/2026-09-17-reliable-lab-evidence.json --verify-evidence
```

The final command requires the retained local artifacts and recorded checkout.
Trace-specific files are independently retained per attempt; the aggregate
index can grow without changing earlier evidence. Artifact hashes establish
file identity, not hardware correctness. No new candidate RTL, synthesis, or
physical-hardware result is claimed here.

The Linux run used a read-only tar snapshot of the checkout in a disposable
container with networking disabled. Its digest and command output are retained.
It exercised the workflow's four check commands, not GitHub's hosted services.
The branch has not been pushed and there is no hosted CI run to claim.

## Tool sources

The workflow follows the official [checkout](https://github.com/actions/checkout)
and [setup-python](https://github.com/actions/setup-python) usage documentation.
Their v6 refs were resolved with `git ls-remote` and pinned to
`d23441a48e516b6c34aea4fa41551a30e30af803` and
`ece7cb06caefa5fff74198d8649806c4678c61a1`, respectively. Credentials are not
persisted by checkout. [actionlint](https://github.com/rhysd/actionlint) 1.7.12
was built locally with Go into ignored run storage for workflow validation.
The CLI and normal unit suites add no third-party runtime dependencies.
