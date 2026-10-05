# AES-256-GCM research record

This is a dated research record for Experiment 002. It identifies the sources
that define the primitive and the verification vocabulary; it is not a
certification claim. If a source changes or a successor publication becomes
normative, update this record and the experiment manifest before changing the
profile.

Research date: 2026-08-29

## Shared auxiliary-family closure and depth-three probes — 2026-10-05

No correct 27-AND AES circuit, 34-AND AND-depth-three AES circuit, global AES
lower bound, or world first has been established. The preceding shared-family
SAT timeout is now superseded by an exact finite scan, not by a timeout being
treated as an exclusion.

Fix the same eighteen retained products, whose affine truth span W has
dimension 27. The prepared family has B=W+d of dimension 28, T=span(W,AES)
of dimension 35, and seven auxiliary columns Q independent modulo T. Of its
127 nonzero combinations, 64 have constructive two-product prefixes from
the earlier fixed system. Write V=B+span(Q), R=T+span(Q). A single complete
scan covers every nonzero constant-free left factor in B and solves exactly
for every right factor in V. It exhausts 134,217,727 left forms, exit zero,
in 377.80 seconds command wall. On every multiplication kernel modulo R,
the entire target-complement tag D is zero, before imposing the auxiliary
parity or output/operand-coefficient relation.

That stronger observed condition excludes all 127 nonzero Q envelopes,
including the 63 algebraically granted cases not asserted to have the same
constructive two-product prefix. For q nonzero in span(Q), independence gives
V intersect (T+q)=B+q. Every useful operand plane in U=B+q meets B modulo
constants. A Boolean change of basis changes its product only by U terms.
Normalize one factor into B: if the product lies in S=T+q, the complete
zero-D scan places it in V and hence U. Thus U is closed under S-constrained
products. Starting from W cannot reach AES inside S. With nine replacement
products, a successful span containing W, the AES targets and an outside-T
auxiliary would have to equal S, so these are conditional 27-AND exclusions.
They do not cover changed retained gates, other auxiliary directions, or
arbitrary AES circuits.

A separate scan for the branch with both factors in B exhausts 67,108,863
left forms, exit zero, in 71.94 seconds command wall. Its codimension-one
left cut preserves every useful operand plane. It is consistent with, but
not needed for, the stronger zero-D conclusion above. Independent review
reconstructs all 702 and 918 matrix entries respectively and checks 5,827
and 8,643 actual-binary small instances. The large scans were observed,
not independently repeated. The retained input columns, proof and artifact
hashes are in `workspace/aes-256-gcm/reports/sbox_shared_family_study.json`.

For the public 35-AND, AND-depth-three g139/gd27 source, all four rank-eligible
terminal-three-to-two windows were also tested with unrestricted affine
factors in the full depth-at-most-two span P of dimension 32. Retained W has
dimension 41 and T=span(W,AES) dimension 43, so both new products would have
to lie in T and remain parallel to preserve AND depth three. The necessary
first-product searches all return UNSAT, exit 20, in 39.58, 44.20, 44.42 and
39.81 seconds command wall. Each original removed product passes a relaxed
positive control. Independent review reconstructs all four negative and
positive CNFs byte-for-byte and checks 1,860 projected products. It also
tests 288 tiny actual SAT instances against brute force. No formal UNSAT
certificate was checked; the other public prefix spaces and larger windows
were then tested separately. All twelve corresponding probes in the three
other pinned depth-three sources return UNSAT, exit 20, with twelve actual
source-product positive controls. Independent review reconstructs their
24 negative/positive CNFs and checks 5,580 more product projections. This
brings the directly tested terminal-three-to-two windows to sixteen.

Each source also has 36 rank-eligible four-terminal windows and 144
five-terminal windows. Every one contains a uniquely selected excluded
triple and has exactly the same target envelope T. This initially excludes
parallel replacements only. To check whether new depth-two gates could feed
new depth-three gates, take L to be the original depth-at-most-one span of
dimension 20 and P the original depth-at-most-two span of dimension 32.
The degree-at-most-four slice of each T has dimension 35, so degree alone
does not identify it with P. Instead, the span M of P and every pairwise
L-basis product has dimension 127 or 138 by source. All sixteen separately
reconstructed intersections M intersect T_low equal P, dimension 32.
Therefore the earliest new depth-at-most-two gate inside T cannot add rank;
the rank-tight budget forbids such a gate. All useful replacements must be
parallel depth-three products. Together with the solver results and exact
equal-envelope diagnostics, this excludes 736 rank-eligible terminal
windows of sizes three through five across the four fixed-prefix sources.
It does not exclude changed prefixes or surplus-rank six-terminal windows.

Three broader auxiliary spans, of quotient dimensions 17, 8 and 9, cover the
148 stored envelopes. A stronger necessary-condition relaxation finds a
positive product in each after 1,410,699 left forms. All three inferred q
directions independently match the original a13 auxiliary modulo T. They
rediscover the known envelope, not a new circuit. Original-direction-excluded
scans then exhaust the branch with both operands in B for all three spans:
67,108,863 left forms each, exit zero, in 116.74, 109.84 and 109.34 seconds
command wall. Independent review reconstructs all 2,106 entries and checks
5,892 actual-binary instances. In the auxiliary-bearing-input branch, the
eight-dimensional family exhausts 134,217,727 left forms, exit zero, in
430.27 seconds command wall. Both branches together close its 254 nonzero,
non-original auxiliary envelopes for the same fixed W. Overlap with the
earlier seven-dimensional family is not counted as additional exclusions.

The other two auxiliary-bearing-input searches return positive products
after 2,983,530 and 2,096,903 left forms. The first has a constructively
verified three-gate prefix. Independent comparison nevertheless finds its
30-dimensional available span exactly equal to the old index-53 closure,
already excluded by the preceding 268,435,455-form scan. Eight finite warm
continuations also stall in that same space. Thus this is another
rediscovery, not a new viable envelope. The search now excludes each known
auxiliary separately; excluding their entire linear span would incorrectly
discard directions not actually searched.

An unrestricted product SAT probe from the original warm span of dimension
33 was inconclusive: exit 15 after 123.70 seconds command wall, with
18 small solver controls and a fixed source-product positive control.
A separate exact search partitions its complete left-factor hyperplane
into disjoint affine cosets. All 32 batches now exhaust, exit zero, covering
2,147,483,647 nonzero left forms. Independent review checks the full matrix,
3,672 actual-binary small cases and the complete terminal partition; the
large scan is not independently repeated. The resulting dimension-33 space
is closed inside the original dimension-36 envelope and contains W. Thus no
completion starting from W and staying in that envelope can reach all AES
targets, regardless of how the original auxiliary is represented.

The finite-exclusion scans also finish: Q17 and Q9 each exhaust 134,217,727
left forms, exit zero, in 651.35 and 438.86 seconds command wall. They exclude
only individually listed known classes, not their linear span. Independent
review reconstructs all 2,160 full matrix entries and checks 7,432 actual
small binary/brute cases. Combining both operand branches with the known
closed superspaces for indices 0/1/53 and the original auxiliary closes all
three quotient families. Their pair intersection dimensions are 1, 2 and 1;
the triple intersection dimension is 1. Inclusion-exclusion gives 131,833
distinct final envelopes, with no double-counting. All 148 stored two-product
prefixes have their actual gates independently replayed and are covered.
This is a fixed-W, single-outside-T envelope exclusion, not global AES
optimality; changed prefixes and other auxiliary classes remain open.

Six terminal gates in the first public depth-three source admit six
rank-slack-one windows. A finite constructive campaign tests 424 distinct
restricted-factor auxiliary implementations per window: 2,544 rectangles
and 5,207,568 left forms, all with zero useful target-direction rank. The
pool covers actual depth-one basis pairs and source-middle-factor nonlinear
radius-one perturbations; deduplication modulo the original terminal-factor
span preserves both operand spaces. Three unrestricted fixed-auxiliary
first-product probes return UNSAT with source-product positive controls.
These finite restrictions do not close the general six-terminal route.

A separate joint solver allows arbitrary depth-one factor combinations for
the new depth-two auxiliary and arbitrary depth-two combinations for its
first useful depth-three product. Three 120-second probes return
INDETERMINATE, exit 15, after 125.97--126.30 seconds command wall. Twenty-four
full-affine small brute/solver controls and three source-product positive
controls pass. Independent review of this latest encoding was not completed
at publication, and no exclusion follows from its timeouts. Five parallel
depth-three replacements without a new depth-two auxiliary are a separate
open branch. See [the progress handoff](PROGRESS.md) for the current state.

Primary sources were checked again on 2026-10-05. The current
[NIST table](https://csrc.nist.gov/projects/circuit-complexity/list-of-circuits)
and its [AES source inventory](https://raw.githubusercontent.com/usnistgov/Circuits/master/data/slp/aes/aes-sbox/README.md)
list selected 28-AND and 35-AND depth-three examples and attribute those
contributions to Milad Nasr. Neither table is an optimality proof. Published
[SAT synthesis](https://arxiv.org/abs/2005.01778) and the
[explicit 29-AND construction](https://umizame.github.io/S-box_29-AND/) are
prior art. Elementary linear-algebra reductions here are not claimed as a
new general synthesis method.

Detailed evidence is retained under `runs/aes-family-third-split-20261005/`,
`runs/aes-third-family-structure-20261004/`,
`runs/aes-third-tag-review-20261005/`, `runs/aes-alternative-route-20261004/`
and `runs/aes-shared-family-closeout-20261005/`. Run records validate with
`./tools/experiment`. No RTL or protected evaluator changed; physical and
security metrics remain unavailable. The coding-guidelines skill led to
keeping experimental search changes separate from the working accelerator
and to verifying that positive witnesses were not known constructions.

## Complete two-product envelope images — 2026-10-04

There is still no complete 27-AND AES construction or established world first.
The new result is a complete enumeration of attainable auxiliary quotients
inside several finite fixed-factor families, replacing the preceding witness
sample. It is not an enumeration of arbitrary AES circuits or all prefix
spans inside each envelope.

For a fixed f,h,alpha,beta, let K be the coefficient kernel enforcing
r=h*v+(alpha*h+beta)*f*g in T. On K define A=q modulo T and C=r modulo W.
Eliminate A while retaining coefficient lifts and their C tags. If C is
nonzero on ker(A), every nonzero A image has a useful lift: add a zero-image
kernel vector whenever the chosen lift has C=0. Otherwise C descends to the
A image, so exactly the images outside its kernel are useful. If the A image
has rank a and the descended C map has rank c, the two respective counts are
2^a-1 and 2^a-2^(a-c). Gray enumeration supplies one actual two-product
witness per useful image. This is elementary linear algebra, not a claimed
new general method.

The retained tool is
`workspace/aes-256-gcm/tools/enumerate_two_and_envelopes.py`. It accepts
separate first/second factor pools, checks input dimensions and constant-free
masks, hashes dependencies, and refuses to overwrite existing evidence.
Above the configurable image-rank limit it marks the report incomplete;
skipped enumeration never becomes a negative result. All current image
ranks are at most seven, below the default limit of eighteen.

The measured finite families are:

- Original 161-by-161 pool: 103,684 systems, 38 feasible systems, 111 distinct
  auxiliary envelopes. The old 58-envelope sample is contained in this set,
  leaving 53 previously missed envelopes. The original run took 40.66 seconds;
  the initial promoted-tool repeat took 41.22 seconds. After input-guard fixes,
  the retained tool repeated all three families with identical results; its
  base repeat took 49.22 seconds while the two other repeats ran concurrently.
  These host algorithm wall times are not a controlled speed comparison.
- Change the second fixed factor by exactly two nonconstant coefficient bits
  around mask 2,097,416, excluding the original pool: 320 new second factors,
  206,080 systems, no feasible prefix. An independent low-pivot implementation
  repeats every system and finds C identically zero on every kernel. This is
  an exact exclusion of this finite factor family only.
- Change the first fixed factor by exactly two such bits around mask 11,776,
  excluding the original pool: 322 new first factors, 207,368 systems, 21
  feasible systems, 51 envelopes. Of these, 37 are absent from the complete
  original pool. Independent full replay matches every feasible-system key,
  image count, envelope and retained witness. The combined inventory is 148
  distinct auxiliary envelopes, not 148 complete AES implementations.

The 53 newly enumerated original-pool envelopes and 37 new first-factor
envelopes were constructively tested with the previous source-gate warm
starts and finite dynamic left-factor pools. All 90 stalled at dimension 29
without reaching AES. These heuristic failures do not exclude unrestricted
extensions. The preceding three exact envelope exclusions remain valid;
this campaign adds no unrestricted closure exclusion.

One original-pool fixed system has A-image rank seven and descended C rank
one, yielding 64 useful envelopes. Its prepared family writes the available
space after two products as U=B+q, B=W+d, with q a seven-parameter linear
combination and one parity constraint selecting the useful half. A joint
SAT instance tests any third useful product in T+q across all 64 choices.
The operand plane can be normalized so its left factor lies in B; diagonal
products vanish modulo B. The remaining exact coefficients are quadratic
for B-times-B products and cubic for the variable-q term. The actual AES
instance has 978 variables, 2,780 clauses and 229 XOR constraints. It returned
`INDETERMINATE`, exit 15, after 121.06 seconds command wall under a 120-second
solver budget. No exclusion or circuit follows from that timeout.

Independent verification includes 80,357 complete small abstract-map pairs,
10,240 fixed-factor truth systems, every image in all 38 reported positive
original-pool systems, and both complete radius-two sweeps. The base pool's
full feasibility classification was independently replayed in the preceding
campaign; this campaign does not repeat that independent full base sweep.
The family SAT audit compares 32 whole small families and 26 fixed parameter
fibers against exhaustive unrestricted operands: 22 SAT and 36 UNSAT. All
128 AES preparation parameter vectors pass truth checks, with 64 useful
envelopes. The four zero-image kernel generators have both q and r differences
inside W, so alternative lifts define the same available spaces. Four new
tool tests also cover exhaustive images, affine operands, incompleteness and
evidence preservation.

Primary web sources were checked again on 2026-10-04. The
[NIST circuit table](https://csrc.nist.gov/projects/circuit-complexity/list-of-circuits)
lists selected 28-AND AES examples, including the depth-four 131-gate source;
the table is neither comprehensive nor an optimality proof. Established
[two-AND structure research](https://www.nist.gov/publications/number-boolean-functions-multiplicative-complexity-2)
and [SAT synthesis](https://arxiv.org/abs/2005.01778) predate this attempt.
No new novelty claim is supported. No candidate RTL or protected evaluator
changed, and physical/security metrics remain unavailable.

Detailed immutable run evidence is in `runs/aes-envelope-image-20261004/`,
`runs/aes-envelope-image-review-20261004/` and
`runs/aes-envelope-closeout-20261004/`. The compact committed record is
`workspace/aes-256-gcm/reports/sbox_envelope_image_study.json`. Run records
retain unavailable per-attempt model/usage/time/cost telemetry as null.

## Constructive two-AND prefixes and exact auxiliary closures — 2026-10-04

The current fixed eighteen-product family still has no complete 27-AND AES
construction. The three unrestricted two-product SAT searches (free, excluding
the original auxiliary envelope, and fixing only the original first product)
each returned `INDETERMINATE`, exit 15, under a 120-second solver budget. Actual
command wall times were 135.77–136.02 seconds. Twelve brute-force controls and
the fully fixed original AES prefix passed. Independent review checked 31
small encoded instances, including 15 envelope-exclusion cases. Timeouts are
inconclusive.

A constructive alternative fixes two operand functions f,h in W and writes
q=f*g and p=h*(v+alpha*q), where g,v are arbitrary affine forms in W and
alpha,beta are bits. Requiring p+beta*q in T gives the linear relation
h*v+(alpha*h+beta)*f*g in T. On its kernel, q modulo T and the relation modulo
W must both be nonzero. These two linear maps may be nonzero on different
kernel generators; their sum then supplies a valid witness. This avoids
discarding feasible systems merely because no individual generator satisfies
both conditions. A second operand plane in W+q always intersects W, so the
form covers every two-product prefix if all f,h in W are enumerated. The
actual search uses a finite factor pool and makes no such coverage claim.

The pool contains 161 constant-free coefficient masks: available source wires,
individual W basis factors, and single-coefficient neighbors of the known
first factors. Its 103,684 fixed systems have 38 feasible cases. Sampling kernel
generators and their pairwise sums produced 58 distinct realizable auxiliary
envelopes, 57 different from the original and 56 absent from the preceding 79
proposal sample. These are two-product prefixes only. A separate low-pivot
implementation replayed every fixed system and agreed on feasibility and
kernel dimensions. It also verified all 58 truth witnesses and independently
replayed the public source against scalar AES on all 256 inputs.

The implementation is retained as
`workspace/aes-256-gcm/tools/search_two_and_prefix.py`. Its rerun reproduces
the same fixed-system counts, kernel dimensions and exact witness list from
the run-local input. The measured search times were 39.44 seconds for the
run-local program and 40.47 seconds for the retained tool. These are algorithm
wall times on the host, not agent time, RTL simulation or a fair speedup
comparison against unrestricted SAT. Four tool tests cover nullspaces,
exhaustive affine operand choices, malformed inputs and preserving existing
output evidence. The exhaustive feasibility test includes 966 positive and
1,974 negative cases. Independent extraction controls include 37 cases that
require combining two kernel generators.

Constructive extensions using source gates and finite dynamic left-factor
pools stalled in all 58 envelopes: 56 ended at dimension 29, one at 33, and one
at 30. This heuristic stagnation alone does not prove impossibility. Three
selected new envelopes received complete product scans instead. A useful
operand plane modulo constants meets a codimension-one hyperplane; changing
its basis changes the product only by current-span functions. Therefore
restricting the left operand to that hyperplane preserves every useful
quotient product while halving the number of left forms. All three scans
returned `EXHAUSTED_NO_EXTENSION`:

- Prefix index 0: dimension 29, 134,217,727 left forms, 213.73 seconds command wall.
- Prefix index 1: dimension 29, 134,217,727 left forms, 222.73 seconds command wall.
- Prefix index 53: dimension 30, 268,435,455 left forms, 442.89 seconds command wall.

The total is 536,870,909 forms. Every introduced product is constructively
available inside its fixed S=T+q. Complete absence of another product makes
the final span the least S-constrained product closure of W. Since AES is
outside each closed span, every completion confined to each of these three
envelopes is excluded. This does not exclude the remaining 55 witnessed
envelopes, all other auxiliaries, changed retained gates, or arbitrary AES
circuits. Independent checks verified all 2,324 serialized matrix entries,
32 small hyperplane quotient comparisons, and 12 actual-binary controls
(six positive, six negative). The large scans were observed, not independently
repeated. No candidate RTL changed, so no new physical or security metrics
are claimed.

Primary web sources were checked again on 2026-10-04. The current
[NIST AES circuit table](https://raw.githubusercontent.com/usnistgov/Circuits/master/data/slp/aes/aes-sbox/README.md)
still lists 28 ANDs as its minimum and credits the A28 contributions to Milad
Nasr, communicated 2026-09-24. That table is not an optimality proof. Find,
Smith-Tone and Turan's
[two-AND function study](https://www.nist.gov/publications/number-boolean-functions-multiplicative-complexity-2)
(2015 preprint, 2017 journal publication) establishes prior work on this
structure. Soeken's
[SAT synthesis paper](https://arxiv.org/abs/2005.01778) (2020) establishes prior
work on exact multiplicative-complexity synthesis with symmetry breaking.
The local MC2 PDF retrieval failed with HTTP 403 and is retained as a failure;
the primary publication record supports the limited attribution above.
Neither the local application of linear kernels nor the scoped negative
results establish a world first.

Detailed evidence is retained in `runs/aes-linear-two-prefix-20261004/`,
`runs/aes-two-gate-auxiliary-20261004/`, the corresponding review directories,
`runs/aes-two-prefix-prior-art-20261004/`, and
`runs/aes-two-prefix-closeout-20261004/`. The compact committed record is
`workspace/aes-256-gcm/reports/sbox_two_prefix_study.json`; unknown model,
per-attempt tokens, agent time and cost telemetry remain explicitly null in
schema-validated run records.

## One-auxiliary envelopes and four-terminal windows — 2026-10-04

The next search permits a coordinated change to the depth-four public
131-total-gate source: replace the ten-AND a13 cone using nine ANDs after
eighteen retained products. This is the earlier full-joint SAT problem, now
analyzed through its truth-function spaces. W has dimension27; adding the
eight AES outputs gives T of dimension35. A successful nine-gate replacement
can have at most one independent function direction outside T.

First, an exact unrestricted first-product test exhausts all 67,108,863
nonconstant left forms in W and finds no useful product inside T. This proves
that any successful nine-gate replacement from this fixed W must begin with
an outside-T auxiliary, after discarding any redundant gates. It does not
identify the auxiliary or prove nine gates impossible.

The general rank-slack-one reduction is to saturate W using products inside
T, then consider realizable products q outside T and compute exact closure
inside S=T+q. Saturation is necessary in general: restricting the first
auxiliary's operands to the original W can otherwise miss solutions. Here the
initial exact exclusion proves the saturation is W itself. For a fixed S,
adding any realizable useful product inside S is safe: all available functions
remain available, and monotone product closure reaches a unique least closed
space regardless of choice order. The independent review checks this
reduction against 35 target spaces from a complete three-input, three-gate
space enumeration. An additional unreachable-input negative control passes.

A finite heuristic proposal set contains the original a13 factor pair, its
52 single nonconstant-selector-bit changes, and 32 seeded random factor
pairs. Deduplicating the resulting S spaces leaves 79 outside-T envelopes.
All79 pass a relaxed linear-span closure test, demonstrating that this
relaxation does not discriminate the proposals. It is not evidence that the
envelopes contain realizable AES circuits.

Three envelopes receive constructive checks. The first selector mutation
and first random proposal each fail an unrestricted first-product test after
q is introduced: 134,217,727 left forms per envelope. These two exact closure
dead ends exclude those particular envelopes, not all79 proposals or all
possible auxiliaries. The original a13 envelope allows six original products
including a13 to be replayed inside S, reaching dimension33. The missing
original functions are four terminal products: a18,a22,a23,a28. A fixed
pre-tail-factor search cannot add another useful product, exhausting
8,388,607 left forms. A three-gate unrestricted joint solve remains
INDETERMINATE after122.040 seconds; no impossibility claim follows.
A smaller native-XOR SAT formulation asks only for any first useful product,
with both operands unrestricted and a nonzero selector over the three target
quotient directions. Twelve brute-force SAT/UNSAT controls pass, but the AES
instance also returns INDETERMINATE under its120-second budget. Reducing the
question to one product has therefore not yet resolved this envelope.

Root independently reconstructs the source and checks all 2,870 serialized
matrix entries from these four enumeration problems and every warm-start
witness. The large scans themselves are not independently repeated. The
square search executable is byte-identical to the previously independently
tested engine. Evidence: `runs/aes-auxiliary-first-20261004/` and
`runs/aes-auxiliary-review-20261004/`.

The auxiliary warm start also exposes a terminal four-to-three family absent
from the earlier two/three-root inventory. Across nine public sources, an
inventory checks all 6,435 four-element subsets of the thirteen terminal
ANDs per source. Exactly170 are rank-eligible; all have retained dimension33
and AES target dimension36. Of these,130 contain a previously excluded pair
or triple. Exact space-containment checks lift those earlier fixed-P closure
exclusions to the larger windows. The other40 source windows reduce to22
distinct canonical(P,W,T) truth-space problems. This deduplication checks
actual equality, not a conjectured affine input equivalence.

One of the22 problems exactly matches the already completed original-a13
warm-start search and is reused. The other21 run new exact fixed-P closures.
There are189,278,567 new left-form evaluations, including six successful
intermediate stages and176,160,747 forms across the21 final exhaustive
negative stages. Eighteen of22 problems stop at dimension33, two at34, and
two at35; none reaches36. Every positive witness, every source-space grouping,
and all20,056 new product-matrix entries pass a separate review. The full new
scans are not independently repeated. Thus all170 rank-eligible terminal
four-to-three windows are excluded **only when every replacement product has
one factor in the fixed pre-tail space P**. Arbitrary both-non-P factors,
changed retained functions, and larger replacements remain open. Evidence:
`runs/aes-four-terminal-20261004/`.

A further exact symmetry observation can reduce future unrestricted product
enumeration: after omitting constants, any useful product has two independent
operand vectors. Their plane intersects every codimension-one coordinate
hyperplane. A change of basis within the operand plane changes the product
only by already available functions, so restricting the left factor to one
such hyperplane and leaving the right unrestricted preserves every product
modulo W. All32 small exhaustive quotient-product controls agree. This is a
proved enumeration reduction, not a measured runtime gain or a novelty claim;
it does not justify restricting the left factor to a higher-codimension P.

No correct27-AND AES circuit, world-first result, global AES lower bound, or
physical implementation result has been obtained. The compact result is
`workspace/aes-256-gcm/reports/sbox_auxiliary_window_study.json`. Future work
must leave the excluded fixed-P families or choose a different auxiliary
envelope; repeating their closure searches cannot yield a reduction.

## Rank-tight replacement windows — 2026-10-04

No correct 27-AND AES S-box or world-first result was obtained. This study
establishes exact lower bounds for three fixed retained-circuit families and
restricted exclusions for terminal replacements. It does not establish the
global multiplicative complexity of AES.

An inventory of nine public 28-AND sources examines all 32,886 sets of exactly
two or three roots and their forward dependency cones. Deduplication within
each source leaves 5,075 windows. The necessary output-rank test admits 29
windows removing fewer than ten gates: two pairs, 24 triples, and three
nine-gate cones. These are rank-eligible windows, not synthesized reductions.
The nine-gate cases are also single-root cones rooted at depth-four a15;
the earlier search's root-depth filter omitted them. They are not newly
discovered multi-root structures. Evidence:
`runs/aes-multiroot-windows-20261003/`.

### Three exact nine-to-eight exclusions

The 124-, 128-, and 150-total-gate public sources each contain a nine-AND a15
cone with nineteen dependency-closed retained ANDs. Let W contain constant,
the eight raw inputs, and those retained functions, and let T additionally
contain the eight AES outputs. Exact 256-row truth-space ranks are
dim(W)=28 and dim(T)=36 in all three cases.

Eight new ANDs can add at most eight independent functions. If they implement
AES with an arbitrary affine decoder, the final available span must therefore
equal T. Every intermediate product must lie in T, and the first useful
product must lie outside W. This reduces an arbitrary sequential eight-gate
replacement to the necessary first step: find f,g in W with fg in T but not W.
Both factors are unrestricted within W; no pre-tail-factor restriction is
imposed here.

An exact Gray-code/kernel enumeration finds no such first step in any case.
It exhausts 134,217,727 nonconstant left forms per source, or 402,653,181
across the three problems, solving for every right form by linear elimination.
Operand constants may be omitted because their contributions are in W.
Consequently these fixed nineteen-retained families require at least nine
additional ANDs; each original nine-gate witness attains that bound. The
original a15 product is outside T, so the known nine-gate implementation does
not contradict the obstruction. Other original products can also lie outside
T; the exact lists are retained rather than assumed identical across sources.

The root enumerator passes 24 brute-force random controls and three named
negative/sequential controls. Independent review reconstructs all three
sources on all 256 inputs, verifies every one of the 2,187 serialized product
matrix entries, and tests the actual executable against 48 further exhaustive
small cases. The three full AES enumerations were not independently repeated.
The relaxed linear product closure reaches dimensions 28→32→36, so a mere
linear-span relaxation does not prove this result; the absence of an actual
factorable first product is essential. Evidence:
`runs/aes-tight-cone-closure-20261004/` and
`runs/aes-tight-cone-review-20261004/`.

### Terminal pair and triple replacements

Removing a18/a27 from the 124-gate source or a21/a28 from the 128-gate source
leaves 26 ANDs and a 35-dimensional retained space W. The AES outputs require
one additional function. In both cases, exhaustive enumeration excludes a
replacement product with one factor in the 24-dimensional pre-tail space P
and the other anywhere in W: 8,388,607 nonconstant left forms per case.
An independent quotient/kernel construction repeats both complete searches
and agrees, including the full rank histograms. Source/constant/symmetry
audits pass; the original and replay engines have 16 and 12 small brute-force
controls respectively. Unrestricted W×W searches using two solvers remain
INDETERMINATE/UNKNOWN after their 90-second budgets. Those outcomes are not
proofs of impossibility.

An initial known-positive solver probe also timed out and triggered an
incorrect completion-time assertion. That failed attempt is retained. The
corrected control fixes a known witness in the full-space CNF and checks every
serialized constraint; a separate CP control uses the known three-dimensional
operand span. Neither is misrepresented as a freely solved full-space control.
Evidence: `runs/aes-terminal-pair-repair-20261003/`, including `review/`, and
`runs/aes-pair-repair-audit-20261003/`.

The two triples not containing either excluded pair are a17/a23/a25 in the
124-gate source and a19/a23/a25 in the 150-gate source. Each has retained
dimension34 and target dimension36. With one factor per replacement fixed to
P, exact sequential closure finds a first useful product but stops at
dimension35: each final stage exhausts all 8,388,607 left forms. Root verifies
both first witnesses and independently repeats both full final-stage searches
using exact-image membership rather than the original kernel test. Exhaustive
BFS controls on 32 small spaces check that choosing another first product
does not evade the fixed point.

For the other 22 triples, exact containment checks give W⊂V⊂T, where V is
the corresponding pair's retained space, with dimensions34,35,36 and P⊂W.
The pair exclusion implies (P·V)∩T⊂V. Any T-constrained replacement sequence
therefore stays in V by induction, while AES requires a function outside V.
Rank tightness forces every successful two-gate sequence to stay in T, so this
excludes those 22 cases under the same fixed-P-factor restriction. It does not
exclude replacements with both operands outside P. Evidence:
`runs/aes-terminal-triple-repair-20261004/` and
`runs/aes-triple-closure-review-20261004/`.

The exhaustive pair exclusions also supply a sound cut for the unrestricted
W×W solver: a feasible two-dimensional operand plane cannot intersect P in a
nonzero function. In the existing highest-pivot canonical basis, this means
the smaller-pivot operand must have a non-P component. All 59,988 small
coefficient-plane controls verify that equivalence, and two planted tail×tail
SAT controls pass full serialized-model/truth checks. Both new full-space
searches still return INDETERMINATE, exit15, after approximately122 seconds
each. Thus the cut is verified, but it has not resolved the unrestricted
problem or demonstrated a performance advantage. Evidence:
`runs/aes-full-pair-cut-20261004/`.

The [pinned NIST circuit listing](https://raw.githubusercontent.com/usnistgov/Circuits/b402f09ee22fd26cc58a2904bf5bd524fcd0cbcc/data/slp/aes/aes-sbox/README.md)
and [Soeken's SAT synthesis paper](https://arxiv.org/abs/2005.01778) were checked
again on October3 UTC. The public28-AND circuits are prior work, and SAT
synthesis/symmetry breaking are established methods. No novelty claim follows
from these local exclusions or an unsuccessful literature search. No physical
area, timing, power, or leakage measurement is produced by this study. The
compact record is `workspace/aes-256-gcm/reports/sbox_tight_window_study.json`.

Primary-source follow-up located the authors'
[implem-sbox code](https://github.com/seduval/implem-sbox), inspected at commit
`6500beee71bd1ee246434b17811d423002a233ba`. Its README lists precomputation for
four through seven input bits, but its CLI text says 16–64 LUT entries; it
does not document full eight-bit AES support. This documentation discrepancy
and the lack of a full-AES claim must be resolved before treating the tool as
a drop-in search backend. No external code was executed and no precomputation
dataset was downloaded. The pinned README and fetch status are retained in
`runs/aes-tight-window-closeout-20261004/`. The related TCHES2026 paper's
[author listing](https://seduval.github.io/research/) verifies its title,
authors and publication date; the publisher's DOI page was unavailable during
this check, so no technical conclusion is attributed to unread paper text.

## Auditing the local-search barrier — 2026-10-03

No correct 27-AND circuit or world-first result was obtained. The current
local-search evidence explains a limitation of the search representation,
not a general limitation of AES implementations.

An independent audit of the previous 64-state walk and its terminal choice
found that **only gate index 14, the first tail product, changed**. All other
26 gate selectors and operand functions stayed fixed. Its distinct full
function spaces were real, but each was only a one-product extension of the
same 35-dimensional space, inside the already excluded `P x W` repair family.
The complete initial radius-two neighborhood contains 2,492 deficit-one
assignments and 991 distinct full spaces; every one has the same core span
when gate 14 is omitted. Root independently replayed all 2,492 assignments
using a different elimination direction. Evidence:
`runs/aes-neutral-structure-20261003/`, including `neighborhood/`, and
`runs/aes-deficit2-bridge-20261003/neutral-cross-check.json`.

One recommendation from that review was incorrect: replacing the first tail
gate by products in two distinct singleton-tail cosets was not an unsearched
family. The earlier twelve `t_i + P` enumerations already permitted arbitrary
right operands in W and therefore cover those 66 pairs. The structural audit
remains valid; this recommendation is explicitly corrected in
`runs/aes-deficit2-bridge-20261003/review-erratum.json`, without overwriting the
original review record.

A new bounded walk permits temporary output-rank deficit two and chooses
states with distinct **core** spans, omitting only gate 14 from its diversity
key while fully reevaluating all downstream gates. It checks 22,600,512
neighborhood assignments across 32 states, including 31 deficit-two states,
and finds no repair. This time four tail gates vary, but the first fourteen
early/middle gates still do not. A full deterministic repeat agrees; all
selected states are independently replayed on 256 input rows. A nonvacuous
toy control independently enumerates 2,024 neighbors across eight states and
verifies the minimum-deficit/diversity selection rule, including a transition
from deficit two to one. The diversity key is a heuristic, not a
completeness-preserving equivalence for sequential circuits. Evidence:
`runs/aes-deficit2-bridge-20261003/`.

An exact radius-three search tests **278,740,836** selector assignments, split
into disjoint even/odd first-edit shards. None has output deficit zero. Together
with the earlier radius-zero/one/two enumeration, this excludes all
279,447,103 assignments within three selector-bit changes of this particular
27-AND encoding. Eight complete small-instance histograms agree with an
independent Python evaluator; combinatorial counts check shard coverage. The
two AES shards finish successfully in 374.257 and 373.308 seconds of observed
command wall time. They run concurrently, so these are not additive elapsed
experiment time. No second full AES radius-three replay is claimed. Evidence:
`runs/aes-radius3-repair-20261003/`.

Finally, requiring a changed pre-tail function space and allowing deficit up
to three produces **no eligible first move**. A complete radius-two
classification finds that changing this prefix span requires deficit at least
six: one assignment has deficit six, 11,364 have seven, and 404,953 have eight.
The deficit-six witness is independently replayed. This is a local landscape
measurement for the recorded selectors, not a global lower bound, an invariant
of all equivalent representations, or evidence that coordinated changes are
impossible. Evidence: `runs/aes-prefix-bridge-20261003/`.

The next search should change multiple dependent factors jointly, change the
representation, or select a different nonlinear construction. More steps in
the same low-deficit tail orbit do not address the observed prefix barrier.
The [pinned NIST frontier](https://raw.githubusercontent.com/usnistgov/Circuits/b402f09ee22fd26cc58a2904bf5bd524fcd0cbcc/data/slp/aes/aes-sbox/README.md)
and [Soeken's SAT-synthesis paper](https://arxiv.org/abs/2005.01778) were checked
again during this work. Neither local search nor SAT-based XOR–AND synthesis
is presented as a new technique. Physical area, timing, power and leakage
remain unmeasured by these searches. The compact record is
`workspace/aes-256-gcm/reports/sbox_local_barrier_study.json`.

## Joint nonlinear search beyond the fixed interfaces — 2026-10-03

The fixed-interface obstruction below motivated three broader searches. None
has produced a correct 27-AND AES S-box or established a world-first result.

First, the single-product repair was allowed to use a retained tail function
in its left operand: each of the twelve cosets `t_i + P`, where P is the
23-dimensional pre-tail span. The right operand is arbitrary in the retained
35-dimensional span. For the 131-gate outer source with a16 removed, every
one of the 4,194,304 left forms in each tested coset failed: 50,331,648 forms.
This tests only twelve of 4,095 nonzero tail cosets, not every retained-space
left operand. The new offset enumerator includes step zero. A separate audit
reconstructs the source/matrices, brute-forces 24 small controls, checks
first/last-step probes and sampled AES steps, and verifies constant omission;
it does not independently repeat all 50 million forms. Evidence:
`runs/aes-tail-coset-repair-20261003/`, including `review/`.

Second, an inventory of nine public 28-AND circuits and 252 dependency-closed
single-root cones identifies a ten-gate middle-to-tail cone with room for a
one-AND reduction by the necessary output-rank test. In the 131-gate source,
remove a13 and its nine nonlinear descendants. The 18 retained ANDs plus
inputs and constant span 27 functions; the eight AES outputs add eight
independent functions. The new solver allows nine arbitrary sequential ANDs,
with both operands using any retained signal or earlier replacement, and an
arbitrary affine output decoder. It constrains all 256 reachable input rows,
not 27 fictitiously independent inputs. Removed internal functions, AND depth,
and the earlier quotient envelope are not fixed.

The original ten-gate cone passes positive controls with all factors fixed
and with its root factors free. An independent review checks all source
cones, 40 small brute-force comparisons, lexical symmetry, and the scalar AES
control. The fully free nine-gate instance returns **INDETERMINATE**, exit 15,
after 60.823 seconds. A 24-row counterexample-guided solve returns a circuit
that fails all 232 unchecked rows; after adding sixteen counterexamples, the
40-row solve is also inconclusive. These are not UNSAT results. Evidence:
`runs/aes-joint-method-20261003/`, including `review/`.

A canonical operand-plane variant strips constant selectors and chooses an
echelon pair for each AND. The product changes only by previously available
affine functions, which later factors and the decoder can absorb. All 40
small brute-force outcomes agree; 4,752 ordered affine-pair checks verify the
normalization identity; the normalized ten-gate control passes scalar AES on
all 256 inputs. The canonical nine-gate solve nevertheless remains
INDETERMINATE after 63.589 seconds. Evidence:
`runs/aes-joint-canonical-20261003/`.

Third, the invalid 27-AND 9+5+13 hybrid was used as a local-repair seed.
All 706,267 selector assignments within Hamming distance two of its 1,188
affine-factor selectors were evaluated with a free affine output decoder.
None completes AES. There are 2,492 assignments, including the seed, that
retain a one-function output deficit; 2,134 introduce a function outside the
seed's available span. A deterministic, seeded walk through 64 distinct
function spans evaluates 45,201,024 additional neighborhood assignments,
without finding a correct circuit. These are evaluation counts, not counts
of globally distinct circuits. A second execution reproduces the walk;
separate low-pivot elimination checks every retained state on all 256 rows,
semantic distinctness, and one/two-bit adjacency. Eight complete toy
neighborhood histograms and a known one-bit repair control pass. This remains
a bounded local search, not an AES lower bound. Evidence:
`runs/aes-local-nonlinear-repair-20261003/`.

The synthesis concepts themselves are established prior art: see
[Soeken, arXiv:2005.01778](https://arxiv.org/abs/2005.01778) for abstract XOR–AND
selectors, symmetry reduction and counterexample-guided refinement, and
[Haaswijk et al., DAC 2018](https://people.eecs.berkeley.edu/~alanmi/publications/2018/dac18_topo.pdf)
for topology-family exact synthesis. The sources were checked on 2026-10-03.
The useful next search must cross a larger structural neighborhood or change
the selected cone/topology; extending an inconclusive timeout is not evidence
of novelty. No physical area, timing, power, or security metric was measured
by these Boolean searches. The compact record is
`workspace/aes-256-gcm/reports/sbox_joint_nonlinear_study.json`.

## Nonlinear stage splicing and a restricted obstruction — 2026-10-02 to 2026-10-03

The public 28-AND circuits use either 10+5+13 or 9+6+13 nonlinear stages,
as described in the
[pinned source](https://raw.githubusercontent.com/usnistgov/Circuits/b402f09ee22fd26cc58a2904bf5bd524fcd0cbcc/data/slp/aes/aes-sbox/aes-sbox-a28-ad5-g124-gd27-xx96-26.circ.txt).
The experiment tried 9+5+13 by combining compatible stages. All selected
AND operands can be reconstructed from previously available signals, but
the resulting 27 products omit one independent AES output function. Such
a splice is therefore not a correct AES circuit.

Three representative outer circuits (131, 141 and 177 gates, all 28 ANDs
and AND depth four) were combined with the 124-gate circuit's five-AND
middle. For each, only one of the thirteen single-tail removals leaves an
output deficit that one new product could fill. Exhaustive searches found
no repair in the original 13-dimensional tail operand space. A wider exact
enumeration then tested every nonconstant left form in the 23-dimensional
pre-tail space and solved the right form over all 35 retained signals.
All 4,194,303 choices per case failed: 12,582,909 in total. This covers
either factor lying in the pre-tail space, including arbitrary affine
forms of the retained tail signals in the other factor. It does not cover
two factors with independent nonzero cosets outside that space. The general
35-by-35 CP-SAT and CryptoMiniSat runs timed out without a conclusion.

There is a stronger obstruction to changing only the norm-based middle.
Let `N=x^17`, and allow arbitrary XOR/NOT operations and AND gates on its
four bits. Keep the nine early gates and the thirteen tail gates **with
their original operand truth functions** fixed. For each of the three
pinned outer circuits:

1. The affine functions of N form a space of dimension five, including the
   constant. The required tail operands additionally require all four
   coordinates of `N^-1`.
2. Completing the AES outputs requires one further function of N. Together
   these functions span a ten-dimensional space T. The retained source
   and exact intersection calculations establish this necessity; it is
   not inferred from the failed heuristic searches.
3. Five ANDs could add at most five dimensions to the affine input space.
   To produce T with five ANDs, every intermediate AND output would have
   to lie in T.
4. Exhausting all 32-by-32 pairs of affine norm functions finds **no
   non-affine product in T**. Hence the first useful AND cannot lie in T,
   contradicting a five-AND construction.

Thus this precisely defined middle stage needs at least six ANDs. The
original six-AND middle is also verified to be realizable using only norm
bits, so six is attained in this restricted family. This does not establish
a global 28-AND lower bound for AES. Refactored tail operands and different
outer gates are outside the claim. The known 60 distinct middle-stage self-equivalences all preserve
the observed one-function deficit in the tested splices.

The result was strengthened to permit the middle to use **all early signals**,
including the raw input bits and nine early AND outputs. Their span A has
dimension 18. The tail operands increase that to 22; adding tail outputs
gives dimension 35, and adding AES outputs gives a space V of dimension 36.
If five middle ANDs were enough, their available span M would have dimension
at most 23. The required interfaces imply `V` is contained in `M + tail`,
whose dimension is at most `23+13=36`. Equality therefore forces every
middle output to lie in V. The first useful middle AND has algebraic degree
at most four, since its inputs have degree at most two. The degree-at-most-four
part of V has dimension 19, extending A by just one direction. Exhaustive
factor enumeration excludes that direction for all 131,071 nonconstant left
forms, with an exact linear solve for the right form. All three cases fail.
The original six-AND middle attains this stronger restricted bound as well.

An independent implementation verifies the scalar AES truth tables, the
18/22/35/36 dimensions, the degree-four intersection, and all 393,213 left
factor cases using a separately written C++ engine. This result still fixes
the early gates and original tail operand functions, and requires the middle
to finish before the tail. It does not bound refactored operands, interleaved
stages, or arbitrary AES circuits. Evidence is in
`runs/aes-middle-initial-span-20261003/`, including the independent proof and
audit under `review/` and the dependency-free Python replay under `promoted/`.

For the failed 9+5+13 hybrid, all 234 two-tail replacement windows are excluded
when each new product has one factor in the pre-tail span and the other in
the retained span, with neither replacement feeding another. Of these,
198 fail the output-dimension requirement and 36 reduce to the prior exhaustive
single-product exclusion. Scanning every nonempty tail subset identifies
four removals as the first size with room for an auxiliary function: two
such windows per outer circuit. Each was tested with all 31 nonzero directions
in the five-dimensional space generated by missing AES outputs and removed
tail products. No set of at most four attainable product directions covers
the required outputs. This additional restriction leaves functions outside
that five-dimensional space and sequential new products open. Retained
records are in `runs/aes-two-tail-repair-20261003/` and
`runs/aes-four-tail-repair-20261003/`.

An independent implementation reconstructed all six four-tail problems,
checked the positive witnesses, replayed each 4,194,303-left-form search,
and checked every subset of at most four attainable directions. All six
negative results agree; twelve small brute-force controls also pass.
Evidence is under `runs/aes-four-tail-repair-20261003/review/`.

A subsequent pilot allows a replacement product to feed later replacements,
while retaining the same five-dimensional quotient envelope. For the two
four-tail windows of the 131-gate outer circuit, it tests all three
four-dimensional subspaces containing the required three-dimensional output
space. Monotone product-span closure reaches a fixed point without completing
the outputs in all six cases. The other two outer circuits were not included
in this sequential pilot; functions outside the envelope and products with
both factors outside the pre-tail span remain open.
`runs/aes-joint-candidate-20261003/run.json` retains this scope. Its materialized
28-AND control passes an independent scalar AES check on all 256 inputs, but
has 600 total gates with unoptimized affine reconstruction. Both operands of
the added repair lie in the pre-tail span, so this control merely restores a
sixth middle gate and is not an escape from the bound or a frontier result.

The small verifier is
`workspace/aes-256-gcm/tools/analyze_sbox_stage_splice.py`; its report includes
16-bit truth-vector generators so the finite obstruction can be checked
without a SAT solver, plus the wider first-product enumeration. Evidence is retained in `runs/aes-norm-stage-bound-20261002/`,
`runs/aes-stage-splice-20261002/`, `runs/aes-stage-splice-wide-20261002/`, and
`runs/aes-splice-algebra-20261002/`. No smaller correct AES circuit, physical
improvement, or world-first has been established. The obstruction directs
further work toward changing the nonlinear stages jointly.

A 2026-10-03 web search for AES 27/28-AND lower bounds and subspace-based
multiplicative complexity did not establish novelty of this obstruction.
General low-multiplicative-complexity and component-optimization techniques
are established; see
[Boyar, Matthews and Peralta](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=908384)
and [Small Low-Depth Circuits for Cryptographic Applications](https://pmc.ncbi.nlm.nih.gov/articles/PMC6463518/).
The limited search provides no basis for a world-first claim.
The pinned NIST table was reopened on 2026-10-03 and still credits the public
28-AND constructions to Milad Nasr. A search hit mentioning 27 AND gates in
[Jeon et al.](https://eprint.iacr.org/2024/1996.pdf) describes an intermediate
field multiplication, not a complete 27-AND AES S-box.

## Self-equivalence sweep and moving frontier — 2026-09-20 to 2026-10-02

The 2026-10-02 primary-source check first found a 137-gate, 29-AND circuit
on NIST's website, then found a substantially stronger frontier in its
[pinned official repository](https://raw.githubusercontent.com/usnistgov/Circuits/b402f09ee22fd26cc58a2904bf5bd524fcd0cbcc/data/slp/aes/aes-sbox/README.md).
The latter includes **28 AND + 96 XOR/XNOR = 124 gates**, gate depth 27 and
AND depth 5. The README attributes the 28-AND contributions to Milad Nasr
(@ Anthropic), communicated on 2026-09-24. These are public prior art, not
our discovery. The source hash is
`dcae5252bc89603aca763a0af914ffbea0026e4a0d59d0a3caff408e19e502ac`;
the pinned upstream revision is `b402f09ee22fd26cc58a2904bf5bd524fcd0cbcc`.
The source describes a tower-field construction with norm `N=x^17`, inversion
of N in GF(16), and products involving `x` and `N+N^-1`. Its contributor's
Lean proof claim was not independently replayed here.

The retained inventory verifies all 55 forward AES S-box files in the three
selected repository directories over all 256 inputs and checks their source
Git blob hashes. It is not a survey of every global implementation. Importantly,
124 is **not** an unrestricted total-gate record: the same repository lists
110-gate circuits with 32 or 34 ANDs. A candidate must state its AND-count,
depth, or physical objective before making a comparison. The previous
29-AND/108-affine and 29-AND/107-affine novelty thresholds are superseded.
The nine-circuit masking results below remain historical controlled comparisons,
not a sweep of this updated library.

Bounded local resubstitution did reduce the public 137-gate source to
**136 gates (29 AND, 107 affine), depth 33, AND depth 6**. The strict
AND/XOR/XNOR circuit passes an independent 256-input replay. However, the
public 28-AND/124-gate source dominates it in all four metrics. This is a
real local reduction, not a frontier improvement or world-first. The same
local optimizer left the public 124-gate source unchanged. Its bounded
95-affine-gate exact-synthesis attempt returned no candidate at a 10,000-conflict
limit; that result is not an UNSAT proof or a global lower bound.

Meanwhile, a bounded search tested all 2,040 multiplicative/Frobenius
self-equivalences of AES. With `F(x)=L(inv(x)) xor 0x63`, the maps
`A(x)=a*x^(2^k)` and
`B(y)=L((a*L^-1(y xor 0x63))^(2^(8-k))) xor 0x63` satisfy
`B(F(A(x)))=F(x)`, including zero, for nonzero `a` and `k=0..7`.
An independent implementation checked all 522,240 parameter/input pairs.
This technique is already used in hardware optimization; see Nakashima,
Ueno and Homma, [IEEE TCAS-II 2022](https://doi.org/10.1109/TCSII.2022.3185632),
whose primary text explicitly describes the 255-by-8 offset search. The
[SAC self-equivalence paper](https://sacworkshop.org/SAC20/files/preproceedings/02-WhiteBox.pdf)
also documents the group size. Neither algebra nor the search method is
claimed as novel.

The local experiment retains the old 138-gate circuit's 101-gate middle and
resynthesizes only its affine boundaries. It includes the cost of transformed
input bits consumed later and tracks XNOR phases. Every generated circuit is
checked against the independent AES oracle over all 256 byte values.

| Heuristic, all 2,040 pairs | Best total gates | Identity total gates |
| --- | ---: | ---: |
| Common-pair factoring | 149 | 151 |
| Greedy exact-word-distance scoring | 147 | 147 |
| Same scoring with phase-aware XOR/XNOR emission | 144 | 144 |

The last sweep additionally asserts retention of all middle gates. The
backend passes symbolic, determinism, invalid-input, conflicting-phase,
fanout, and resource-guard tests. Exact word distances do **not** make the
greedy circuit search exact. In particular, its identity result remains
worse than the known 138-gate construction. These negative results reject
these heuristic candidates, not the entire self-equivalence design space.

A useful necessary bound reduces unproductive work: the original prefix has
13 gates and attains its distinct-target lower bound. Every nonidentity map
increases that bound because transformed input bits are not free. Checking
whether all targets can be reached using only other target forms strengthens
2,024 bounds by one gate. The resulting histogram is
`13:1, 14:1, 15:13, 16:150, 17:756, 18:1119`; only `a=8,k=0` has a
nonidentity bound of 14. These are affine-prefix bounds, not whole-circuit
lower bounds. With the fixed 101-gate middle, beating the older 137-gate
reference requires prefix plus suffix at most 35 gates; that threshold no
longer implies an advance over current public prior art.

The phase-aware search was subsequently applied to the newly pinned sources:

| Source | Retained middle | Pairs | Best total gates | Outcome |
| --- | ---: | ---: | ---: | --- |
| 29 AND / 137 gates | 107 | 2,040 | 137 | Matches source, no improvement |
| 28 AND / 124 gates | 97 | 2,040 | 126 | Worse than source |

Both completed sweeps check every candidate over all 256 inputs. The 28-AND
source exposed two tool assumptions: outputs may precede the final AND, and
complement absorption must not rewrite protected middle gates. Both failed
attempts are retained separately, both issues have regression tests, and the
corrected sweep passes. The tests do not establish that this restricted
boundary model or greedy heuristic is an effective search of all circuits.
An entire repeat of the corrected 28-AND sweep returns identical result rows
and a byte-identical best candidate; only the measured runtime differs.

Reproducible tools and the compact report are in
`workspace/aes-256-gcm/tools/search_sbox_self_equivalence.py`,
`tools/xor_distance_heuristic.py`, and
`reports/sbox_self_equivalence_study.json` under that workspace. Full run
records retain scripts, logs, hashes, candidates and failed comparisons in
`runs/aes-self-equivalence-*/`, `runs/aes-frontier-inventory-20261002/`,
`runs/aes-new137-resub-20261002/`, `runs/aes-new124-resub-20261002/`,
`runs/aes-new137-orbit-20261002/`, and
`runs/aes-new28-orbit-protected-20261002/`.
No new chip, mapped improvement, leakage result, or world-first follows.

## Equal-effort masked-S-box scheduling test — 2026-09-18, reviewed 2026-09-19

The next falsifiable hypothesis was that better register scheduling could
remove the area penalty of the public 29-AND S-boxes without losing their
randomness and delay advantages. A fixed-topology CP-SAT model jointly chooses
integer operation cycles and the orientation of asymmetric HPC2 operands.
It minimizes shared alignment-register bits at eight-cycle latency. Each
transaction still receives an independent random bit per AND at cycle zero.
Internal gadget registers and the valid pipeline are constant for each
topology; they are excluded from the optimization objective, not from mapping.

All nine models returned `OPTIMAL` with equal objective and bound, and their
emitted alignment-register counts independently matched the model. This is a
solver result for that precise register-cost model, without an external proof
certificate. It does not establish minimum mapped area or delay, or a lower
bound for alternative Boolean circuits, gadgets, or randomness interfaces.

| Circuit | Alignment bits before → after | Nangate45 area (um²) | ABC delay (ps) | Fresh bits |
| --- | ---: | ---: | ---: | ---: |
| classic-g113-d27 | 389 → 366 | 4,540.620 | 390.03 | 32 |
| a29-ad5-g140-d37 | 445 → 415 | 4,729.480 | 732.57 | 29 |
| a29-ad5-g141-d32 | 445 → 415 | 4,741.716 | 501.30 | 29 |
| a29-ad5-g161-d24 | 473 → 427 | 4,865.406 | 416.36 | 29 |
| a29-ad5-g184-d20 | 525 → 468 | 5,101.614 | 449.39 | 29 |
| a29-ad6-g138-d38 | 443 → 417 | 4,728.150 | 753.26 | 29 |
| a29-ad6-g139-d33 | 447 → 419 | 4,741.716 | 486.32 | 29 |
| a29-ad6-g154-d27 | 495 → 449 | 4,942.812 | 539.37 | 29 |
| a29-ad6-g181-d21 | 523 → 477 | 5,180.882 | 513.74 | 29 |

The hypothesis failed in this test: every 29-AND candidate is larger and
slower than the equally optimized classic circuit. The 29-bit randomness
advantage remains, so those designs are not dominated when randomness is
included as a third objective. Comparing only against the older, unoptimized
classic mapping would overstate the improvement. A next search must change
the Boolean topology, gadget choice, or another explicitly modeled cost;
register-count minimization in this model has already reached its reported
optimum. Other equally register-optimal schedules can still map differently;
one mapping per topology does not exhaust the area/delay frontier.

Every RTL and mapped candidate passes 4,096 functional transactions. The
implemented HPC2 gadget passes universal functional SAT checks. fullVerif
passes the corresponding independently emitted composition graph, including
sharing preservation, output latency, fresh-random timing, transition-robust,
and cleared-state checks. The latter check sharing validity after pipeline
flush, not reset zeroization. HPC2 security is assumed by the trusted gadget
library. This is not a leakage proof for the mapped netlist or a physical
measurement. Full records and hashes are in
`workspace/aes-256-gcm/reports/masked_sbox_schedule_study.json` and
`runs/aes-masked-schedule-20260918/`.

The technique itself is established prior art:
[COMPRESS](https://eprint.iacr.org/2023/1600) already jointly optimizes masked
pipeline scheduling, gadget choice, and register overhead. Its
[official implementation](https://github.com/cassiersg/compress) was inspected
on 2026-09-18. The local experiment uses a narrower, independently implemented
fixed-HPC2 model with OR-Tools 9.14.6206, not COMPRESS-generated circuitry.
No world-first or globally best masked S-box claim follows.

The promoted command-line tools were replayed on 2026-09-20. The candidate's
solver result, emitted RTL, mapped netlist and statistics reproduce the
prototype exactly: 427 alignment bits, 4,865.406 um², and 416.36 ps. Both sets
of 4,096 functional tests and the independently generated fullVerif composition
pass again. All nine archived schedules regenerate byte-identical RTL; all
nine reject a deliberately invalid input-arrival cycle. The original 152-entry
artifact manifest passes hash verification. The new verifier binds its report
to the measured RTL and schedule hashes, and the measurement entry point
checks the library pin. Historical child records saying composition was
pending are superseded by the completed combined report, not rewritten.
Reproduction commands are in the workspace README; the promoted replay is
retained under `runs/aes-masked-schedule-20260918/promoted-replay-20260920/`.

## First-order HPC2 masked S-box study — 2026-08-31 to 2026-09-01

Research hypothesis: the three fewer nonlinear operations in the new 29-AND
circuits may be valuable after each AND is replaced by a substantially more
expensive masked gadget, even though the unmasked study below shows that the
same circuits are worse conventional standard-cell implementations.

- `make masked-sbox-study` translates the classic and eight new NIST SLPs into
  two-share, first-order HPC2 pipelines. Each AND consumes one fresh random bit.
  The compiler uses HPC2's asymmetric operand timing and swaps commutative AND
  operands when doing so shortens the schedule. All nine generated S-boxes have
  an eight-cycle pipeline latency and accept one input per cycle.
- Every generated RTL and its Nangate45-mapped netlist passed 4,096 streamed
  functional transactions: all 256 byte values under 16 deterministic
  share-mask/fresh-random trials. A separate Yosys SAT proof checks the actual
  two-cycle HPC2 gadget for every possible pair of two-share inputs and fresh
  random bit. The full sweep was repeated and produced identical report SHA-256
  `06ccea74ba01e5c04d1006d27c40edcff4901d32c2bae4cea8df597fddff3b8a`.
- Candidate `a29-ad5-g161-d24` is nondominated in this study. Compared with the
  classic `g113-a32-d27` circuit, it needs 29 rather than 32 fresh random bits
  per S-box (-9.375%) and has a 436.16 ps rather than 453.66 ps mapped
  combinational critical path (-3.858%). Both have eight-cycle latency. Its
  cost is 5,061.182 rather than 4,658.458 um^2 of mapped cell area (+8.645%).
- The closest prior art found materially narrows the result. Hadzic and Bloem,
  ["Efficient and Composable Masked AES S-Box Designs Using Optimized
  Inverters"](https://doi.org/10.46586/tches.v2025.i1.656-683), TCHES 2025(1),
  Table 2, already report a first-order, composable Canright-based S-box using
  29 random bits with four-cycle latency (1,806 GE standalone and 2,948 GE
  including their PRNG model). Therefore 29 random bits is neither new nor a
  global record, and this eight-cycle result is not globally latency-best. The
  paper also discusses the earlier DOM/HPC2 reuse method of Feldtkeller et al.,
  ["Randomness Optimization for Gadget Compositions in Higher-Order
  Masking"](https://doi.org/10.46586/tches.v2022.i4.188-227), which preserves
  restricted rather than full SNI/PINI notions. Any claim below 29 random bits
  for this SLP would require a new reuse construction and a security argument
  matched to the claimed composability notion; it cannot be inferred here.
- This is evidence for a new target-specific Pareto point, not evidence of a
  world-first or a physically leakage-resistant chip. The functional/mapped
  RTL and the independently generated composition model cross-check the AND
  count, latency, and five schedule-driven operand swaps. They are separate
  representations, so the fullVerif result below proves the abstract gadget
  composition and randomness discipline rather than the final mapped netlist.
- Two independent leakage tools were investigated rather than treating the
  functional SAT result as security evidence. CocoAlma revision
  `95c80df5d6d704bf525f47ef6e58e98e27fedf97` reports a cycle-2 dependency on
  `c[0]`, but the same report reproduces on an isolated HPC2 gadget. Exact
  enumeration of all four reconstructed input pairs, all four input-share
  masks, and both fresh-bit values shows that every named stable first-order
  probe has the same distribution for every secret; in particular
  `c[0] = a[0](b[0] xor b[1]) xor r` is uniform because `r` is fresh. SILVER
  revision `0a3c85fc5a60d76eedb84d996473df28fc18ef42` independently passes the
  exact RTL gadget under first-order robust probing, robust NI, robust PINI,
  and output uniformity. This makes the CocoAlma result a documented
  tool-model incompatibility for this HPC2 construction, not a demonstrated
  physical leak. A monolithic SILVER run over the complete S-box exceeded the
  practical BDD state-space budget and was not reported as a pass.
- fullVerif revision `227f31215d8269c3b78bb0ebaebf6a1db6bc198e`, which
  was designed for compositional masked-hardware verification and ships an
  assumed-PINI HPC2 gadget, verifies both the 29-AND candidate and the classic
  32-AND baseline. Transition-robust and cleared-state checks remain enabled.
  For the candidate, fullVerif finds all 29 HPC2 instances valid, traces all 29
  unique fresh bits to cycle zero, preserves all sharings and output latencies,
  and finishes successfully. Repeated candidate and baseline runs are
  bit-for-bit deterministic after normalizing VCD timestamps, temporary source
  paths, and unordered diagnostic presentation. Their report SHA-256 values are
  respectively `bc07448cbf47cfbeb48c2c242efe71beefc3bb7a274ecf79decbda24e5233051`
  and `632a25df432ac05790d076c8b5d68d684798208b80d34f662e5868c51677de0a`.
- The primary masking source is [Hardware Private Circuits: From Trivial
  Composition to Full Verification](https://www.eng.biu.ac.il/leviita2/files/2020/12/Hardware-Private-Circuits-From-Trivial-Composition-to-Full-Verification.pdf).
  Relevant independent verification/tool context includes
  [AGEMA](https://eprint.iacr.org/2021/569.pdf) and [Formal Analysis of
  Masked Hardware Implementations](https://eprint.iacr.org/2017/897.pdf), plus
  the [fullVerif repository](https://github.com/cassiersg/fullverif) and its
  [composition paper](https://eprint.iacr.org/2020/185).
  The primary-source web search found no publication evaluating these exact
  August 2026 29-AND circuits as HPC2-masked hardware. That identifies a
  plausible publication gap but cannot prove nonexistence.
- Machine-readable source hashes, generated RTL and mapped-netlist hashes,
  formal-log identities, cell counts, timing, and verification results are in
  `workspace/aes-256-gcm/reports/masked_sbox_study.json`. The independent
  candidate and baseline composition records are in
  `masked_sbox_fullverif.json` and `masked_sbox_fullverif_classic.json` in the
  same reports directory. Random-generator area/energy, routed timing, power,
  leakage, and full AES-GCM integration are currently unavailable and must not
  be inferred from this S-box experiment.

## Novelty boundary and 29-AND affine search — 2026-09-01

- The proposed first-order HPC2 randomness-reuse direction does not follow
  from Feldtkeller et al.'s 2022 theorem. Their optimized HPC2 distribution
  starts at masking order `t >= 2`; the authors' SAIREDA implementation at
  revision `f29af69b30309db669c70014ed70e4938c51c71e` explicitly rejects its
  optimized distribution pass at order one. Strict reuse yields only R-PINI,
  while the relaxed HPC2+ construction adds output registers to retain the
  stronger composability property. This is a falsified hypothesis, not a
  license to share the 29 first-order gadget random bits.
- Groß et al., ["First-Order Masking with Only Two Random
  Bits"](https://eprint.iacr.org/2018/1007.pdf), already demonstrate a
  first-order AES S-box construction using two total random bits and no online
  randomness in their probing model. The paper also identifies transition and
  horizontal-leakage limitations. Its local PDF SHA-256 is
  `14301ad1a4d00c92cae234066a8d7a6caf829ddc6c79c75cf4915e124493404b`.
  Therefore merely reducing first-order randomness below 29 bits cannot be a
  world-first claim; any advance would need a materially stronger threat model
  and evidence.
- The active clean novelty target is instead the Boolean circuit frontier
  added by NIST in August 2026. Its smallest 29-AND forward AES S-box uses 109
  XOR/XNOR gates. The eight circuits normalize to five distinct nonlinear
  schedules; pairs with different published depth/size points can share the
  same schedule. A correct 29-AND circuit with fewer than 109 affine gates, or
  a strictly better size/depth point, would be an externally checkable result
  but would still require a final public-code and literature signature search.
- A custom constrained linear-resynthesis harness reconstructs each circuit as
  an affine network around 29 fixed ANDs, strips and later restores XNOR
  phases, prevents an AND operand from using its own or any later AND output,
  and exhaustively compares all 256 input values after synthesis. Mockturtle
  revision `0886ebfdd101ce1110daf3d60b96d72edd3143ea` supplies the exact SAT
  backend. Quick 1,000-conflict searches found no 108-gate solution for any of
  the eight circuits; a 100,000-conflict search on the 109-gate schedule also
  found no solution before its limit. These are bounded timeouts, not
  lower-bound proofs. Mockturtle's cancellation-free Paar heuristic produced
  180 gates on the smallest target and is not competitive.
- A second, independent search route uses the authors' implementation of
  ["A Framework for Generating S-Box Circuits with Boyar-Peralta
  Algorithm-Based Heuristics, and Its Applications to AES, SNOW3G, and
  Saturnin"](https://doi.org/10.46586/tches.v2025.i1.586-631), revision
  `11e6b783f179cb9089a08be597d5974e99966e3a`. The paper's method preserves
  nonlinear-gate count and AND depth while resynthesizing the surrounding XOR
  network and optionally applies correctness-preserving nonlinear-gate
  transformations. The retrieved paper SHA-256 is
  `561bc90bff50b255bb6d2f033a92149a7b3cadb15a1875e3a7e4e759977deca8`.
  A converter maps the NIST bit convention into the framework and its output
  passed all 256 AES S-box inputs before the long randomized searches began.
  No improvement is recorded until a generated circuit completes and passes
  independent equivalence and gate-count checks.

## Exact affine-completion search — 2026-09-01

- The public target remains a 29-AND AES S-box with at most 108 affine gates,
  or 137 total gates. Exact web signature searches for `137 gates`, `108 XOR`
  with `29 AND`, and the NIST-style `g137` filename found no matching public
  circuit. This makes 137 a clean candidate threshold, but search-engine
  absence is not a proof that no unpublished or differently described result
  exists.
- A live recheck on 2026-09-16 found the NIST circuit list unchanged at 29
  AND plus 109 XOR/XNOR gates (138 total) for its smallest 29-AND forward AES
  S-box. Refreshed exact-signature searches again found no public 137-gate or
  29-AND/108-affine circuit. This only refreshes the public candidate frontier;
  it does not convert search absence into a novelty proof.
- Maximal affine-region extraction reduces the 138-gate circuit's only hard
  local question to whether eight required values can be completed from 42
  already available values in 15 XORs instead of the published 16. Eleven of
  the fourteen regions are trivially optimal; separate exact runs also proved
  the small 6-to-5 case and the bounded final-suffix reductions UNSAT. The
  remaining 16-to-15 region is the only schedule-local route to 137 gates.
- The hard problem was initially encoded in a 37-bit ambient basis, but its 42
  available values have rank only 17. A lossless Gaussian coordinate pass now
  compresses every source and target into that 17-dimensional span before SAT
  construction. The map is injective on the span and therefore preserves XOR,
  equality, source availability, and target realization. Positive and negative
  controls pass after compression: a one-gate toy is SAT and its zero-gate
  form UNSAT; a published four-gate completion is SAT and its three-gate form
  UNSAT; and the published hard block is reconstructed in 16 gates.
- CryptoMiniSat 5.14.7 supplies an independent native-XOR encoding alongside
  Mockturtle revision `0886ebfdd101ce1110daf3d60b96d72edd3143ea` and its
  [SAT-based optimum linear synthesis](https://mockturtle.readthedocs.io/en/latest/algorithms/linear_resynthesis.html).
  On the 12 independent incoming values used by the published completion, the
  native solver proved two complete 15-gate schedule classes UNSAT: removing
  an internal before the first required target, and removing one of the three
  middle internals. These results quantify over every operand choice and every
  internal affine value under the stated source set and target schedule. They
  were independently reproduced by the Glucose and Maple backends,
  respectively. They are not a lower bound for arbitrary schedules or for all
  42 free inputs.
- A rank-compressed constructive search independently reproduces the known
  16-gate block. It found no 15-gate completion in 476 full-source randomized
  trials, the earlier 2,000 sparse trials, all 435 pairs, or all 4,060 triples
  of extra incoming wires added to the published 12-wire support. These are
  negative heuristic observations, not proofs. The remaining late-deletion
  exact schedule remained unresolved after at least 30 minutes in
  CryptoMiniSat, 19 minutes in BMCG, and 16 minutes in Maple; all three were
  externally stopped and are recorded as unknown, not UNSAT.
- The late schedule is now decomposed into finite, independently replayable
  operand partitions. All 325 possible final-step operand pairs were tested at
  100,000 conflicts: 270 are exact UNSAT and 55 timed out, with no SAT branch.
  The four hardest final pairs were each split over all 171 operand pairs for
  internal step 7. At 10,000 conflicts those 684 branches yielded 516 UNSAT
  and 168 timeouts; deepening precisely those timeouts to 100,000 conflicts
  yielded another 95 UNSAT and 73 timeouts. Every one of those 73 parents was
  then partitioned over the definition of its latest referenced internal
  value. Across 10,965 child branches, staged limits of 1,000, 10,000, and
  100,000 conflicts reduced the open set from 3,554 to 1,735 to three. One
  final recursive partition for each of those three parents closed all seven
  residual leaves UNSAT. Thus the four hard final pairs are now fully UNSAT
  for the published 12-source support and fixed late-deletion schedule. Three
  additional final pairs, `5,19`, `6,19`, and `8,19`, were independently
  closed the same way. The `8,19` class alone had 171
  step-7 branches produced 141 UNSAT and 30 timeouts at 10,000 conflicts; the
  timeout replay produced 14 UNSAT and 16 timeouts at 100,000 conflicts. Those
  16 parents expanded to 2,431 child branches, which staged replay reduced
  from 686 to 306 to zero timeouts; the last 306 leaves were all UNSAT. Other
  top-level final pairs remain under durable replay, so this is not yet a
  fixed-schedule lower bound. Every retained branch status and the exact scope
  are recorded in `workspace/aes-256-gcm/reports/xor_completion_branch_study.json`;
  the replay harness records per-branch exit status and elapsed time and now
  checkpoints atomically after every completed branch.
- The replay harness now supports `--resume-from` for interrupted partial
  reports. It preserves prior branch records, classifies only missing operand
  pairs, and marks completion only when the full theoretical pair set is
  present. Recursive partitioning also handles a timeout whose pinned internal
  uses only the original source values by splitting the preceding step; this
  avoids silently discarding source-only branches.
- Commands, hashes, source scopes, controls, null timing provenance, and the
  precise claim boundary are retained in
  `workspace/aes-256-gcm/reports/xor_completion_study.json`. No 137-gate
  candidate and no world-first result is claimed.
- An unrestricted follow-up over all 42 incoming wires (rather than the
  published 12-source support) requested 15 affine steps with a 10,000,000
  conflict budget and returned `timeout`. It found no candidate but is not an
  UNSAT proof; the exact scope, command, hashes, and null elapsed-time
  provenance are retained in
  `workspace/aes-256-gcm/reports/xor_completion_all_sources_search.json`.

## Current 29-AND S-box ASIC study — 2026-08-31

Research hypothesis: the eight forward AES S-box circuits that NIST added in
August 2026, each using 29 AND gates, might improve the unmasked standard-cell
area or critical path of this AES-256-GCM accelerator compared with the classic
113-gate, 32-AND NIST circuit. This hypothesis was falsified on the pinned
Nangate45 target.

- `make sbox-circuit-study` retrieves each circuit from NIST revision
  `4e23832e62f490aeffd8770b1285d99056b5f8bf`, refuses a source whose SHA-256
  differs from its manifest, translates the SLP to standalone Verilog,
  exhaustively compares all 256 inputs with the independent AES reference, and
  maps it with the same Yosys/ABC library, input driver, and output load.
- All nine circuits pass all 256 functional values. The classic circuit maps
  to 200.830 um^2 and 1,019.48 ps. Every 29-AND circuit is dominated by it in
  both dimensions: the smallest new result is 274.246 um^2 (+36.6%), while the
  fastest is 1,070.65 ps (+5.0%). The best new area-delay product is 70.5%
  worse than the classic result.
- This does not contradict the new circuits' multiplicative-complexity result.
  In an ordinary unmasked standard-cell flow, reducing three AND gates does
  not compensate for the added affine gates and, depending on the circuit,
  added logic depth. The result suggests that their most promising chip-design
  use is masked hardware, where a nonlinear gadget can cost registers and fresh
  randomness rather than one ordinary AND cell.
- The primary sources are NIST's [current circuit
  list](https://csrc.nist.gov/projects/circuit-complexity/list-of-circuits),
  the pinned [NIST Circuits repository](https://github.com/usnistgov/Circuits),
  and the author's [explicit 29-AND construction](https://umizame.github.io/S-box_29-AND/).
  The web and primary-paper search found no published hardware evaluation of
  these exact August 2026 circuits and no masked realization of them. That is
  evidence of a research gap, not proof of absence or a novelty claim.
- Machine-readable results, cell-type counts, hashes, and constraint identity
  are retained in `workspace/aes-256-gcm/reports/sbox_circuit_study.json`.
  These are pre-layout unmasked results; routed timing, power, leakage, and
  first-order masking security remain unmeasured.

## Boolean S-box and technology-aware architecture sweep — 2026-08-31

- The clean retained evaluator run
  `aes-gcm-2ba718c-nangate45-breakthrough` passes at candidate commit
  `2ba718c926fb170c3223086c0cfa8b7f597c38ac`. It records separate precheck,
  build, simulation, and synthesis durations and hashes; the fresh synthesis
  phase took 1,541.114 seconds. All phase exit codes are zero.

- The original 2,048-bit lookup formulation was replaced by the NIST Circuit
  Complexity team's pinned forward `g113-a32-d27-ad6` and inverse
  `g121-a34-d21-ad4` AES S-box straight-line programs. The generator translates
  only `AND`, `XOR`, and `XNOR` gates and checks the declared gate counts. A new
  RTL harness exhaustively compares all 256 inputs in both directions before
  the existing key-schedule, primitive, and full-GCM tests run.
- Source revision `4e23832e62f490aeffd8770b1285d99056b5f8bf` and normalized file hashes
  are recorded in `workspace/aes-256-gcm/third_party/nist-circuits/SOURCE.md`.
  Primary sources are the [NIST circuit list](https://csrc.nist.gov/projects/circuit-complexity/list-of-circuits)
  and [NIST Circuits repository](https://github.com/usnistgov/Circuits).
- A Canright-style composite-field S-box was synthesized as a retained design
  exploration, motivated by [OpenTitan's documented ASIC-oriented Canright
  choice](https://opensecura.googlesource.com/3p/lowrisc/opentitan/+/refs/heads/master/hw/ip/aes/README.md),
  but the pinned NIST SLP produced the smaller complete candidates in this
  flow. The selected SLP lowered generic cells from 36,843 to about 24,700 for
  the folded baseline and from 73,782 to about 42,700 for the original
  two-round/eight-bit point. Those are same-flow comparisons, not universal
  circuit-minimality claims.
- GHASH was parameterized at 8, 16, 32, and 64 bits per cycle and crossed with
  one- and two-round AES datapaths. This exposes a crucial target-aware result:
  two-round AES reduces cycles but approximately doubles the mapped critical
  combinational path, so its real-time estimate is dominated by one-round AES
  points under the selected library and workload.
- Named mapping uses Yosys `dfflibmap` and ABC against the Nangate Open Cell
  Library typical corner (45 nm, 1.1 V, 25 C), pinned from OpenROAD Flow
  Scripts revision `be0dca0b1fd41df54792b3012350cd52bccd99bb`. The exact library
  SHA-256 and license provenance are in
  `workspace/aes-256-gcm/third_party/nangate45/SOURCE.md`. The flow applies a
  `BUF_X1` input driver and 5 fF output load, checks for unmapped internal
  cells, and retains statistics, logs, and mapped netlists.
- The mapped-netlist gate uses a functional model regenerated from that same
  Liberty file and reruns all 1,038 GCM operations. This verifies synthesis
  semantics for the selected frontier candidate; it is not formal equivalence
  or routed silicon validation.

## Simulation-complete outcome — 2026-08-30

- Candidate commit `9afd0b63e4d85b35a48013ef1bc97414e3e9852a` implements and measures two
  synthesizable organizations under the frozen profile. The evidence-backed
  comparison is recorded in `RESULTS.md` and the machine-readable workspace
  reports.
- Verilator 5.050 is the cycle/lint engine. Yosys 0.68+post
  (`c12172fbae8af5e20f6fb52e3d4e92d56ed587b6`) is the generic synthesis
  engine. The generic-cell comparison is meaningful only inside this identical
  flow and is not an FPGA LUT or ASIC-area claim.
- The host has no configured FPGA/ASIC target, physical board, timing library,
  power model, or leakage/fault instrumentation. The experiment therefore ends
  at the specified simulation-complete boundary; physical metrics remain
  unavailable rather than estimated.

## Profile-freeze verification — 2026-08-30

- The live [FIPS 197 CSRC page](https://csrc.nist.gov/pubs/fips/197/final)
  still identifies FIPS 197-upd1, updated 2023-05-09, as final and states that
  the update made no technical change to AES.
- The live [SP 800-38D CSRC page](https://csrc.nist.gov/pubs/sp/800/38/d/final)
  still identifies the November 2007 publication as final and carries the
  2024-03-06 planning note that NIST decided to revise it. No final successor
  was present on the canonical page, so profile `aes-256-gcm-64-v1` pins the
  2007 text and must be re-reviewed if NIST publishes a replacement.
- The [CAVP block-mode page](https://csrc.nist.gov/Projects/Cryptographic-Algorithm-Validation-Program/CAVP-TESTING-BLOCK-CIPHER-MODES)
  was retrieved 2026-08-30. It describes its GCM vectors as informal
  correctness checks that do not replace validation.
- `KAT_AES.zip`, retrieved from NIST on 2026-08-30, has SHA-256
  `a203b16c9246b2ebae31dee5de21a606be80cf78ceabaca37150236fa098eb60`.
- `gcmtestvectors.zip`, retrieved from NIST on 2026-08-30, has SHA-256
  `f9fc479e134cde2980b3bb7cddbcb567b2cd96fd753835243ed067699f26a023`.
- The normalized committed subset is reproduced only after both archive hashes
  match. It includes AES-256 primitive cases plus GCM encryption, successful
  decryption, and failed-authentication cases within the frozen profile.

## Normative sources

### AES

- [NIST FIPS 197 — Advanced Encryption Standard (AES)](https://csrc.nist.gov/pubs/fips/197/final)
  defines AES-128, AES-192, and AES-256 over 128-bit blocks. This experiment
  selects the AES-256 key schedule and round function; the source, rather than
  an implementation convention, is the authority for byte ordering and the
  state/key-schedule transformations.

### GCM

- [NIST SP 800-38D — Recommendation for Block Cipher Modes of Operation:
  Galois/Counter Mode (GCM) and GMAC](https://csrc.nist.gov/pubs/sp/800/38/d/final)
  defines the authenticated-encryption mode, GHASH, tag generation, IV
  processing, and the authentication failure behavior that the profile must
  make explicit. NIST currently marks the publication for revision, so the
  manifest pins the source used for each run and must be revisited if a
  successor becomes applicable.

### Validation vectors and vocabulary

- [NIST Automated Cryptographic Validation Protocol (ACVP)](https://pages.nist.gov/ACVP/)
  is the reference for machine-readable cryptographic test-vector and
  validation concepts. ACVP compatibility is a future interoperability goal,
  not a claim that this repository is an accredited validation laboratory.

## Architecture context

### Current-ciphertext decrypt overlap and port review — 2026-09-18

`ARCH=11` and `ARCH=12` launch GHASH of input ciphertext alongside its AES
counter encryption. `ARCH=13` and `ARCH=14` combine that decrypt schedule with
the earlier encrypt overlap; the even-numbered variants use Karatsuba GHASH.
All four preliminary RTL and mapped-netlist runs passed the 1,038-operation
transfer scoreboard and repeatable cycle traces. The complete preliminary
numbers and source hashes are in
`workspace/aes-256-gcm/reports/dual_overlap_pre_hardening.json`.

These measurements exposed two reasons to withhold an implementation claim.
First, rebuilding the baseline from the same modified source produced
77,866.446 um² and 2,772.31 ps, different from the older 75,700.408 um² and
2,726.41 ps baseline. Direct comparisons must use the same source snapshot.
Second, independent source review found that the raw output pins revealed
buffered plaintext during invalid cycles, and that decryption returned the
computed tag even after rejection. These bugs predate the new overlap path;
the previous harness checked transfers and encryption tags only. They
invalidate the broad external-port confidentiality claim in prior revisions.
The wrapper now drives zero on invalid data cycles and suppresses decryption
result tags. New raw-port regressions require rebuilding and remeasuring the
candidate; preliminary results are retained as superseded evidence.

The hardened candidate `25da99238a162c2a4c55e204f315054c151191b4` subsequently
passed the complete baseline `make check` and the retained targeted evaluator
`aes-gcm-dual-hardened-20260918` from a clean tree with unchanged source hashes.
All five selected configurations (baseline ARCH7 and ARCH11–14) passed the
1,038-operation RTL corpus twice with byte-identical logs, generic synthesis,
Nangate45 mapping, and byte-identical mapped-netlist corpus output. The new
raw-port checks run in both RTL and mapped simulations.

For the same 96-bit-IV/0-AAD/64-byte warm-key workload, ARCH11 reduces the
estimated decrypt latency by 5.48% for 0.82% more area; encryption is 0.77%
slower. ARCH14 reduces estimated encrypt/decrypt latency by 5.46%/6.60% at
14.75% more area. ARCH12 and ARCH13 are dominated by ARCH11 in this five-point
area/encrypt-latency/decrypt-latency comparison. Repeated ARCH13 mapping has
identical netlist and statistic hashes: its 2,939.95 ps path erases the cycle
savings, reversing the preliminary ranking. These are pre-layout estimates,
not routed clock or silicon measurements. Exact measurements, deltas and
reproduction command are in
`workspace/aes-256-gcm/reports/dual_overlap_hardened.json`.

The scheduling principle is established prior art. Yang, Mishra and Karri,
[A High Speed Architecture for GCM](https://eprint.iacr.org/2005/146.pdf)
(2005), section 3.3 and Figure 4(b), describe overlapping decrypt hashing with
keystream generation. NIST also links that paper in its
[2005 mode-selection comments](https://csrc.nist.gov/projects/block-cipher-techniques/bcm/public-comments-modes-development).
Eric Biggers' original
[Linux AES-GCM implementation](https://github.com/torvalds/linux/blob/master/arch/x86/crypto/aes-gcm-aesni-x86_64.S)
explains the same dependency distinction in `_aes_gcm_update`: ciphertext is
immediately available during decryption; encryption hashes the previous batch
while encrypting the next. Sources were checked on 2026-09-18. These are
prior-art anchors, not evidence of comparable area or latency across targets.
No novelty claim follows from the local schedule or the security fixes.

### Constructive GHASH branch — Karatsuba exploration (2026-09-17)

To complement the exact affine-search frontier, the workspace now contains an
`ARCH=8` two-stage 64-bit Karatsuba carry-less multiplier for GHASH
(`workspace/aes-256-gcm/rtl/ghash_karatsuba.sv`).  It was checked against all
1,038 existing GCM RTL operations, including 32 stalled replays; the retained
log is `workspace/aes-256-gcm/reports/karatsuba_rtl.log`.  The representative
96-bit-IV/0-AAD/64-byte encryption case measured 252 warm cycles.

The same frozen Yosys/ABC flow measured 86,537.248 um² total Nangate45 mapped
cell area, 2,700.92 ps critical combinational delay, and 370.244213 MHz
pre-layout Fmax.  The existing balanced-xwide 1r/64b point is 75,700.408 um²,
2,726.41 ps, and 257 warm cycles.  This makes the branch a local Pareto point
in the measured area/latency plane (about 680.6 ns versus 700.8 ns estimated
pre-layout latency), but not a world-first claim.  The full machine-readable
record is `workspace/aes-256-gcm/reports/karatsuba_exploration.json`.

This direction is also not claimed as unprecedented.  A current prior-art
anchor is Chuang et al., “High-Performance AES-GCM Hardware via Circuit and
Architecture Co-Design of AES and GHASH,” ISCAS 2026,
[published record](https://researchoutput.ncku.edu.tw/en/publications/high-performance-aes-gcm-hardware-via-circuit-and-architecture-co/),
which reports a redundant-basis S-box and two-stage Overlap-Free Karatsuba
GHASH.  The local design is a separately measured, simpler RTL point and does
not reproduce or supersede that work.

### AES/GHASH data-overlap branches — 2026-09-17

The next constructive branch attacks a different bottleneck: the original
state machine waited for a payload GHASH multiply to finish before launching
the next counter/AES block.  `ARCH=9` keeps the same one-round AES and 64-bit
GHASH datapaths but, after the first payload block, launches those two
independent operations in parallel.  `ARCH=10` combines the schedule with the
two-stage Karatsuba multiplier from the preceding exploration.  Both variants
pass the complete 1,038-operation corpus, 32 deterministic stalled replays,
and 38 fixed-cycle comparisons; the retained logs are
`workspace/aes-256-gcm/reports/overlap_rtl.log` and
`workspace/aes-256-gcm/reports/overlap_karatsuba_rtl.log`.

On the representative 96-bit-IV/0-AAD/64-byte encryption workload, `ARCH=9`
measures 245 warm cycles versus 257 for the frozen `balanced-xwide-1r64b`
baseline.  The pinned Nangate45 flow maps it to 78,137.766 um² with a 2,767.82
ps critical path, versus 75,700.408 um² and 2,726.41 ps for the baseline.  The
result is a measured local Pareto point: 4.7% fewer cycles and 3.2% lower
estimated pre-layout latency at 3.2% more area.  `ARCH=10` reaches 243 warm
cycles and an estimated 668.75 ns pre-layout latency, but costs 88,751.698 um²;
it is a latency-oriented point rather than a uniformly better design.  Exact
hashes, synthesis reports, commands, and deltas are retained in
`workspace/aes-256-gcm/reports/overlap_exploration.json`.

The idea is not presented as a world first.  IBM's ISCAS 2006 study already
reported sequential GCM organizations with full-pipelined AES and a block per
clock ([primary record](https://research.ibm.com/publications/high-speed-hardware-architectures-for-authenticated-encryption-mode-gcm)).
The 2026 ISCAS paper cited above also combines two AES modules with a pipelined
Karatsuba GHASH.  The contribution here is narrower: a reproducible overlap
schedule for this small, one-round AES-256-GCM core, measured against its own
technology-aware Pareto sweep.

- [RISC-V Unprivileged ISA — Scalar Cryptography](https://docs.riscv.org/reference/isa/unpriv/scalar-crypto.html)
  is the primary source to consult if the AES implementation is exposed as
  scalar ISA instructions. Any instruction proposal or custom extension must
  separately record its encoding, architectural state, compiler/toolchain
  support, and fallback behavior.
- [RISC-V Unprivileged ISA — Vector Cryptography](https://docs.riscv.org/reference/isa/unpriv/vector-crypto)
  is the primary source to consult if the design uses vector operations. A
  vector design must state its vector length, element grouping, tail/mask
  behavior, and software ABI rather than treating “vector AES” as a single
  comparable datapoint.

## Research rules for this experiment

- Pin the URL, retrieval date, relevant section/table, and any local copy or
  checksum used to generate vectors.
- Separate normative requirements from implementation choices and hypotheses.
- Do not infer security, throughput, area, or energy from an architecture
  diagram. Attach each reported number to a simulator, synthesis, measurement
  artifact, or explicitly labeled estimate.
- Keep rejected architecture branches and failing vectors in the run record;
  they are part of the experiment history.
