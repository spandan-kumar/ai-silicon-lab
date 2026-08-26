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

