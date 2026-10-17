# Experiment 002: AES-256-GCM — progress and research handoff

Last updated: **2026-10-18**. Work is on
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
- **Newest follow-up:** three of those larger windows have solver-reported
  exclusions of useful parallel products inside the target envelope. A
  46-factor constructive search completes across all six windows without a
  candidate; a larger 105-factor search completes for one window. Unrestricted
  five-product and auxiliary searches remain unresolved.
- **Current research step:** an exact two-product tensor-chart formulation
  passes exhaustive small controls and rules out 16 fixed-block cases in
  one chart by explicit linear contradictions. One remaining case times out;
  this is not a complete two-product or AES exclusion. Eleven forward-normalized
  public seeds form seven distinct exact function spaces in the tested input
  coordinates. A changed-prefix pilot tests 26,488 candidate states without
  finding a smaller circuit; neither result settles arbitrary new prefixes.
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
| Five parallel replacement products | Preserve all early gates and replace six terminal gates with five products, with no new depth-two auxiliary. | Three useful-inside-target product probes return UNSAT. Finite 46-factor and 105-factor searches find no complete circuit; broader full-truth and coefficient solver probes time out. |
| Tensor and top-degree relaxations | Project the five-product problem onto alternating tensors or degree-seven/eight output coefficients. | An arbitrary tensor representative is not a minimum-rank bound. The top-degree relaxation admits witnesses that fail the full AES truth table, so neither diagnostic establishes a lower bound. |
| Exact two-product charts | Search actual rank-four alternating tensors for one chosen four-coordinate principal block. | Explicit XOR-polynomial certificates exclude 16 fixed-block cases. Twelve cases and the other coordinate quartets remain open; the attempted nonlinear case times out. |
| New public seeds and changed prefixes | Compare refreshed circuits' exact truth spaces, then pilot a 10+12+12-AND organization with mutable first and second layers and fixed final tail functions. | Seven distinct forward-normalized public seed spaces are identified. The finite 26,488-evaluation constructive pilot finds no candidate, not an impossibility proof. |

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
timeouts establish no negative result. Independent review is now complete:
40 small full-affine exhaustive cases agree with 240 production/independent
solver runs; all original serialized instances and AES input spaces were
checked. No encoding defect was found, but no expensive AES search was
repeated and no timeout became an exclusion.

### New parallel-product follow-up — 2026-10-06

This route keeps the first public 35-AND, depth-three source's 23 early ANDs
and six retained terminal ANDs. Its factor space `P` has dimension 32, retained
space `W` dimension 38, and `T = W + AES` dimension 42. Replacement operands
must be in `P`; neither new nor retained depth-three outputs may be factors.

For three of its six windows (indices 0, 3 and 5), exact coefficient encodings
report no product in `T` outside `W`: `UNSAT`, exit 20, in 45.85, 47.97 and
49.60 seconds command wall time. An independent reconstruction reproduces
all 24 control/search CNFs byte-for-byte and checks 6,144 full-affine product
projections. No formal UNSAT certificate was replayed. These results exclude
the all-inside-`T` branch for those fixed windows, subject to solver correctness.

Consequently, a successful five-product replacement there would need five
actual products in one common nonzero outside-`T` class, with four independent
pairwise differences spanning `T/W`. This is a necessary and sufficient
condition for that fixed parallel architecture, not for arbitrary AES circuits.
Nine broader full-truth probes time out. A compressed complete coefficient
model for window 0 also times out (exit 15, 183.26 seconds); it establishes no
negative result, and windows 3 and 5 were not attempted with that model.
Independent reconstruction matches that compressed model's serialized AES
CNF and all 465 product-coordinate entries, with 256 full-affine projection
checks. Seven nontrivial negative controls and three positive decoder checks
finish, while a fourth positive probe and an earlier decoder probe time out.
The control campaign is not an all-passing audit, and no AES exclusion follows.

A separate constructive method intersects exact product images for chosen
left factors while allowing every right factor in `P`. For the 46-factor pool
of source terminal operands plus the `P` basis, all **8,224,524** five-left
combinations across six windows are accounted for by exact pruning. All
294 surviving nonzero common-q form evaluations finish; the maximum target
difference rank is two, below the required four. Independent high-pivot
reconstruction verifies that finite campaign.

The expanded 105-factor source-operand/XOR-pair pool completes for window 0:
**96,560,646** combinations accounted for, 45,987 common-q form evaluations,
maximum target difference rank two, no candidate. This expanded campaign
was not independently repeated. A 1,023-factor pilot processes only part of
one selected root before its 60-second enumeration limit; it is explicitly
partial and cannot exclude the full pool. The finite left-factor choices do
not cover arbitrary `P` operands. Repeated-left cases cannot complete these
tested common-class searches because their exact maps have no useful
inside-`T` product.
These evaluation counts are summed over factor combinations/windows; they
are not counts of globally distinct outside classes.

Promising unclosed questions are:

1. Unrestricted auxiliary choices and full factor spaces in the surplus-rank
   windows, with stronger exact reasoning or a better solver encoding.
2. Five parallel new depth-three products whose span has an outside-target
   direction, **without** adding a new depth-two auxiliary. This is a separate
   branch: finite factor pools are tested, but arbitrary factors remain open.
3. Changed early/middle gates or a materially different nonlinear
   construction, rather than another variation of an already closed prefix.
4. Target-specific implementation and physical measurements if a genuinely
   new complete circuit passes the independent oracle.

Any prospective candidate must be materialized as actual gates, checked on
all 256 S-box inputs, recounted for AND number/depth and compared with current
primary-source prior art before a novelty claim is made.

### Tensor-chart follow-up — 2026-10-18

The new pair formulation searches rank-four alternating tensors that can be
decomposed into two actual products. It does not use the rank of an arbitrary
tensor representative as a lower bound. Fixed invertible four-coordinate
blocks yield exact quadratic equations; linear elimination reduces a tested
case from 108 to 88 free coefficient bits. Its 90-second solver probe remains
`INDETERMINATE` (exit 15). No search-speed advantage is established.

The controls cover all 19,124 rank-four alternating matrices of sizes four
through six, 960 symbolic/direct comparisons and 26,112 exhaustive small
chart assignments. Three additional nonlinear negative controls survive
linear simplification and actually return UNSAT. Separate exact XOR-polynomial
certificates rule out 16 of 28 fixed-block cases for one chosen AES chart.
The other 12 cases and all other index quartets remain open; there are
31,465 possible quartets, so this is narrow coverage.

The earlier 1,023-factor pool has 1,023 distinct exact multiplication-image
maps in every window; merely deduplicating identical maps cannot compress
that search. Its affine space has dimension 11 including the constant,
not the full 32-dimensional factor space. This motivates structured tensor
search and changed prefixes instead of another unqualified finite-pool sweep.

### Changed-prefix handoff — 2026-10-18

A separate interpreter checks the eleven released public JSON circuits and
compares eleven forward-normalized cases (nine forward circuits plus two
affine conversions of inverse circuits) against nine older 28-AND and four
older 35-AND/depth-three sources. The eleven forward cases form seven exact
full-space classes. Each supplies six directions outside even the combined
79-dimensional older-source span; together their residual rank is 16.
These are differences in the fixed input coordinates, not affine-inequivalence
or novelty proofs. For the converted `invsbox109_d30`, the six new witness
directions occur in degree-seven gates, so this is not automatically a new
low-degree prefix.

The constructive pilot changes both earlier nonlinear layers of the public
11+12+12 source, aiming for 10+12+12 ANDs at depth three while preserving
the exact final tail operand functions. All eleven first-layer deletions
pass a necessary relaxed product-span test, but the actual bounded search
evaluates 26,488 candidate states and never spans all required tail functions;
the smallest remaining rank deficit is three. The original 35-AND source is
materialized as a positive control and checked on all 256 AES inputs.
This unsuccessful finite neighborhood search is not a changed-prefix
exclusion. The completed search and overlap computations are replayed at
publication; no improved AES candidate results.

The next open step is a genuinely constructive search over changed early
functions or another nonlinear organization. An eight-AND quadratic norm
stage was considered as a possible subproblem, but no such solver experiment
or complete AES construction has been run at this checkpoint. The
[changed-prefix study](../../workspace/aes-256-gcm/reports/sbox_changed_prefix_study.json)
records exact scope, controls, source revisions and limitations.

## Sources and novelty checks

Primary web sources were checked again on 2026-10-18:

- [NIST circuit table](https://csrc.nist.gov/projects/circuit-complexity/list-of-circuits)
  and [AES source inventory](https://raw.githubusercontent.com/usnistgov/Circuits/master/data/slp/aes/aes-sbox/README.md).
  The pinned source revision is `b402f09ee22fd26cc58a2904bf5bd524fcd0cbcc`.
  Selected public 28-AND and 35-AND depth-three examples are prior art, not ours.
- [SAT-based multiplicative-complexity synthesis](https://arxiv.org/abs/2005.01778)
  and [the explicit 29-AND construction](https://umizame.github.io/S-box_29-AND/)
  establish relevant prior work.
- The [current NIST source snapshot](https://github.com/usnistgov/Circuits/tree/8366158a4324ef902ce740f29ddc9f7ebb1018b2/data/slp/aes/aes-sbox)
  contains 37 forward S-box files, all checked on 256 inputs and recounted
  locally. Their minimum counts remain 28 ANDs, and 35 ANDs at AND depth three.
  These are inventory minima, not global lower bounds.
- [Swapnil Jain's released circuits](https://github.com/Swapnil-jain/gf2m-circuits/tree/9daf883e529ab4b9c80c66632683b403f0c69e89/sbox)
  provide newer prior art: all 11 released JSON circuits pass our separate
  256-input check and mutation controls. Forward `sbox106_d24` has 34 ANDs,
  AND depth four and gate depth 24; forward `sbox106_d34` has 32 ANDs,
  AND depth six and gate depth 34. Inverse `invsbox109_d30` has 32 ANDs
  and AND depth six. These circuits are not ours. We did not rerun Lean or
  execute downloaded search/verifier programs.

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
- [Parallel-product follow-up summary](../../workspace/aes-256-gcm/reports/sbox_parallel_replacement_study.json),
  including the new exclusions, finite campaigns, encoding reviews and
  unresolved solver probes.
- [Tensor-chart study](../../workspace/aes-256-gcm/reports/sbox_tensor_chart_study.json)
  and [refreshed prior-art/seed inventory](../../workspace/aes-256-gcm/reports/sbox_frontier_refresh_study.json)
  retain the latest narrow results and unresolved cases.
- [Changed-prefix and seed-overlap study](../../workspace/aes-256-gcm/reports/sbox_changed_prefix_study.json)
  records the completed constructive pilot and fixed-coordinate source diversity.
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
