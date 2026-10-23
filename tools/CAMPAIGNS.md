# Durable research campaigns

`campaign.py` is standard-library execution plumbing, not a theorem checker.
It runs a trusted recipe's argv stages sequentially, retains actual exits and
stdout/stderr in numbered attempts, and seals success only after the declared
independent final audit passes. The producer and checker remain separate.
It neither pushes Git changes nor schedules future agent work.

## Run and resume

```sh
python3 tools/campaign_status.py --run --recipe experiments/gf16-multiplicative-complexity/campaigns/finalize-frontier-all-inputs.json --record experiments/gf16-multiplicative-complexity/records/frontier-finalization-all-inputs-attempt-20261023.json --run-dir runs/gf16-frontier-finalization-all-inputs-20261023 --as-of 2026-10-23 --out experiments/gf16-multiplicative-complexity/STATUS.md
python3 tools/campaign.py status --recipe experiments/gf16-multiplicative-complexity/campaigns/finalize-frontier-all-inputs.json --record experiments/gf16-multiplicative-complexity/records/frontier-finalization-all-inputs-attempt-20261023.json --run-dir runs/gf16-frontier-finalization-all-inputs-20261023 --as-of 2026-10-23
```

Review the code and recipe before running it: argv is arbitrary trusted code,
not sandboxed by this runner. The run directory must be a child of `runs/`.
Use the same command to resume. The first command also regenerates the experiment
checkpoint after a successful run or recorded failure. A lock refuses a second supervisor. A stopped
supervisor does not magically reconstruct an unobserved exit: an orphaned
child must terminate or be deliberately inspected/stopped before retry. Old
attempts remain intact. SIGTERM/SIGINT are forwarded to the child process group.
No guarantee is made for power loss or a child that ignores termination.

Recipes specify schema version 1, campaign/experiment ID and revision, exact
claim, `prior_art` ledger path and review-age limit, pinned `{path,sha256}`
inputs, and ordered stages. Each stage specifies `id`, `role`
(`build`, `scan`, `replay`, `audit`), `time_kind`, argv, and declared outputs.
Paths in argv can use `{root}`, `{run}`, `{stage}`; `{stage}` is a fresh attempt
directory. Output paths are relative to that directory. JSON `equals` checks
support dotted keys. An audit must explicitly require `status: pass`.
Pin every executable source, helper, configuration and scientific input;
pinning an arbitrary unrelated file is not meaningful provenance. Toolchains
and environmental dependencies still need their own recorded identities.

The prior-art ledger must match the exact claim, contain dated queries and
primary sources with verified facts and limitations, classify novelty, and
justify continuing. `--as-of` is an explicit operator review date, not an
automatically trusted freshness oracle. The runner validates structure and
hashes, not whether a human/agent actually searched or understood a paper.
A new claim or stale review requires fresh research and a new run identity.
Archive old runs rather than editing their original recipe or provenance.

Before reuse, all declared outputs/logs and pinned inputs are rehashed. Failed
stages retry in fresh numbered attempts; successful stages are not recomputed.
Any changed identity or invalid completed evidence fails closed. A final
revalidation checks earlier outputs again before sealing. `state.json` and
`verified.json` are machine-readable; `STATUS.md` is generated, not handwritten.
Always run `status` before consuming an old seal. Integrity checks detect
accidental changes, not an adversary rewriting receipts and manifests together.

## Existing full frontier campaign

`campaigns/frontier-pairs.json` is a frozen **legacy evidence** manifest, not
the generic runner recipe. It preserves the original AES experiment IDs,
candidate revisions and actual native shard exits. `finalize-frontier.json`
invokes the portable streaming finalizer over that evidence. The final
`finalize-frontier-all-inputs.json` recipe also pins every raw artifact directly
so status/resume rehashes them; the first recipe is retained as the initial
integration checkpoint. This closes the
already-computed campaign without pretending to have rerun native scans.
The finalizer checks full TSV-to-source mapping, all cases and scalar marks,
per-case kernels/counters, and positive witnesses where present.

The scientific conclusion remains conditional on the separately reviewed
normal-form and field-target reductions. A zero scan or audit exit alone is
not a global GF(16) theorem, formal proof, external review, or novelty result.

## Raw evidence and current status

Use [artifact bundles](ARTIFACT_BUNDLES.md) for explicit large-file capture,
hash verification and restore to a fresh directory. Git contains recipes and
compact reports, not an implicit copy of ignored `runs/`. Restored binaries
are platform-specific evidence, not portable executables; recompile reviewed
source if a new native scan is needed. Restore/replay must never run code
automatically. The same recipe can finalize a reviewed restored tree using
the finalizer's `--root` option.

Experiment status is generated by `campaign_status.py` from a revalidated
run. Its evidence hashes and generation time make it a checkpoint, not a
live monitor. Re-run the generator after a new audit, failure or decision.
Chronological notes stay intact and link to this shorter checkpoint.

## Validation and sources

```sh
python3 -m unittest discover -s tools -p 'test_*.py' -v
```

Tests execute real subprocesses for success, nonzero exit, audit-verdict
failure, interruption, resume, duplicate supervisors, and corruption. Their
fixtures are explicitly not mathematical research evidence. The integration
campaign supplies the real scientific audit separately.

Design research checked 2026-10-23:

- [Snakemake official CLI](https://snakemake.readthedocs.io/en/stable/executing/cli.html):
  records provenance-based rerun triggers and incomplete-run handling. We
  adopt explicit identities and failure states, not a claim to invent a DAG
  runner; Snakemake was not installed or benchmarked here.
- [OpenAI workflow iteration](https://developers.openai.com/cookbook/examples/codex/iterating-development-workflows-with-codex):
  treats harness/context files as adaptable project conventions, not mandatory
  product behavior. We add only controls addressing observed lab failures.
- [OpenAI best practices](https://learn.chatgpt.com/docs/learn/best-practices):
  recommends practical reusable repository guidance. We keep repository rules
  concise and put detailed runner semantics here. No model capability, hidden
  setting, account limit, or system instruction was changed.

Queries: `site.developers.openai.com codex AGENTS.md instructions` and direct
fetches of the above primary documentation. A working runner demonstrates
specific reliability controls, not a measured increase in research throughput.
