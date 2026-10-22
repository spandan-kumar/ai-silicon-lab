# Remaining nonquintic prefixes: the independent-raw-input branch

Date: 2026-10-22. This is an exact scalar-prefix inventory and search
normalization, not a complete field multiplier or an exclusion of all
eight-AND field circuits.

The [machine-readable frontier study](../../workspace/aes-256-gcm/reports/sbox_norm_q5_quartic_first8_study.json)
retains complete per-representative counts, exact orbit multiplicities,
source hashes and raw-archive identities.

The [quintic result](GF16_QUINTIC_PREFIX_BOUND.md) leaves actual gate
degrees at most four in the five-gate, eight-input, rank-eight quadratic
scalar problem. This follow-up treats only first-four raw rank eight;
the raw-rank-six/seven nonquintic branches remain separate questions.

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

## What remains

No three-gate field continuation is tested by this inventory. A next
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
Raw-rank-six/seven prefixes, complete continuations and the full
eight-AND multiplier remain open.

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
