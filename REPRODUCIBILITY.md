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

The reference source, asset source tag, checksums, compiler inputs, and host
snapshot are recorded under `ground_truth/` and `docs/ENVIRONMENT.md`. The
reference IWAD and frame archive are included so a normal evaluation does not
depend on a live download. Rebuilding the reference engine on another host is
supported by `ground_truth/reference/Makefile`; a platform-specific prebuilt
binary is included only as a convenience for this host.

