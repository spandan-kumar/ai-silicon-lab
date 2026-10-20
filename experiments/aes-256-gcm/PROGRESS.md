# Experiment 002: AES-256-GCM — progress and research handoff

Last updated: **2026-10-20**. Work is on
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
- **Earlier tensor-chart route:** an exact two-product formulation
  passes exhaustive small controls and rules out 16 fixed-block cases in
  one chart by explicit linear contradictions. One remaining case times out;
  this is not a complete two-product or AES exclusion. Eleven forward-normalized
  public seeds form seven distinct exact function spaces in the tested input
  coordinates. A changed-prefix pilot tests 26,488 candidate states without
  finding a smaller circuit; neither result settles arbitrary new prefixes.
- **Norm-stage boundary:** a certificate-backed search excludes an eight-AND
  GF(16) multiplier when every AND operand is affine in the original inputs.
  The matching nine-AND construction is verified. An earlier public claim
  exists; this is not a novelty claim. Dependent-AND eight-gate probes remain
  inconclusive, and no complete AES improvement follows.
- **Unrestricted norm search:** counterexample-guided dependent-AND searches
  reject every partial fit on the full input table. The latest models enforce
  nested target witnesses after gates five, six and seven, two distinct
  dependent gates, and an exact higher-degree escape condition. All nine
  pre-normalization bounded solver probes remain inconclusive. No search speedup or complete
  eight-AND circuit is established.
- **Latest concrete-prefix result:** exact product closure excludes a
  three-AND continuation for 160 distinct tested prefix spaces: the earlier
  157 plus the two rank-two counterexamples and explicit rank-three prefix.
  All three newest spaces receive complete independent nullspace rescans;
  other five-gate structures remain open.
- **Normalized free-prefix search:** fixing the first target direction requires
  seven jointly verified first-gate cases. The earlier three cases remain
  valid when that target direction is free. All seven normalized probes now
  finish UNKNOWN; no speedup or unrestricted exclusion is established.
- **Latest hypothesis check:** a proposed limit of one independent
  higher-degree component in a five-AND prefix computing a rank-eight
  quadratic is false. Two actual
  solver witnesses have rank two; a simple explicit construction reaches the
  maximum rank three and computes GF(16) output bit zero on all 256 inputs.
  It does not compute all four outputs.
- **Latest family obstruction:** complete product inventories rule out every
  invertible linear input version of six specified prefixes, provided
  their scalar output maps to a field-output combination modulo affine
  terms. The two newest have rank-one higher-degree images but lack a
  four-product quadratic basis. All six are independently replayed.
  This is broader than individual coordinate changes, but
  does not classify all five-gate circuits. A new six-gate search seeks a
  second independent output direction with higher-degree rank at least two
  in its first five gates; all seven bounded cases remain UNKNOWN.
- **Output-pair frontier:** all 35 independent two-output subspaces have
  actual six-AND parallel constructions, replayed independently. Their
  semilinear classes have sizes five and thirty, but the costs are the same.
  A joint scalar-direction/pair classification gives three safe search
  cases, not just two. The newer nonquadratic six-gate probes in those three
  cases all return UNKNOWN; no smaller full multiplier is obtained.
- **Latest full-eight-gate search:** the earlier higher-degree rank budget is
  now encoded for all eight gates on all 256 inputs. All three normalized
  cases return UNKNOWN at their 20-second limits. An independent audit
  reconstructs all five control/search formulas and replays the generic
  positive control, including its cubic final gate. No full GF(16) candidate
  or unrestricted exclusion results.
- **Scalar-only strengthening:** an added constraint on higher-degree rank
  growth from gate three to gate five has a self-contained proof and
  independent finite/encoding controls. The three stronger 30-second
  full-eight-gate probes also return UNKNOWN.
- **Newest structural checks:** two actual five-gate prefixes refute a
  proposed four-product-basis shortcut. A separate six-input example refutes
  a stronger local flattening lemma. Neither refutes general rank-one
  flattening or improves a complete field multiplier.
- **Newest verified structural checkpoint:** a second-method symbolic/Pfaffian
  replay completes for all 192 nonquadratic fifth-gate classes after four
  disjoint products. Counts match and no rank-eight-pair escape exists.
  The reviewed reduction, explicitly invoking the published strong
  scalar-optimal structure theorem, excludes the Q-by-four branch. It does
  not exclude all eight-AND multipliers. The two product implementations
  share a primary author; this is not external peer review.
- **Newest search:** a no-early-target constraint is checked on admitted and
  rejected controls, 173,584 small span cases and five serialized formula
  blocks. All three strengthened full-eight-gate probes finish UNKNOWN
  at 30-second limits. No solver speedup or complete circuit is established.
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
| Quadratic norm stage | Allow arbitrary affine raw-input factors, including mixed input halves. | Nine ANDs are necessary and sufficient in this restricted model; the eight-AND refutation has checked DRAT/LRAT evidence. The result has prior precedent. |
| Dependent norm stage | Allow earlier AND signals as operands, with exact prefix, symmetry and higher-degree constraints. | General eight-AND probes remain inconclusive. The earlier concrete inventory records 160 fixed spaces; newer product inventories exclude all invertible linear images of six specified prefixes. |
| Scalar prefix assumptions | Test whether five ANDs computing a rank-eight quadratic can contain two independent higher-degree components. | The proposed rank-at-most-one rule is refuted. Verified examples attain ranks two and three; no complete smaller multiplier follows. |
| Scalar available by gate four | Classify the next nonquadratic product after a canonical four-disjoint-product precursor, then scan each resulting prefix by two methods. | All 192 classes are obstructed. The reviewed Q-by-four exclusion invokes the published strong scalar-optimal structure theorem and the earlier quadratic bound. Scalar-first-at-five remains open; all three stronger probes are UNKNOWN. |

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

At the preceding publication snapshot, the eight-AND norm stage was only
proposed. Its completed follow-up is described below. The
[changed-prefix study](../../workspace/aes-256-gcm/reports/sbox_changed_prefix_study.json)
records exact scope, controls, source revisions and limitations.

### Certificate-backed norm-stage follow-up — 2026-10-18

GF(16) multiplication and the affine-equivalent GF(256) norm need nine ANDs
in the parallel affine-input model, including factors that mix input halves.
The normalized eight-product instance has independently reconstructed
coefficients and a verified DRAT/LRAT refutation. An actual nine-product
construction passes all 256 input pairs. This closes that particular
eight-product stage, not arbitrary AES circuits or dependent-gate designs.
The [bound note](GF16_QUADRATIC_BOUND.md) gives the model and proof chain.
An earlier public author entry already claims the same quadratic bound;
no priority or world-first claim is made here.

A separate full-truth search allows arbitrary earlier AND results as
operands. Verified symmetries reduce the first gate to three representatives
covering 10,795 planes. All three bounded eight-AND probes time out; none
establishes an exclusion. The next constructive route must allow such
nonlinear dependencies or change the surrounding AES organization.
The same three full-truth cases also reach a second solver's 90-second
limits with explicit UNKNOWN outcomes. Their six translated control/search
instances independently reconstruct exactly, but the broader answer remains
unresolved. The [second-solver study](../../workspace/aes-256-gcm/reports/sbox_dependent_norm_solver_study.json)
keeps those outcomes separate from the checked quadratic certificate.

The subsequent [counterexample/prefix-witness study](../../workspace/aes-256-gcm/reports/sbox_norm_cegis_study.json)
replays all proposed circuits on 256 inputs. Its base campaign rejects nine
partial field fits; exact ranks show all nine prefixes are already
uncompletable. The stronger campaign enforces a free nonzero target
combination in the first five gates on every input, a necessary dimension
condition rather than a fixed construction. Its six partial fits have valid
prefix witnesses but still fail the complete multiplier. All main cases
remain UNKNOWN. Independent CNF/model/feedback audits pass for both methods.
An additional quadratic-product reduction supports requiring higher-degree
intermediates in any eight-AND escape; it has not yet been used to exclude
any search case.

### Latest scalar prefix counterexamples

Let addition mean XOR and multiplication mean AND. Five actual gates can
compute a rank-eight quadratic while their degree-above-two parts span three
independent directions:

```text
g1 = ab
g2 = (g1+c)d
g3 = (g1+e)f
g4 = (g1+g)h
g5 = g1(d+f+h)
g1+g2+g3+g4+g5 = ab+cd+ef+gh
```

Three is the maximum for this five-gate scalar problem: the higher-degree
projection kills both the first, quadratic gate and an independent selector
computing the rank-eight quadratic, leaving rank at most `5-2=3`.
The construction also maps exactly to output bit zero of multiplication in
GF(16) with polynomial `t^4+t+1`. All 256 inputs pass a separate replay.
This invalidates a proposed search shortcut; it is not a new full multiplier
or a novelty claim. Two separately synthesized rank-two examples also pass
independent formula and truth-table checks; the other five bounded probes
remain UNKNOWN.

The [counterexample study](../../workspace/aes-256-gcm/reports/sbox_norm_prefix_counterexample_study.json)
retains explicit gates, terminal results and audit scope. The small committed
[replay tool](../../workspace/aes-256-gcm/tools/verify_norm_prefix.py) runs with
`python3 workspace/aes-256-gcm/tools/verify_norm_prefix.py`, without a solver
or the ignored raw archive. Completion to all four field outputs remains open.

### Linear families of the new prefixes

The three new scalar prefixes themselves are closed inside their
prefix-plus-field-output envelopes. Independent code repeats all 24,573
nonzero-left scans and checks 24,887 right-kernel basis products. None adds
a useful direction, and all three spaces differ from the previous 157.

A stronger calculation relaxes the target to arbitrary quadratic functions.
For the rank-three construction it enumerates all 61,504 eligible unordered
nonzero operand pairs. After cancelling the available cubic parts, every
quadratic residue has a representative of polar rank at most four modulo
the available quadratic span. A new field direction would instead have
minimum rank at least six. This contradiction survives every invertible
linear input substitution mapping its scalar output to a field component.

For the two rank-two prefixes, separate inventories cover 54,976 and 50,080
eligible pairs. No residue coset contains both `t` and `t+Q` of polar rank
eight, as a second independent field direction would require. A separate
truth-table implementation reproduces both inventories and their obstruction.
These are three specified linear families, not all rank-two/rank-three
prefixes or an unrestricted eight-AND lower bound.

The [family study](../../workspace/aes-256-gcm/reports/sbox_norm_linear_family_study.json)
gives the precise argument and evidence. The rank-three inventory has a
standalone replay:
`python3 workspace/aes-256-gcm/tools/verify_norm_family.py`.
A follow-up six-gate model requires `Q` after five gates, higher-degree rank
at least two there, and a second independent field direction after six.
All seven ten-second probes return UNKNOWN. Nine independently reconstructed
formulas and the positive model pass, but no new field prefix or exclusion
is obtained from those probes.

### Output pairs and earlier higher degree escape

Every independent pair of GF(16) output combinations can be computed with
six parallel ANDs. The 35 explicit circuits come from subsets of the known
nine-AND multiplier and linear input changes; independent verification checks
8,960 output rows and 53,760 individual gate rows. Six is also the parallel
lower bound: three nonzero decoder words each need weight at least four,
whereas their total weight is at most twice the number of products.
There is no harder seven-AND pair class to exploit.

For unrestricted circuits, equality with the quadratic pair complexity uses
the published Mirwald–Schnorr theorem, as stated by
[Boyar and Find](https://arxiv.org/html/1407.6169v3#S4). The original full proof
was not replayed here. This theorem does not permit replacing an optimal
nonlinear prefix while preserving auxiliary signals needed later.

Let `r_i` be the rank of degree-above-two parts among the first `i` gates.
Selector-space dimension counting gives `r_8 <= 3` and `r_8-r_3 <= 1` for
any hypothetical eight-gate field multiplier, including padded circuits.
Invoking the published pair theorem gives the stronger `r_8=r_5`: all
higher-degree directions must already be present by gate five. The complete
quadratic eight-gate exclusion then requires at least one such direction.
These are necessary conditions, not a complete lower bound.

Keeping the first scalar target direction with its two-output plane yields
105 flags and three semilinear orbits of sizes 15, 30 and 60. The first
direction can be bit zero, with second covector 2, 4 or 12. A separate
determinant-one input symmetry fixes the first left factor without fixing its
whole plane. New six-gate probes use these cases and permit higher-degree
rank one as well as larger ranks in the first five gates. All three reach
30-second limits with UNKNOWN. The corrected positive and negative controls
pass; the original control import failure is retained separately.

The [output-pair study](../../workspace/aes-256-gcm/reports/sbox_norm_pair_frontier_study.json)
separates independently executed constructions, published theorem dependencies,
finite rank checks and solver outcomes. Its committed replay is
`python3 workspace/aes-256-gcm/tools/verify_norm_pairs.py`.

### Full-eight-gate checkpoint — 2026-10-19

The newest model constrains every gate on the complete input table, rather
than searching only a six-gate prefix. It permits arbitrary dependencies on
earlier gates, requires a nonzero higher-degree component by gate five, and
expresses the higher-degree parts of gates six through eight in the span of
those already present. The necessary-condition argument uses the published
two-output theorem and the separately reviewed rank budget above; the audit
does not prove those dependencies anew. The last gate is not forced to be
quadratic.

The three cases, with second covectors 2, 4 and 12, each reach a 20-second
solver limit with UNKNOWN. This is neither a lower bound nor evidence of a
search speedup. Independent code reconstructs all five CNFs byte-for-byte.
It checks the generic positive witness on all 256 inputs, including a cubic
last gate with `r_5=r_8=3`; this witness is a control, not a field multiplier.
The negative control adds a new late higher-degree direction (`r_5=3`,
`r_8=4`) and has a directly checked span contradiction. No UNSAT certificate
was checked for these controls.

The [full-eight-gate checkpoint](../../workspace/aes-256-gcm/reports/sbox_norm_early_high_study.json)
retains the terminal outcomes, exact scope, audit and artifact hashes. It
supersedes the earlier pair study's proposed next action of building this
encoder. The remaining question is still whether any unrestricted eight-AND
GF(16) multiplier exists; no improved complete AES circuit has been found.

At publication commit `93458fa`, the rank-one shared-cubic family probe was
still provisional. The independently completed follow-up below supersedes
that limitation, without changing the historical report or the total of
160 distinct concrete prefix spaces. General rank-one flattening remains
unproved.

### Rank-one family and scalar-only rank budget — 2026-10-19

The earlier shared-cubic prefix has five gates of the form
`ab, (ab+c)d, abd, ef, gh`, whose sum is the rank-eight quadratic
`ab+cd+ef+gh`. Its higher-degree image has rank one, and its available
quadratic polar space has dimension four. Complete inventories in two
different implementations cover 8,191 nonzero left forms, 53,776 eligible
unordered operand pairs and 10,036 quadratic polar cosets. No coset, including
the zero coset, has a representative `t` for which both `t` and `t+Q` have
polar rank eight. The same rank-tight argument as above therefore excludes
every invertible linear input version of this specified prefix mapping `Q`
to a field component modulo affine terms. It does not classify all rank-one
prefixes. There are now four verified specified linear families, not a new
global eight-AND lower bound.

A new standalone replay needs no solver or ignored archive:
`python3 workspace/aes-256-gcm/tools/verify_norm_rankone_family.py`.
It also checks all 15 nonzero field-output polar ranks.

The additional search constraint is `r_5-r_3 <= 1`. It already follows from
a rank-eight scalar quadratic decoded after five gates. Such a scalar needs
at least four ANDs: restricting one nonconstant affine operand per gate
makes a k-AND circuit affine on an input subspace of codimension at most k,
while a rank-eight quadratic is affine only on direction spaces of dimension
at most four. Its decoder is thus in the five-gate higher-degree kernel but
outside the first-three selector space. Kernel dimension counting gives the
claimed rank inequality, without invoking the published pair theorem.

The encoding expresses this as one global nonzero pair `(alpha,beta)` and
free global `(gamma,delta)` with
`alpha H4 + beta H5 = gamma H2 + delta H3` across all 219 residual coordinates.
Zero and dependent early directions are permitted. Independent checks cover
69,904 finite vector quadruples and 4,096 triangular signal rewrites; a
separate encoding audit includes the additional zero-dimensional case,
reconstructs six CNFs, and replays both SAT models. A low-rank generic
control is SAT without the cut and rejected with it, isolating the predicate;
it is not a field exclusion. The inherited late-span constraints still use
the earlier published-theorem dependencies.

All three new field cases return UNKNOWN at 30 seconds. A separate general
rank-one-flattening investigation proves only that a simple local signal
substitution fails; its example still flattens globally. The 17,856 sampled
local identities without a counterexample are not a general theorem.
The [rank-one and scalar-budget study](../../workspace/aes-256-gcm/reports/sbox_norm_rankone_and_scalar_budget_study.json)
retains the scopes, proof reviews, completed probes and provenance. No
additional GitHub push or new hardware measurement is part of this follow-up.

### Two rank-one shortcuts refuted — 2026-10-19

Rank-one higher-degree state does not imply a four-product basis for its
four-dimensional quadratic polar kernel. An actual counterexample is:

```text
g1 = ab
g2 = c(d+ab)
g3 = (a+c)(b+d+ab)
g4 = ef
g5 = gh
Q  = g2+g3+g4+g5 = ad+bc+ef+gh
```

Its only higher-degree direction is `abc`. Its quadratic kernel is
`K=span{ab,ad+bc,ef,gh}`, but its only rank-two elements are `ab,ef,gh`.
The kernel therefore needs five parallel products, not four. Five suffice,
so this is not a separation between unrestricted and quadratic complexity.
A separately synthesized five-gate example has a different K polar-rank
histogram, proving that these two K types are not related by an invertible
linear input change. Both compute the exact GF(16) bit-zero scalar after
normalization and pass all 256 inputs. The bounded scalar search yields
five SAT prefixes and five UNKNOWN probes; it is not an all-prefix census.

Complete product inventories then exclude both specified linear families:
the explicit example has 48,256 eligible pairs and 10,516 quadratic polar
cosets; the synthesized type has 47,200 pairs and 10,440 cosets. Independent
truth-table/Mobius/high-pivot code reproduces both, including zero cosets and
all sixteen K shifts per coset. No coset contains both `t` and `t+Q` of
polar rank eight. The previous family argument applies, bringing the
specified whole-family total from four to six. This does not recount the
earlier 160-space concrete inventory or classify every rank-one prefix.

A stronger proposed local lemma also fails. There are six-input quadratic
forms `P,Q,A,B` with nonquadratic `h=P*Q` and quadratic `q=A*B+h`, but every
one of the sixteen forms in `q+span(P,Q,A,B)` has polar rank four. None is
affine plus one raw-affine product. The exact coefficients and all rank
checks are retained. The audit reconstructs six CNFs, verifies both SAT
models, and checks the Pfaffian rank predicate on 33,856 small alternating
matrices. The other three local-mode probes are UNKNOWN. This challenge
does not budget the cost of producing `P,Q,A,B`; it is not a general
flattening counterexample, complexity separation, or full multiplier.

The [kernel-shortcut study](../../workspace/aes-256-gcm/reports/sbox_norm_kernel_shortcut_study.json)
retains the witnesses, exact scopes and independent audits. Its standalone
replay is
`python3 workspace/aes-256-gcm/tools/verify_norm_kernel_counterexamples.py`.
Both proposed shortcuts must remain out of sound unrestricted searches.

### Q-by-four investigation: provisional publication — 2026-10-20

The latest route studies a possible eight-AND GF(16) multiplier in which a
nonzero field-output combination `Q` is already available by gate four.
The proposed reduction starts with four disjoint products
`p_i = a_i*b_i`, with `Q = p_0+p_1+p_2+p_3` modulo affine terms. Its
published scalar-optimal normal-form dependency and the complete reduction
from arbitrary circuits still need a consolidated review. In particular,
normalizing `Q` must transport the other field outputs jointly; it is not
sound to fix their original coordinate tables at the same time.

The concrete finite computation is complete in that canonical precursor:

- The twelve-dimensional operand space modulo constants has **2,794,155**
  independent two-dimensional operand planes. Blockwise affine changes and
  permutations of the four pairs divide them into **216** classes.
- **192** classes, representing **2,781,824** planes, produce a nonquadratic
  fifth gate. The other 24 classes produce a quadratic gate or an old wire.
- An independent block-type/multiset calculation identifies all 216 classes
  and their exact sizes. A negative control confirms that preserving the
  precursor and `Q` does not necessarily preserve the other field outputs.
- All 192 producer scans exit successfully. Each exhausts **8,191** nonzero
  left forms and the full corresponding right kernels. None finds a
  quadratic residue `R` for which both `R` and `R+Q` have polar rank eight,
  after allowing all sixteen precursor-product corrections. That is a
  necessary-condition test, not a complete field-multiplier construction.
- **The full 192-class product scan has not been independently replayed.**
  Matching the orbit inventory does not independently verify those product
  inventories. The frozen report therefore keeps both `Q_by_four_branch_excluded`
  and `unrestricted_eight_AND_excluded` false.

Earlier direct two-product solver probes for this route give one UNKNOWN
at its 45-second limit and one solver-reported UNSAT in 2.96 seconds.
Small positive/negative controls finish, but no formal UNSAT certificate or
complete independent encoding audit is claimed. These outcomes were checked
against the terminal JSON and solver logs, not an earlier progress summary.
A related diagonal-prefix collision also refutes a one-product correction
shortcut; a two-raw-product identity preserves its quadratic output instead,
not the intermediate nonlinear wire needed by an arbitrary later suffix.
The broader transfer/annihilator verification script is an **unexecuted
draft**, preserved as such rather than reported as passing.

The [checkpoint inventory](../../workspace/aes-256-gcm/reports/sbox_norm_q4_snapshot.json)
contains the class representatives, terminal scan results, command outcomes
and artifact hashes. The [source snapshot and reproduction instructions](../../workspace/aes-256-gcm/tools/norm_q4_snapshot/README.md)
preserve the new scan programs. The original failed orbit-control script
and its syntax-error log remain in the local raw archive; the corrected
independent audit is a separate file.

Next steps are to independently replay all product inventories, finish the
normal-form and rank-budget proof review, and only then assess a scoped
Q-by-four exclusion. The unrestricted case, including scalar outputs first
appearing at gate five, remains open. No improved AES circuit, world-first
claim, physical implementation or new hardware measurement follows here.

### Q-by-four second-method replay and reduction — 2026-10-20

This follow-up supersedes the pending checks in the preceding publication
snapshot, whose original records remain unchanged. All **192** product
inventories now have a complete second-method replay. Symbolic Boolean-ring
multiplication, low-pivot row-equation kernels and Pfaffian truth tables
replace the producer's truth-table/Mobius, column-kernel and Gaussian-rank
methods. Every eligible-pair and polar-coset count matches. All sixteen
precursor corrections, including the zero coset, are covered. The command
exits zero in **45.747 seconds**. This is algorithmic independence under the
same primary author, not an external independent review.

The [reviewed early-scalar proof](GF16_EARLY_SCALAR_BOUND.md) now assembles
the normalization, complete orbit coverage and rank-tight continuation
argument. It invokes the published statement that every scalar-optimal
quadratic circuit is single-level; merely replacing a scalar circuit by
some parallel optimum would not preserve its other wires. That literature
dependency is explicit, and its original 1992 full proof is not reproduced
here. The Q-by-four branch is excluded under these dependencies. An
eight-AND multiplier would therefore need its first target direction at
gate five; this remaining case is **not** excluded.

A stronger full-eight-gate model forbids every nonzero target combination
in the affine span of its first four gates. Its new constraint block and
XOR-to-CNF suffix are reconstructed exactly for all five control/search
instances. All 255 zero-preserving truth-basis projections, 173,584 small
span cases and the positive model's actual gate truths pass. The prior
base encoder is unchanged except for exposing its truth-variable IDs;
this does not claim a fresh full audit of all inherited constraints.
All three 30-second field probes finish **UNKNOWN**. There is no checked
UNSAT certificate, new complete field circuit, measured speedup or
improved AES implementation.

The transfer/annihilator draft is separately executed in a fresh directory:
524,800 diagonal shadow comparisons, the embedded collision and stated
annihilator controls pass. This does not establish a general
cost-preserving rank-one flattening theorem.

The [verified study](../../workspace/aes-256-gcm/reports/sbox_norm_q4_verified_study.json)
retains commands, hashes, counts, proof dependencies and terminal outcomes.
Its [standalone symbolic verifier](../../workspace/aes-256-gcm/tools/verify_norm_q4.py)
requires only Python and the committed provisional inventory:

```sh
python3 workspace/aes-256-gcm/tools/verify_norm_q4.py controls --output runs/q4-independent-replay
python3 workspace/aes-256-gcm/tools/verify_norm_q4.py campaign --output runs/q4-independent-replay
```

Use a new output directory; existing artifacts are not overwritten. The
next research question is the structure or construction of prefixes whose
first scalar output appears at gate five. No world-first is established.

## Sources and novelty checks

Primary web sources were checked again on 2026-10-18:

- [NIST circuit table](https://csrc.nist.gov/projects/circuit-complexity/list-of-circuits)
  and [AES source inventory](https://raw.githubusercontent.com/usnistgov/Circuits/master/data/slp/aes/aes-sbox/README.md).
  The pinned source revision is `b402f09ee22fd26cc58a2904bf5bd524fcd0cbcc`.
  Selected public 28-AND and 35-AND depth-three examples are prior art, not ours.
- [SAT-based multiplicative-complexity synthesis](https://arxiv.org/abs/2005.01778)
  and [the explicit 29-AND construction](https://umizame.github.io/S-box_29-AND/)
  establish relevant prior work.
- The [MF-167 author entry](https://slopdealer.com/research/papers/mf-167/)
  already claims the nine-product mixed-affine GF(16) bound and an
  eight-product bound for its three-output projection. Our checked
  certificate covers the former restricted model; our projected
  seven-product probe times out and does not verify the latter claim.
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
- [Norm-stage study](../../workspace/aes-256-gcm/reports/sbox_norm_stage_study.json)
  and [bound note](GF16_QUADRATIC_BOUND.md) record the checked quadratic
  certificate and unresolved dependent-gate probes.
- [Dependent second-solver study](../../workspace/aes-256-gcm/reports/sbox_dependent_norm_solver_study.json),
  [prefix and counterexample-guided study](../../workspace/aes-256-gcm/reports/sbox_norm_cegis_study.json),
  [higher-degree escape study](../../workspace/aes-256-gcm/reports/sbox_norm_escape_study.json),
  [concrete-prefix study](../../workspace/aes-256-gcm/reports/sbox_norm_concrete_prefix_study.json)
  and [normalized search study](../../workspace/aes-256-gcm/reports/sbox_norm_normalized_search_study.json)
  distinguish verified restricted results from inconclusive unrestricted probes.
- [Latest scalar-prefix counterexamples](../../workspace/aes-256-gcm/reports/sbox_norm_prefix_counterexample_study.json)
  and [standalone replay](../../workspace/aes-256-gcm/tools/verify_norm_prefix.py)
  preserve the refuted assumption and explicit rank-three construction.
- [Linear prefix-family study](../../workspace/aes-256-gcm/reports/sbox_norm_linear_family_study.json)
  and [standalone family replay](../../workspace/aes-256-gcm/tools/verify_norm_family.py)
  retain the three broader obstructions and unresolved six-gate search.
- [Output-pair frontier and rank-budget study](../../workspace/aes-256-gcm/reports/sbox_norm_pair_frontier_study.json)
  and [standalone pair replay](../../workspace/aes-256-gcm/tools/verify_norm_pairs.py)
  retain all 35 six-AND pair constructions and the three unresolved flag cases.
- [Full-eight-gate early-higher-degree study](../../workspace/aes-256-gcm/reports/sbox_norm_early_high_study.json)
  retains the latest three UNKNOWN probes, independent formula/model audit
  and explicitly provisional rank-one diagnostic.
- [Rank-one family and scalar-budget follow-up](../../workspace/aes-256-gcm/reports/sbox_norm_rankone_and_scalar_budget_study.json)
  and [standalone rank-one replay](../../workspace/aes-256-gcm/tools/verify_norm_rankone_family.py)
  supersede that provisional diagnostic and record the three stronger UNKNOWN probes.
- [Kernel-shortcut counterexamples and two further families](../../workspace/aes-256-gcm/reports/sbox_norm_kernel_shortcut_study.json)
  and [standalone replay](../../workspace/aes-256-gcm/tools/verify_norm_kernel_counterexamples.py)
  preserve both invalidated assumptions without claiming a general lower bound.
- [Provisional Q-by-four snapshot](../../workspace/aes-256-gcm/reports/sbox_norm_q4_snapshot.json)
  and [source/reproduction guide](../../workspace/aes-256-gcm/tools/norm_q4_snapshot/README.md)
  preserve the original producer-only publication state.
- [Verified Q-by-four follow-up](../../workspace/aes-256-gcm/reports/sbox_norm_q4_verified_study.json),
  [reviewed proof and dependencies](GF16_EARLY_SCALAR_BOUND.md) and
  [standalone second-method replay](../../workspace/aes-256-gcm/tools/verify_norm_q4.py)
  close that scoped branch while leaving scalar-first-at-five open.
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
