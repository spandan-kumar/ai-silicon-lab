# Security boundary

This workspace is an experimental sandbox, not a hardened multi-tenant
system.

## Protected state

`lab/` and `ground_truth/` contain the evaluator, reference execution, input
schedule, asset, oracle, and trust manifest. On this macOS host they are
protected with the filesystem `uchg` flag and are also non-writable by normal
permissions. The evaluator verifies the recorded SHA-256 values before and
after every run. A tamper or missing file produces an integrity failure.

The protection applies to normal workspace operation. An administrator who
deliberately clears filesystem flags can still maintain the laboratory; that
maintenance action must be treated as a new trusted setup and followed by a
new validation run.

## Agent scope

The future agent should work in `workspace/`, create experiment artifacts in
`runs/` and `results/`, and use the immutable lab as a read-only service. No
credentials, SSH keys, API keys, or unrelated personal files are copied into
the repository or evaluation logs. Environment variables are reduced to a
small execution environment before candidate processes start.

Candidate commands run on the host by default and may execute arbitrary code
with the current user's permissions. For an untrusted agent, use Docker,
Apple Virtualization, or a separate disposable account/machine, and pass only
the candidate workspace and required read-only inputs into that environment.
The repository does not attempt to claim that host execution is a security
boundary.

## Trusted maintenance

Changes to a protected tool are a lab maintenance operation. Preserve the
starting trusted manifest and restrict the edit to the intended files. Before
refreshing the manifest, run `python3 tools/verify_trusted.py --json` and inspect
every mismatch. Regenerate SHA-256 values for the complete set of tracked
files under `lab/` and `ground_truth/`, excluding the manifest itself. Review
the resulting manifest diff; it must match the intended maintenance scope.

Run the full lab validation after a trusted change:

```sh
python3 -m unittest discover -s tools -p 'test_*.py' -v
python3 -m unittest discover -s workspace/verification -p 'test_*.py' -v
./tools/experiment --json check
python3 tools/verify_trusted.py --json
./lab/protect --apply
./lab/status --json
./lab/evaluate --self-test known-good
./lab/evaluate --self-test broken
```

The known-good fixture must pass with 120 exact frames. The broken fixture must
exit 1 specifically for a frame-comparison failure; an unrelated failure does
not validate rejection. Both must preserve trusted-file integrity. Commit the
new trusted state, retain a clean-commit known-good run, and use
`./lab/reproduce <run-id>` to verify it in a detached worktree. Protect that
worktree's lab files too. Retain commands, return codes, logs, and result hashes,
including failures encountered while developing the maintenance.

The portable CI integrity check also rejects tracked protected files omitted
from the manifest. A manifest and source changed together can still agree;
review of trusted changes remains necessary. The manifest is never regenerated
automatically by CI or a normal evaluation.
