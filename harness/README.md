# Autonomous research harness

`lab/evaluate` is the protected Doom judge and stays exactly that. This
directory is the experiment-agnostic layer around it: a way to take any
experiment in `experiments/` from a written specification to executed,
compared, gated, and recorded evidence without a human driving each step.

```sh
./harness/aisl experiments              # what exists and what is wired
./harness/aisl env aes-256-gcm          # does this host have what the experiment needs
./harness/aisl verify aes-256-gcm       # build, reference, execute, compare
./harness/aisl gate aes-256-gcm         # join gate criteria to check results
./harness/aisl record aes-256-gcm       # emit and validate a provenance run record
./harness/aisl loop status aes-256-gcm  # where the experiment stands
./harness/aisl loop step aes-256-gcm    # one iteration, stopping at the phase boundary
./harness/aisl loop approve aes-256-gcm PHASE --approver NAME
```

Self-tests:

```sh
python3 -m unittest discover -s harness -p 'test_*.py'
```

## What the layer is for

The repository already had the hard parts of a trustworthy benchmark: a
protected oracle, exact comparison, integrity hashing, and a provenance schema.
What it did not have was a way to reuse any of that for a second experiment.
`EXPERIMENTS.md` says a new experiment "must provide its own candidate adapter,
oracle or vectors, and metrics" — this layer is what makes that a small amount
of experiment-specific code rather than a second laboratory.

## The trust boundary is structural

The property that makes an oracle worth anything is that the design under test
cannot see it. Here that is enforced by the shape of the API, not by a rule in
a document:

- `reference()` receives a `Context` with `oracle_dir` set.
- `execute()` receives `context.candidate_view()`, whose `oracle_dir` is
  `None`. The runner asserts this before every execution.
- Comparison runs in the harness after the candidate process has exited, over
  files on disk.

A comparator that checked nothing fails rather than reporting success, so a
missing reference or an empty output directory cannot masquerade as a pass.

## Unevaluated is not passed

`experiment.json` states gate criteria in prose, because a criterion is a
promise to a human reader. `harness.json` maps each criterion to the check IDs
that would demonstrate it. A criterion with no mapped checks, or whose checks
did not run, is **unevaluated**, and one unevaluated criterion makes its whole
gate unevaluated.

This is the single most important behaviour in the layer. The AES baseline
passes every automated check it has, and its `simulation-complete` gate still
reports unevaluated, because one criterion — that unknown metrics and security
limitations are honestly labelled — is a human judgement that no script should
claim to have made. Crossing that boundary requires a recorded approval, and
approving an unevaluated phase requires an explicit `--override` that is stored
in the state file as an override.

An approval is bound to the run ID and a digest of the evidence it was granted
against. Change the candidate and the approval goes inactive, so a stale
approval cannot carry a new design past a gate it never faced. The digest
covers checks, candidate identity, and commit, but not wall time, so a rerun
that is merely slower does not invalidate a human decision.

## Adding an experiment

Add `experiments/<id>/harness.json` and a plugin module:

```json
{
  "schema_version": 1,
  "experiment_id": "<id>",
  "plugin": "workspace/<id>/harness_plugin.py",
  "requirements": { "required": ["verilator"], "optional": ["yosys"] },
  "suites": [ { "workload": "<workload-id>" } ],
  "gates": { "<gate-id>": { "criteria": [
      { "criterion": "<exact text from experiment.json>", "checks": ["suite:<workload-id>"] }
  ] } },
  "phase_gates": { "<phase-id>": ["<gate-id>"] }
}
```

The plugin subclasses `ExperimentPlugin` and implements `describe`,
`workloads`, `build`, `reference`, and `execute`, plus optional `lint`,
`synthesize`, and `policy_checks`. Criterion text must match `experiment.json`
exactly; a criterion the manifest does not mention stays unevaluated, which is
the intended failure mode for incomplete wiring.

`harness.json` is deliberately separate from `experiment.json` so that changing
how the repository runs an experiment never looks like changing what the
experiment promised.

## Check IDs

| ID | Meaning |
| --- | --- |
| `build` | The candidate built |
| `tool:lint`, `tool:synthesize` | Optional hooks; unevaluated when the plugin returns nothing |
| `reference:<workload>` | The reference produced artifacts |
| `execute:<workload>` | The candidate ran to completion |
| `suite:<workload>` | Candidate output matched the reference |
| `determinism:<workload>` | Repeated executions were byte-identical (only when `repeat > 1`) |
| `policy:<id>` | An experiment-specific forbidden-shortcut check |

## Comparators

| Name | Use |
| --- | --- |
| `exact-bytes` | Every reference artifact must exist and match byte for byte |
| `vectors` | `vectors.json` matched by case ID, never by position |
| `digest` | Whole-directory digest, for large opaque artifact sets |

Determinism is separate: it re-runs the candidate and requires identical
output, rather than trusting that a design is deterministic because it should
be.

## Provenance

`harness/aisl record` builds a run record from the verification report and
validates it with the repository's own `./tools/experiment validate-run`. Build
and simulation time are measured and separated. Agent tokens, cost, agent wall
time, and hardware time are `null` with a source note, because this harness
does not receive that telemetry; supply it through the `AISL_AGENT_*`
environment variables rather than inferring it:

```sh
export AISL_AGENT_PROVIDER=... AISL_AGENT_CANONICAL_ID=... AISL_AGENT_HARNESS=...
```

Without a canonical model ID the record carries `identity_status: alias-only`,
matching the schema's rule that a readable alias is not a reproducible
identity.

## What this layer does not do

- It does not replace or weaken `lab/evaluate`. Doom's oracle is untouched.
- It never writes inside `lab/` or `ground_truth/`; that is asserted in code.
- It cannot judge a criterion no one wrote a check for, and it does not pretend
  otherwise.
- It has no opinion on whether a design is good. It reports what was measured
  and what was not.
