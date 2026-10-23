# Experiment plan: unrestricted GF(16) multiplication

Revision 1, 2026-10-23. This is an open mathematical research experiment,
separate from the completed [AES simulation baseline](../aes-256-gcm/RESULTS.md).
The [generated current status](STATUS.md) distinguishes completed commands,
verified results, missing audits, and publication. Historical evidence remains
under its original AES paths and experiment IDs; do not relabel old attempts.

## Exact question

Determine the unrestricted XOR-AND multiplicative complexity of
`(a,b) -> a*b mod (t^4+t+1)`, with eight Boolean inputs and four outputs.
XOR, NOT, constants, and affine output corrections are free. An AND may use
any affine combination of the original inputs and earlier AND outputs.
Boolean idempotence is part of the model: nonlinear intermediate wires and
high-degree cancellation must not be excluded by assumption.

The reference encoding is the polynomial basis, least significant bit first,
with reduction polynomial `0x13`. Every positive full multiplier is compared
with an independent carryless-product/reduction oracle on all 256 inputs.
Changing coordinates is allowed, but the whole target and every available
wire must move together. An equivalent scalar alone does not preserve an
arbitrary continuation.

## What counts as a result

An eight-AND witness must compute all four exact outputs, not merely one
rank-eight scalar or a pair of bent forms. A nine-AND lower bound must cover
all unrestricted eight-AND circuits through an explicit complete case tree,
with the semantic reductions reviewed and every necessary finite certificate
independently checked. A local branch exclusion is a legitimate intermediate
result but does not complete this experiment.

AND count is not chip area, frequency, energy, an improved complete AES
circuit, or leakage resistance. Any hardware transfer needs its own named
target, workload, synthesis/implementation constraints, and measured result.
Physical metrics remain null until that work exists. Neither a branch closure
nor an unsuccessful web search establishes a world first.

## Dependency and remaining-case map

`r_i` means rank of the raw operand covectors through gate `i` in the reviewed
normal form, not dimension of the whole wire space. The map below is a research
index under the named reductions, not a machine-checked global proof.

- [Quadratic nine-AND bound](../aes-256-gcm/GF16_QUADRATIC_BOUND.md):
  restricted-model result and flattening dependency, not the unrestricted
  conclusion.
- [Early-target exclusion](../aes-256-gcm/GF16_EARLY_SCALAR_BOUND.md):
  the Q-by-four branch is excluded under its reviewed dependencies. The
  self-contained saturation lemma in the later quintic note supersedes the
  historical imported strong-theorem dependency.
- [Five-gate normal form](../aes-256-gcm/GF16_FIVE_GATE_INPUT_NORMAL_FORM.md):
  all ten raw forms span eight dimensions; first-four raw rank is six, seven,
  or eight. Its old UNKNOWN solver outcome remains historical evidence.
- [Quintic branch](../aes-256-gcm/GF16_QUINTIC_PREFIX_BOUND.md):
  complete rank-seven/eight replays plus the rank-six argument exclude a
  degree-five fourth wire in the scoped first-target-at-five problem.
- [Nonquintic frontiers](../aes-256-gcm/GF16_QUARTIC_PREFIX_FRONTIER.md):
  the all-quadratic-first-four branch has its own field argument. For
  `r4=6,r3=6`, all 6,120 lifted spaces and 6,552 scalar marks have complete
  producer/checker comparisons supporting that conditional branch exclusion.
  For `r4=8`, the 203,728-state producer and independent scan have terminated;
  only a successful final per-case audit permits promoting their numerical
  result to a verified branch exclusion. Consult generated status for that
  audit's current outcome, not an old document's “running” checkpoint.
- Remaining `r4=6,r3=4` and `r4=6,r3=5` cases: open. A two-fresh-variable
  peel is a possible reduction in the former; the one-fresh case forces only
  one factor affine and must still allow a nonlinear other factor. These are
  leads, not completed coverage.
- Remaining `r4=7` case: open. Preserve the one-fresh-variable nonlinear
  factor, all old wires, constants/output shifts, and every scalar mark.

Any positive necessary-condition survivor still needs full target compatibility
and a complete suffix. Conversely a negative scan excludes only the cases
proved to reduce to its exact inventory. Reconcile the entire dependency tree
before making a global claim; never infer completion from a checklist alone.

## Prior-art checkpoint before major campaigns

Use [the dated research ledger](RESEARCH.md) and [machine ledger](PRIOR_ART.json).
Before launching a major new campaign, record the precise proposed claim,
circuit model, map, source/input revisions, and what a positive or negative
answer changes next. Search primary papers, author repositories, and official
circuit collections for that claim and its closest variants. Record queries,
retrieval dates, versions/sections, verified facts, missing artifacts, and
differences from the closest result. Follow citations when a relevant claim
rests on an older result; inaccessible originals remain a limitation.

Classify the proposed contribution as known, reproduction, possibly new, or
unverified. Reproducing a result may still be valuable if it verifies a needed
dependency or improves portability; say so rather than renaming it novel.
Refresh this comparison before publication and before novelty claims. Search
absence is not a priority proof, and an author's statement is not an
independently replayed theorem.

## Campaign and finalization contract

Freeze coverage and source/input/binary identities before launch. Retain actual
argv, compiler flags/versions, command exits, stdout/stderr, and failures. Keep
producer and independent mathematical algorithms distinct; share only capture,
state, hashing, and audit plumbing where appropriate.

The dependency chain is execution, independent replay, exact coverage/per-case
audit, verified result, then regenerated short status. A scan terminating with
zero exit is not the final audit. Resume may reuse only validated completed
stages; a changed input or missing/truncated output must invalidate reuse or
fail explicitly. A generated status reports artifact evidence, not an agent's
optimistic interpretation. Publication remains a separate action.

Controls must include a real positive circuit, negative/malformed data,
truncation or altered hashes, interrupted execution/resume, and an actual
command failure. Evaluate workflow changes against these controls and retain
their real outcomes; do not assume that a new process improves reliability.
Same-team independent algorithms are not external peer review or formalization.

## Continue, pivot, and completion decisions

At each milestone, record the remaining cases, next falsifiable question,
expected decision value, observed compute cost, and whether primary literature
already answers it. Continue when the next campaign closes a necessary gap or
tests a credible construction. Revise the reduction or pivot when controls
invalidate coverage, the next search has no actionable decision, or a primary
result makes the proposed contribution redundant. Preserve the failed approach
and explain the replacement. No arbitrary research-wide time cap is imposed.

The initial decision is continue: finish auditing already-computed evidence
before launching another large scan, then select a remaining rank-six/seven
case using a recorded prior-art and coverage review. A pivot is not a proof of
the original claim. Experiment completion requires the positive-solution or
negative-solution gate in `experiment.json`; novelty remains a separate review.
