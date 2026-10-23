# Workflow change validation — 2026-10-23

Implemented the observed closure-gap fixes, not a new theorem-search algorithm.
The completed AES baseline and protected evaluator remain unchanged. The open
GF(16) question now has its own contract, dated primary-source ledger, remaining
case tree and [generated current checkpoint](STATUS.md).

## Measured outcomes

- All 22 shared-tool tests pass, including real nonzero exits, wrong audit
  verdicts, changed inputs/outputs/receipts, stale seals, later-stage mutation,
  duplicate supervisors, SIGTERM resume, and a SIGKILL orphan/restart case.
- Six finalizer tests pass with none skipped on this host: synthetic metadata,
  actual preserved-campaign preflight, wrong helper, corruption and nonzero
  terminal exits. Two existing per-case comparator tests and the two-AND/stage
  regression suites pass separately.
- All 203,728 preserved r4=8 frontier states and 207,184 scalar marks compare
  exactly, all marks negative. The first standalone final audit took 39.852 s;
  the audit through the durable runner took 40.606 s coordinator wall time.
  Exact mathematical counters agree, not timing. No native scan was rerun.
- The final all-inputs-pinned recipe ran in a fresh directory and passed again
  (35.206 s coordinator wall). Its status/resume path directly rehashes every
  raw evidence file, not just the manifest that lists them. The initial
  integration run and recipe are retained as historical checkpoints.
- An explicit 79-file bundle (334,708,114 payload bytes) was created, verified,
  restored into a fresh tree, and audited again there. The restored audit took
  43.888 s coordinator wall time and agrees on all scientific counters.
  [Archive identity and replay metadata](records/frontier-archive-20261023.json)
  record the checksum and local-only storage boundary; no raw archive upload
  is implied by committing this document.
- `./tools/experiment check`, run-record validation, local-link checks,
  `git diff --check`, and all 236 protected-file hashes pass.

Actual argv, exit status, stdout/stderr and separate command times are retained
under `runs/lab-workflow-upgrade-20261023/`. The
[completed attempt record](records/workflow-validation-final-20261023.json) preserves
source identities, subagent relationships and null/unavailable model telemetry.
The [final numerical result](records/frontier-finalization-all-inputs-result-20261023.json)
preserves every pinned scientific artifact identity. The original 16/24-minute
native scan times remain separate historical measurements, not new agent time.

## Failures found and preserved

The initial shared suite was **18/19**, not passing: opening a directory as a
binary file raised `IsADirectoryError` before the archive tool's intended
nonregular-file rejection. The descriptor is now checked/closed before wrapping.
The independent runner review also reproduced two defects: a later stage could
mutate accepted earlier output before sealing, and detected corruption left a
machine-readable pass seal. Final revalidation and retained seal invalidation
now have regression tests. Lock refusal no longer changes another live run's
status. These fixes were tested; the initial failures were not relabeled passes.

## Limits and next use

This demonstrates specific reliability controls and closes a real missing
audit. It does **not** measure a general productivity/speed/cost improvement.
Agent tokens, cost, exact model identity, build/RTL/physical time and physical
metrics remain unavailable where not exposed or measured. Primary-source
searches are structurally recorded but the runner cannot certify that someone
understood a paper. Receipts and hashes are an integrity mechanism, not a
signature or a sandbox against hostile rewrites.

Use the [single run/resume-and-status command](../../tools/CAMPAIGNS.md) for
future campaigns. Refresh prior art and record a falsifiable next decision
before another major scan. The global reduced-field question, remaining
rank-six/seven cases and novelty assessment remain open; conditional branch
audits do not establish a world first or physical AES improvement.
