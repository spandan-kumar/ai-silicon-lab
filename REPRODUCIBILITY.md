# Reproducibility

Every evaluation records the candidate command, benchmark identity, input
hash, trusted-file verification, Git revision, working-tree status, logs,
metrics, comparison details, and generated frames.

For a reproducible candidate result:

1. commit the candidate before evaluating it;
2. run `./lab/evaluate` and save the reported run ID;
3. keep the referenced Git revision and the protected lab files intact; and
4. run `./lab/reproduce <run-id>`.

`lab/reproduce` creates a detached Git worktree under `.aisl/reproduce/`,
checks out the recorded revision, and invokes the same evaluator there. Runs
made from a dirty or uncommitted worktree remain useful measurements but are
marked non-reproducible and are refused by the replay command until the source
state is committed.

## Experiment and agent provenance

The experiment contract is versioned separately from any candidate. A run must
identify the experiment revision, candidate commit, workload/vector corpus,
reference identity, tool versions, and artifact hashes. The agent attempt that
created the candidate is recorded separately with model/harness identity,
reasoning settings, public prompt/instruction hashes, subagents, token usage,
time, and cost where those values are exposed. Agent time, build time, RTL
simulation time, synthesis time, and physical-hardware time are different
measurements and must not be collapsed into one number.

Reported or estimated values remain labeled as such. Missing telemetry is
`null`/unavailable, not zero. This is especially important when comparing
models or harnesses: a lower token or time total only matters if the resulting
hardware quality and evidence still pass the same experiment gate.

The reference source, asset source tag, checksums, compiler inputs, and host
snapshot are recorded under `ground_truth/` and `docs/ENVIRONMENT.md`. The
reference IWAD and frame archive are included so a normal evaluation does not
depend on a live download. Rebuilding the reference engine on another host is
supported by `ground_truth/reference/Makefile`; a platform-specific prebuilt
binary is included only as a convenience for this host.
