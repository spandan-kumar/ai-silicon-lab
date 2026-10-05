# Experiment 002: AES-256-GCM — progress and research handoff

Last updated: **2026-10-05**. Work is on
[`codex/experiment-2-crypto-algo`](https://github.com/spandan-kumar/ai-silicon-lab/tree/codex/experiment-2-crypto-algo).
This is a progress snapshot, not a claim of a world-first chip or algorithm.

## Where we are now

We have a working, synthesizable AES-256-GCM accelerator and a measured
architecture comparison. The later research asks whether we can improve the
AES S-box's nonlinear circuit beyond pinned public examples. That research
has produced verified restricted impossibility results and unsuccessful
constructive searches, **not a new record-setting AES circuit**.

- **Completed baseline:** eight RTL organizations pass the recorded algorithm,
  interface and synthesis gates. One mapped standard-cell netlist passes the
  same 1,038-operation GCM corpus. See [the implementation results](RESULTS.md),
  [frozen profile](PROFILE.md) and [workspace reproduction guide](../../workspace/aes-256-gcm/README.md).
- **Latest fixed-prefix result:** 131,833 distinct one-auxiliary target
  envelopes are conditionally excluded. This covers all 148 stored
  two-product prefixes in the tested families. It does not exclude arbitrary
  AES circuits or changed prefixes.
- **Latest depth-three result:** 736 rank-eligible terminal replacement windows
  of sizes three through five are excluded across four pinned public sources.
  Six larger, surplus-rank windows remain only partially investigated.
- **No verified breakthrough yet:** no correct 27-AND AES S-box, no correct
  34-AND AND-depth-three S-box, and no global AES lower bound have been found.
- **Physical status:** no placed/routed implementation, board measurement,
  power/energy measurement or physical leakage certification is available.

The experiment manifest's `complete` status refers to the frozen accelerator
baseline. It does **not** mean the open-ended novelty goal has been achieved.
At this publication checkpoint the reported scans and bounded probes are
terminal; no future result is assumed.

## What we tried

| Direction | What was tested | Outcome and boundary |
|---|---|---|
| AES/GHASH architecture balance | Eight organizations vary AES rounds and GHASH width under the same interface, corpus and mapping constraints. | A one-round/32-bit-GHASH design improves the recorded pre-layout area/latency tradeoff over the two-round/8-bit point. This is a measured engineering result, not established novelty. |
| Karatsuba and AES/GHASH overlap | Two-stage GHASH multiplication and overlapping block schedules, including encrypt/decrypt variants. | Reproducible exploratory implementations exist. A later review corrected raw output-port exposures; the hardened report supersedes preliminary rankings. |
| Masked S-box scheduling | Exact alignment-register scheduling and mapped comparisons of public circuits. | The eight tested 29-AND circuits do not beat the equally optimized classic circuit in both mapped area and delay. Randomness cost is a separate tradeoff; physical leakage is not inferred. |
| Affine/XOR and self-equivalence search | Boundary changes and complete finite sweeps around existing S-box circuits. | Local improvements and negative searches were recorded, but the apparent 29-AND reduction is dominated by public prior art. No world-first claim survives that comparison. |
| Nonlinear stage splicing | Attempted a 9+5+13-AND construction with fixed public outer stages and tail operand functions. | It does not compute all AES outputs. Exact truth-space analysis requires at least six middle ANDs for the three tested fixed interfaces; other interfaces remain open. |
| Local repair and retained-gate windows | Cone, pair, triple, radius-limited and auxiliary searches around pinned designs. | Scoped exact exclusions and inconclusive solver timeouts were retained. They are not global AES optimality proofs. |
| Two-product prefixes | Enumerated attainable envelopes in finite factor families, then tested their continuations. | 148 distinct stored envelopes were found. The latest closure campaign conditionally excludes every one, including apparent positives that were independently identified as known constructions. |
| Minimum-AND-depth-three replacements | Replace terminal gates of four public 35-AND sources while preserving their earlier nonlinear gates. | Sixteen direct necessary-product probes return UNSAT; exact envelope and depth-refactoring analysis extends the result to 736 rank-eligible size-3/4/5 windows. |
| Six-terminal escape | Allow one surplus signal: one new depth-two auxiliary followed by four depth-three products. | A finite family of 2,544 auxiliary/window rectangles, covering 5,207,568 left forms, finds no useful target direction. Three unrestricted fixed-auxiliary probes return UNSAT. Three joint unrestricted-auxiliary probes time out and remain inconclusive. |

The detailed historical record is [RESEARCH.md](RESEARCH.md). The working RTL
has not been replaced by any unsuccessful S-box candidate.

## The latest closure result, precisely

In this search, XOR and NOT are affine operations; an AND adds at most one
independent truth function. Counts in this section are Boolean-circuit
metrics, not synthesized cell area or clock frequency.

We fix eighteen retained AND gates. Their available affine truth space `W`
has dimension 27; adding the eight AES output functions gives `T` of dimension
35. A single independent auxiliary direction `q` outside `T` defines the
36-dimensional target envelope `S = T + q`.

Three tested auxiliary quotient spans have dimensions 17, 8 and 9. Complete
product scans, plus independently checked closed superspaces for their few
exceptional directions, show that starting from `W` cannot produce all AES
outputs while every intermediate stays in the corresponding `S`.

The original auxiliary was the last unfinished exception. Its warm available
space has dimension 33. The exact search exhausted all **2,147,483,647**
nonzero left forms in a complete factor-plane-normalizing hyperplane, split
into 32 disjoint batches; every process exited successfully and found no
useful extension. Independent review checked the partition, all input-matrix
entries, small exhaustive controls and terminal records. The large scan was
not independently repeated.

After counting intersections rather than double-counting overlaps, the three
quotient spans cover **131,833 distinct final `S` envelopes**. All **148 stored
two-product prefixes** have their actual gates replayed and are covered.
For a 27-AND completion preserving these eighteen gates, the nine remaining
gates allow at most nine new dimensions. If such a completion uses one of
these outside-`T` directions, its final span must be exactly `S`; the closure
barrier therefore rules it out.

This result leaves other auxiliary classes, a changed retained prefix and
other nonlinear organizations open. In particular, it is not a proof that
AES requires 28 ANDs globally. The induction argument can prohibit arbitrarily
long circuits constrained to the same `S`; it does not prohibit circuits
that leave `S`.

## Depth-three searches: what remains open

“AND depth three” means at most three dependent AND operations on an output
path; XOR depth and physical timing are different metrics.

For the rank-tight size-3/4/5 replacements, every useful new signal must lie
inside the unchanged target envelope. Exact span intersections show that a
new depth-at-most-two product there cannot add rank. Therefore useful new
products must be parallel depth-three gates, and the necessary-product UNSAT
results apply. No formal UNSAT proof certificate was checked; the retained
solver results have positive controls, independently reconstructed encodings
and truth-space checks.

Six-terminal replacements have a surplus dimension, so the preceding
argument does not settle them. We tested 424 distinct restricted-factor
auxiliary implementations in each of six windows. Their factors come from
basis pairs or one-signal perturbations of actual source gates. Enumeration
is exact inside each rectangle, but choosing this auxiliary/factor family is
a restriction, not a complete search of all circuits.

The broader joint solver chooses an unrestricted depth-two auxiliary and a
first useful depth-three product simultaneously. All three 120-second probes
returned `INDETERMINATE`, with exit status 15. Their 24 small exhaustive
solver controls and three source-product positive controls pass; those
timeouts establish no negative result. Independent review of this newest
joint encoding was not completed at this checkpoint.

Promising unclosed questions are:

1. Unrestricted auxiliary choices and full factor spaces in the surplus-rank
   windows, with stronger exact reasoning or a better solver encoding.
2. Five parallel new depth-three products whose span has an outside-target
   direction, **without** adding a new depth-two auxiliary. This is a separate
   branch and is not excluded by the joint-auxiliary architecture.
3. Changed early/middle gates or a materially different nonlinear
   construction, rather than another variation of an already closed prefix.
4. Target-specific implementation and physical measurements if a genuinely
   new complete circuit passes the independent oracle.

Any prospective candidate must be materialized as actual gates, checked on
all 256 S-box inputs, recounted for AND number/depth and compared with current
primary-source prior art before a novelty claim is made.

## Sources and novelty checks

Primary web sources were checked again on 2026-10-05:

- [NIST circuit table](https://csrc.nist.gov/projects/circuit-complexity/list-of-circuits)
  and [AES source inventory](https://raw.githubusercontent.com/usnistgov/Circuits/master/data/slp/aes/aes-sbox/README.md).
  The pinned source revision is `b402f09ee22fd26cc58a2904bf5bd524fcd0cbcc`.
  Selected public 28-AND and 35-AND depth-three examples are prior art, not ours.
- [SAT-based multiplicative-complexity synthesis](https://arxiv.org/abs/2005.01778)
  and [the explicit 29-AND construction](https://umizame.github.io/S-box_29-AND/)
  establish relevant prior work.

The NIST table is a selected inventory, not an exhaustive literature survey
or an optimality proof. Failing to find a competing result on the web does not
establish novelty. The elementary linear-algebra reductions used here are
not claimed as a new general synthesis method.

## Evidence and reproduction

Committed evidence and entry points include:

- [Baseline results](RESULTS.md), [machine-readable architecture report](../../workspace/aes-256-gcm/reports/results.json)
  and [hardened overlap report](../../workspace/aes-256-gcm/reports/dual_overlap_hardened.json).
- [Masked scheduling study](../../workspace/aes-256-gcm/reports/masked_sbox_schedule_study.json),
  [self-equivalence study](../../workspace/aes-256-gcm/reports/sbox_self_equivalence_study.json)
  and [stage-splice study](../../workspace/aes-256-gcm/reports/sbox_stage_splice_study.json).
- [Local repair study](../../workspace/aes-256-gcm/reports/sbox_local_barrier_study.json),
  [fixed-window study](../../workspace/aes-256-gcm/reports/sbox_tight_window_study.json),
  [two-prefix study](../../workspace/aes-256-gcm/reports/sbox_two_prefix_study.json)
  and [complete envelope enumeration](../../workspace/aes-256-gcm/reports/sbox_envelope_image_study.json).
- [Latest shared-family/depth-three evidence summary](../../workspace/aes-256-gcm/reports/sbox_shared_family_study.json),
  including input columns, artifact hashes, exact scope and terminal outcomes.
- [Retained enumeration tool](../../workspace/aes-256-gcm/tools/enumerate_two_and_envelopes.py)
  and the [workspace guide](../../workspace/aes-256-gcm/README.md) for commands.

Raw run-local programs, solver encodings, stdout/stderr, matrix inputs and run
records remain under ignored `runs/` directories on the research machine;
**those large raw artifacts are not included in this GitHub push**. The
committed summaries identify them and retain hashes, but are not substitutes
for the complete raw archive when independently replaying the latest scans.

The latest search-tool checkpoint passes 13 regression tests and the registry
and protected-lab status checks. These documentation changes do not rerun the
entire accelerator corpus or create new hardware measurements. Per-attempt
model identity, token usage, reasoning mode and cost are unavailable where
the harness does not expose them; they remain null rather than guessed.
