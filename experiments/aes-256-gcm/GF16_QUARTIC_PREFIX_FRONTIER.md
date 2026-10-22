# Nonquintic scalar-prefix frontiers

Date: 2026-10-22. This is an exact scalar-prefix inventory and search
normalization, not a complete field multiplier or an exclusion of all
eight-AND field circuits.

The [machine-readable frontier study](../../workspace/aes-256-gcm/reports/sbox_norm_q5_quartic_first8_study.json)
retains complete per-representative counts, exact orbit multiplicities,
source hashes and raw-archive identities.

The [quintic result](GF16_QUINTIC_PREFIX_BOUND.md) leaves actual gate
degrees at most four in the five-gate, eight-input, rank-eight quadratic
scalar problem. The original inventory treats first-four raw rank eight.
A later section also treats the raw-rank-six / first-three-raw-rank-six
sub-branch; other raw-rank-six/seven branches remain separate questions.

## Exact pair-swap normalization

Fix the eight independent raw factor forms of the first four gates as
the eight coordinate units. A gate's two earlier-wire dependency masks
are `a_i,b_i`. Swapping its two fresh coordinates and commuting its
AND factors swaps these masks. It leaves all later dependency labels
unchanged, because each earlier actual gate function is transported
jointly by the same input permutation.

Sort the two masks in each ordered pair. This uses no gate reordering,
scalar-function replacement, nonlinear substitution or dropped output
shift. It transports every available wire space and any entire field
target jointly. The representative need not be the numerically smallest
integer topology code.

There are `3*10*36=1,080` pair-swap orbits among the 4,096 ordinary
prefixes. Exactly 1,576 prefixes have fourth-gate degree at most four,
forming 494 orbits. An independent exhaustive quadratic-decoder census
finds a rank-eight scalar already available by four only in code zero,
the four disjoint products. Removing it leaves 1,575 **proper-first-
scalar-at-five** prefixes and 493 representatives.

The [portable classifier](../../workspace/aes-256-gcm/tools/classify_norm_q5_first8_quartic.py)
checks all 16,384 gate-polynomial transports and 4,194,304 gate truth
rows, not just degree invariance. It also checks generic five- and
eight-gate DAGs with operand constants under all sixteen coordinate
pair permutations. All 4,096 topology IDs, maps and orbit members are
retained in the local classification archive.

## Why code zero needs its own field argument

An arbitrary rank-eight scalar in the available space need not be an
element of the designated four-dimensional field-output target `T`.
Therefore excluding code zero from a **scalar** census is not, by
itself, a complete field-search reduction.

A separate argument excludes any eight-AND field circuit whose first
four gate truths are all quadratic. It invokes the already reviewed
[Q-by-four exclusion](GF16_EARLY_SCALAR_BOUND.md),
span-preserving quadratic-gate flattening and
[the checked quadratic nine-AND bound](GF16_QUADRATIC_BOUND.md):

1. If a field-target direction is available by four, the Q-by-four
   result applies. Otherwise none is available there.
2. At least one target direction must be available by gate five, since
   the final three gates supply at most three. If gate five is the first
   nonquadratic wire, it cannot introduce a quadratic target direction
   against a purely quadratic prefix, a contradiction.
3. Thus the first five wires are quadratic. They cannot supply two
   independent target directions: after cost-preserving flattening,
   each of the three nonzero decoder words needs weight at least four,
   giving total weight at least twelve, but five columns contribute at
   most ten. If gate six is the first nonquadratic wire, the target
   dimension cannot rise there; yet the final two gates require at
   least two target directions by six. Contradiction.
4. If all first six wires are quadratic, their target intersection has
   dimension exactly two. It is at least two by the remaining gate
   budget, and cannot be three: seven nonzero words of weight at least
   four need 28 ones, while six columns contribute at most 24. The final
   two gates are rank-tight and must lie inside the quadratic prefix
   plus target space, so both are quadratic too. An all-quadratic
   eight-gate field circuit contradicts the checked nine-AND bound.

This supplies the additional field-level justification for omitting the
all-quadratic code-zero prefix. It is not inferred from the classifier.

## All fifth-gate scalar extensions

Let `W4` be the raw-affine plus first-four wire space and `K4` its
quadratic polar subspace. The complete one-product scan finds every
quadratic polar coset modulo `K4` admitting a rank-eight scalar `Q`.
For an actual fifth product `g5`, its decoder satisfies `Q=g5+w4`
modulo affine terms. Consequently

```text
W5 = W4 + span(Q).
```

A polar coset determines this unmarked fifth-prefix space exactly.
But `Q` and `Q+k`, for `k` in `K4`, need not be interchangeable as a
distinguished field-target direction. **Every rank-eight choice within
each coset is retained**, with actual product operands and its decoder.
Selecting only one would make a later target-continuation test incomplete.

All 493 representatives are scanned. Exactly 130 admit a fifth scalar;
there are 203,728 per-prefix admitted polar cosets and 207,184 marked
rank-eight scalar choices. These counts are not a claim that all spaces
are inequivalent under arbitrary input changes.

The independent symbolic/joint-row-equation replay repeats all 493
complete searches: 2,018,835 nonzero-left examinations, 21,031,179
eligible unordered pairs and 5,486,888 quadratic polar cosets. It agrees
with every production count and histogram. It separately checks every
retained product, every marked scalar and every possible `K4` offset.
Distinct valid witnessed cosets exhaust the independently established
rank-eight coset count. The positive quartic control is admitted.

Production uses truth-table AND, a Mobius transform and high-column
elimination. Replay uses symbolic Boolean monomial unions and joint
row equations for the right factor and old-gate cancellation. These
are independent algorithms within the same research team, not external
peer review, a checked UNSAT certificate or formal verification.

## The first useful suffix: a necessary test

The following is a reduction of the continuation question, not a statement
that the complete scan has finished. Let `A` contain all raw affine
functions, and let `K_i` denote the quadratic polar subspace of `W_i`.
For each retained state, `W5=W4+<Q>` and `K5=K4+<Q>`. No nonzero field
target lies in `W4`: every such target has polar rank eight, whereas this
inventory's `K4` contains no rank-eight form.
Target dimensions and intersections here are taken modulo `A`, so arbitrary
free affine output corrections are included throughout.

If a transported full field target `T` contains the distinguished mark
`Q`, then `W5 intersect T=<Q>`. Indeed, the map from that intersection
to the one-dimensional quotient `W5/W4` is injective. Thus three target
dimensions remain, with only three ANDs left in a hypothetical eight-gate
circuit. This is rank-tight: the final space must be `W5+T`, and each
remaining gate must increase the available target dimension. In particular,
the sixth actual product must satisfy

```text
g6 = u*v,  u,v in W5;
t = g6+w5 in T outside W5,  w5 in W5;
rank(t) = rank(t+Q) = 8.
```

Constants in the factors add only an old-space correction. With constants
removed there are 8,191 nonzero left forms in the thirteen-dimensional
raw-plus-five-wire basis. For each, solve all right-factor coefficients
jointly with high-part cancellation by old wires. Once a quadratic residue
is found, test **every** quadratic old-space offset in `K5`. Deduplication
is safe only modulo the whole `K5`, and the zero quotient class cannot add
a target direction. Preserve every marked `Q` independently; it is not
safe to select just one mark from an unmarked state.

A negative requires a complete scan of all left forms and their right
kernels. A positive must retain actual factor masks, the old-wire decoder
and an all-256-input replay. It admits further investigation only: a bent
pair need not embed in the designated field target, and it is not a full
four-output multiplier. The producer and symbolic checker use different
quotient/row-equation methods within one team, not external peer review.

## A stronger field-pair filter (not yet a frontier result)

Write the polar form as `x^T B_f y`, using symmetric zero-diagonal
matrices on column coordinate vectors. For nonsingular `B_Q`, set
`J=B_Q^-1 B_t`. A common raw affine input substitution `x=S*y+a`
changes the matrices by congruence and `J` by similarity:
`J_new=S^-1 J S`. Affine output terms do not affect these matrices.

Every genuine field-output functional has the form
`f_c(a,b)=Tr(c*a*b)` for `c` in `GF(16)`. For independent `Q=f_c`
and `t=f_d`, the operator `J` is multiplication by `d/c` on both
field coordinates. Its minimal polynomial is irreducible of degree two
or four. Therefore at least one of the following identities is necessary:

```text
J^2+J+I=0
J^4+J+I=0
J^4+J^3+I=0
J^4+J^3+J^2+J+I=0.
```

This is strictly stronger than the three rank-eight tests. The retained
counterexample uses `Q=[[0,I4],[I4,0]]` and
`J=diag(C,C^T)`, where `C` is the companion matrix of
`X^4+X^2+1=(X^2+X+1)^2`. Then `t=Q*J` is alternating and
`Q,t,t+Q` are nonsingular, but no listed irreducible identity holds.
Testing only the determinant or Pfaffian pencil would miss this
nonsemisimple case; the operator identity matters.

If an accepted pair has an irreducible degree-four operator, any full
field target through it has the unique polar space
`span(B_Q, B_Q*J, B_Q*J^2, B_Q*J^3)`: its normalized coefficient
operators form a four-dimensional field containing `J`, hence equal
`F2[J]`. This is conditional uniqueness, not a constructed gate
continuation or a sufficiency claim. Degree-two operators leave extension
choices open.

The [standalone operator controls](../../workspace/aes-256-gcm/tools/verify_field_pair_operator.py)
check all 210 ordered genuine coefficient pairs, all 180 degree-four target
regenerations, and 128 common affine/GL8 transformations with exact truth
replays. These finite controls support the stated conventions, not a
frontier-wide exclusion or a novelty claim.

## The raw-rank-six / first-three-rank-six sub-branch

Here `r_i` is the raw operand-covector rank after gate `i` in the reviewed
normal form, not the dimension of the complete available wire space. Assume
a hypothetical full eight-AND multiplier has `r4=6`. After the earlier
Q-by-four exclusion, a first field-target direction `Q` is available at
gate five. The old four wires depend on six coordinates `z`, and the last
two raw directions are fresh. Write the actual fifth product as
`g5=(x+A(z))*(y+B(z))`. Its quadratic decoder forces `A,B` to be affine
by the fresh-variable coefficients. A common invertible raw affine shear
makes the **same actual fifth product** `x*y`, leaving every old wire
unchanged. Consequently, modulo free affine terms,

```text
Q = R6(z)+x*y,  rank(R6)=6,  R6 in W4;
W5 = W4 + <x*y>.
```

The first-three raw rank is four, five or six. This section covers **only
`r3=6`**. Its first six raw factors normalize to the six coordinate units,
with all earlier dependencies free: exactly 64 ordered three-gate
topologies. Scalar-function equivalence is not used to replace old wires.
Operand constants are removed only through the reviewed
[unit-triangular, full-span-preserving rewrites](GF16_FIVE_GATE_INPUT_NORMAL_FORM.md);
this is not a restriction to originally constant-free circuits. Original
wire functions remain recoverable by free XORs at the same AND budget.

Only code zero, the three disjoint products, has a rank-six scalar in
`W3`. That fact alone does not justify dropping all its scalar extensions.
If the selected `R6` is old, commute the fresh product `x*y` before the
old fourth gate: a genuine target is then available by four, contradicting
the Q-by-four result. If `R6` is new, code zero's purely quadratic `W3`
forces actual `g4` quadratic too. The previously reviewed
all-quadratic-first-four field argument then applies. This is a
**field-specific** exclusion; code-zero scalar extensions still exist.

For each other topology, a new scalar decoder gives `W4=W3+<R6>`,
preserving the old actual fourth product through its stored decoder.
Every product coset and every rank-six scalar mark is retained, then
lifted with the same fresh product. These are all possible rank-eight
marks in the lift: an old six-input form cannot have rank eight, and
`rank(R6+x*y)=rank(R6)+2`.

Two complete methods agree on all 64 scalar scans: 32,704 left forms,
237,400 eligible unordered pairs, 44,560 quadratic cosets, 6,634 admitted
rank-six cosets and 7,498 scalar marks. Every retained scalar/product
decoder is replayed (479,872 truth rows), including the genuine quartic
code-nine example. Exact full-wire RREF comparison leaves **6,120**
distinct fixed-coordinate noncode-zero lifted spaces with **6,552**
marked scalars; this is not an arbitrary-GL equivalence quotient.

Both complete first-suffix scans are negative on every lifted state and
mark. Every-case comparison agrees on all 50,128,920 left examinations,
289,072,800 eligible pairs, 63,629,712 nonzero quadratic polar cosets,
kernel histograms, old quadratic spaces and mark memberships. Both actual
commands exit zero. The producer includes one additional zero coset per
state; the independent scanner deliberately omits it.

The preceding necessary-condition proof therefore excludes the
**`r4=6, r3=6` full-eight-gate field branch**, conditional on the named
reviewed Q-by-four/all-quadratic-field reductions. Gate six itself need
not be quadratic: the scans allow its high part to cancel against the
actual old wire space. No theorem about every optimal output-pair circuit
being quadratic is assumed. All input normalizations transport the entire
unknown target jointly, rather than fixing the old field tables.

The [local follow-up study](../../workspace/aes-256-gcm/reports/sbox_norm_frontier_pair_followup.json)
retains counts, exact source/run identities and the independent comparison.
The `r3=4/5` and raw-rank-seven branches remain open. The much larger
raw-rank-eight producer campaign is complete but its full independent
replay is still pending at this checkpoint. No global bound, smaller AES
circuit, physical result or established novelty follows.

## What remains

No three-gate field continuation is tested by the original inventory. A next
necessary-condition scan must preserve every marked `Q` and seek a new
quadratic direction `t` with
`rank(Q)=rank(t)=rank(t+Q)=8`. Finding such a pair would only admit a
prefix for further investigation, not construct the four field outputs.
A final positive circuit must still compute the exact full GF(16)
target under one common input substitution on all 256 assignments.

Exact fixed-coordinate function-space deduplication is now completed
using full reduced row-echelon bases: it finds **no duplicates** among
the 203,728 `W5` states, preserving all 207,184 marks. Each state has
at most two admitted marked scalars in this inventory. This is not a
quotient by arbitrary `GL(8,2)` or by field-target equivalence.
The `r4=6,r3=6` sub-branch is excluded as above. Other raw-rank-six/seven
prefixes, the larger independent replay, complete continuations and the
full eight-AND multiplier question remain open.

## Reproduction

From the repository root, use fresh output paths:

```sh
mkdir -p runs/quartic-first8-replay
python3 -B workspace/aes-256-gcm/tools/classify_norm_q5_first8_quartic.py --output runs/quartic-first8-replay/classification.json
clang++ -std=c++20 -O3 -Wall -Wextra workspace/aes-256-gcm/tools/enumerate_norm_q5_first8_extensions.cpp -o runs/quartic-first8-replay/enumerate
runs/quartic-first8-replay/enumerate runs/quartic-first8-replay/full.json 0 493
python3 -B workspace/aes-256-gcm/tools/verify_norm_q5_first8_extensions.py --input runs/quartic-first8-replay/full.json --out runs/quartic-first8-replay/symbolic.json --jobs 4
```

Do not disable assertions. The raw inventory is generated locally and
ignored by Git; the retained study identifies its hashes and counts.
No physical result, AES improvement or world-first claim follows.

To reproduce the smaller raw-rank-six branch with fresh output paths:

```sh
mkdir -p runs/rank6-lift-replay
python3 -B workspace/aes-256-gcm/tools/enumerate_rank6_scalar_prefixes.py --out runs/rank6-lift-replay/inventory.json --frontier-out runs/rank6-lift-replay/frontier.json
python3 -B workspace/aes-256-gcm/tools/verify_rank6_scalar_frontier.py --inventory runs/rank6-lift-replay/inventory.json --frontier runs/rank6-lift-replay/frontier.json --tsv runs/rank6-lift-replay/frontier.tsv --out runs/rank6-lift-replay/inventory-replay.json
clang++ -std=c++20 -O3 -Wall -Wextra workspace/aes-256-gcm/tools/scan_norm_frontier_pairs.cpp -o runs/rank6-lift-replay/producer
clang++ -std=c++20 -O3 -Wall -Wextra workspace/aes-256-gcm/tools/verify_norm_frontier_pairs.cpp -o runs/rank6-lift-replay/independent
runs/rank6-lift-replay/producer runs/rank6-lift-replay/frontier.tsv runs/rank6-lift-replay/producer.jsonl
runs/rank6-lift-replay/independent runs/rank6-lift-replay/frontier.tsv runs/rank6-lift-replay/independent.jsonl
python3 -B workspace/aes-256-gcm/tools/compare_norm_frontier_pair_scans.py --input runs/rank6-lift-replay/frontier.json --producer runs/rank6-lift-replay/producer.jsonl --independent runs/rank6-lift-replay/independent.jsonl --out runs/rank6-lift-replay/comparison.json
```
