# A wire-preserving input normal form for five-gate scalar prefixes

Date: 2026-10-20. This is a search formulation and reviewed reduction,
not a new field multiplier, circuit lower bound, solver speedup or
world-first claim. The full circuit search remains unresolved.

**2026-10-22 follow-up:** complete rank-seven/eight enumerations and
independent full replays now close the quintic branch described below.
The formerly open 487 classes are therefore no longer open **for that
branch only**. The [quintic-prefix note](GF16_QUINTIC_PREFIX_BOUND.md)
also replaces the rank-six step's imported strong-theorem dependency
with a self-contained saturated-scalar induction. Quartic prefixes and
the unrestricted eight-AND field multiplier remain unresolved. The
original UNKNOWN solver result and historical counts below are retained.

## Premise: eight-dimensional raw-input span

After zero-preserving normalization, write an ordered five-AND prefix as

```text
g_i = U_i V_i
U_i = l_i(x) + sum_{j<i} a_ij g_j
V_i = r_i(x) + sum_{j<i} b_ij g_j.
```

The ten raw linear forms `(l_1,r_1,...,l_5,r_5)` must span all eight
input coordinates if the prefix computes a quadratic scalar of polar
rank eight, modulo affine corrections. Otherwise a nonzero direction
annihilates every raw form. All five gate functions are invariant in
that direction, and any decoded output has a constant derivative there.
A nondegenerate quadratic cannot have such a nonzero direction.

This is the elementary raw-input-span argument underlying the existing
dimension bound; the topology/input distinction and scalar dimension
bound are prior art in [Calik–Sonmez Turan–Peralta, Sections 2–3](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=928931).
Our purpose is to preserve the **whole prefix wire space**, not merely
replace its scalar output by another optimal circuit.

## 621 ordered raw-factor classes

A rank-eight list of ten raw forms defines a surjection from `F2^10` to
`F2^8`, with a two-dimensional relation kernel `K`. Two such lists with
the same kernel differ by an invertible input-coordinate change. There
are `(1023*1022)/6 = 174,251` possible relation planes.

Group the ten positions into five ordered operand pairs. For an ordered
relation basis `(u,v)`, a pair contributes a 2-by-2 coefficient block.
Under local `GL(2,2)` changes, there are five local types: the zero block,
three rank-one types and one rank-two type. Changing the relation basis
permutes the three rank-one types and fixes the other two.

The number of length-five type words modulo that permutation is

```text
(5^5 + 3*3^5 + 2*2^5)/6 = 653.
```

Exactly 32 word orbits have relation rank below two. Removing them leaves
**621 ordered classes**. Direct enumeration of all 174,251 planes agrees
with a different weighted block-word calculation on every class and its
size. Taking the quotient by `K` explicitly constructs ten canonical
eight-bit raw forms for each class.

Allowing arbitrary permutations of the five pairs gives a diagnostic
count of 35. That smaller count is **not** used for circuit coverage:
arbitrary pair permutations need not preserve topological gate order.
The 621 count concerns raw-factor lists, not a finite classification of
all five-gate circuits. Earlier-gate coefficients remain free.

## Why output corrections must stay in the model

A local operand-basis change is not harmless if its output correction
is silently dropped. Let `(U',V') = M(U,V)` and `N=M^-1`. Boolean
idempotence gives

```text
UV = U'V' + sigma U' + tau V'
sigma = N00*N10,   tau = N01*N11.
```

Invertibility of `N` prevents `sigma=tau=1`. Therefore the transformed
model needs three possible output shifts per gate: none, `U'`, or `V'`.
These add no AND cost. Keeping this correction preserves the **actual
function of g_i**, so subsequent gates can continue using the same wire;
their raw factors need not be silently rewritten.

Normalize the raw kernel by independent operand-basis changes, choose
the explicit quotient-coordinate map, and retain all five output shifts.
Every original gate truth is then preserved after the common invertible
input substitution. Thus every prefix span, affine output decoder and
possible later continuation is preserved. Conversely a shifted wire is
one bare AND plus available affine combinations; a unit-triangular
rewrite compiles the representation back to exactly five ANDs.

The implementation checks the six local basis changes on all four
operand-bit assignments. It normalizes **1,026** full-rank test circuits,
including the known cubic and quartic prefixes, and compares every gate
on all **256** inputs: **262,656** scalar rows. Affine output decoders
also transport exactly. These finite controls accompany the algebraic
proof; they are not an exhaustive enumeration of all nonlinear traces.

Two negative controls show why the correction is substantive. Omitting
it can change an available prefix span. In a recoded rank-eight quartic
fixture, the correct scalar has degree two and polar rank eight, while
dropping one required shift gives degree three and quadratic-part rank
four. Both original and corrected artifacts are retained.

## A global degree-five probe, not a conclusion

The new formula selects one of all 621 raw-factor matrices, leaves the
earlier-wire coefficients and output shifts free, and asks for a decoded
quadratic scalar with an invertible eight-by-eight polar matrix. It also
requires a degree-five coefficient in the fourth gate and the proper
five-gate scalar dependency cone. The scalar's coordinate table is
**free**: normalizing the input matrix does not permit fixing the old
canonical `Q`, let alone the other three field-output tables.

The chosen scalar uses gate five. In the intended field search this
follows from the [early-scalar exclusion](GF16_EARLY_SCALAR_BOUND.md).
The proper-cone requirement uses the same dependency: an unused gate
would leave an at-most-four-gate scalar ancestor cone that could be
scheduled first. Graph reachability remains only a necessary condition,
not a claim of semantic minimality.

The main plain CNF has 40,524 variables and 185,731 clauses. It returns
**UNKNOWN** at its 60-second limit. The known shifted quartic and relaxed
rank-six/generic-quintic controls are admitted. Missing-shift,
quartic-as-quintic and singular-polar controls are rejected. Rejection
controls have no checked UNSAT proof certificate and are not field
exclusions.

An independently written Boolean builder and XOR-to-CNF serializer
reconstruct all seven control/search CNFs byte-for-byte. All 768 scalar
rows of the three positive models are separately replayed, including
their compilation to bare ANDs. A second control pass checks 55,845
residual-versus-ANF evaluations, the one-AND shifted identities, and
primitive Boolean/XOR truth conditions. The first audit's range-only
shift check was replaced by the actual identity; its source/log remains
preserved. Both methods share a primary author; this is algorithmic
independence, not external peer review or proof-assistant formalization.

## A separate rank-six-prefix lemma

The raw-input span of the first four gates has dimension six, seven or
eight. These cases partition the 621 ordered classes into **134, 337 and
150**, respectively. Local operand-basis changes and the common input
change preserve this prefix rank.

The six-dimensional case cannot have a degree-five fourth gate while
computing a quadratic scalar of polar rank eight after gate five,
**invoking the strong scalar-optimal structure theorem** stated in
[Jukna, Section 2, Theorem 1](https://eccc.weizmann.ac.il/report/2005/021/download/).
The original 1992 proof is not independently reproduced here.

Proof: choose old coordinates `z` spanning the six prefix-input
directions, and two new coordinates `x,y` from the last operand raw
forms. The first four wires depend only on `z`. The last shifted product
has the form

```text
g5 = (x+A(z))(y+B(z)) + sigma(x+A(z)) + tau(y+B(z)).
```

Gate five must participate in the scalar decoder: otherwise the unique
possible degree-five fourth wire must also be omitted, leaving a
rank-eight quadratic from at most three ANDs. That contradicts the
scalar four-AND lower bound. The degree bound ensures the first three
wires have degree at most four.

Since the decoded scalar is quadratic, its coefficients of `x` and `y`
must be affine functions of `z`. Those coefficients are `B(z)+sigma`
and `A(z)+tau`, up to free affine output corrections. Thus `A` and `B`
are affine, `g5` is quadratic, and its polar has rank at most two.
The degree-five fourth wire must now be omitted from the quadratic
scalar decoder as well. The remaining first-three-wire combination is
quadratic, depends on at most the six old directions modulo affine
terms, and has polar rank at least `8-2=6`. Its rank is exactly six.

Those three ANDs are therefore a scalar-optimal circuit. The invoked
strong structure theorem makes its actual ANDs single-level; after
compiling the shifted representation to bare gates, its first three
wires are quadratic too. A fourth product of quadratic operands, plus
available shifted operands, has degree at most four. This contradicts
the proposed degree five. The weaker theorem that some alternative
three-AND scalar optimum exists would not preserve the needed wires.

This is reviewed mathematics under that explicit literature dependency,
not a conclusion from the UNKNOWN probe. It excludes 134 raw-input
classes **only for the quintic branch**. Quartic behavior is still
admitted in this raw-rank case: a retained five-gate witness has degrees
`2,3,4,4,2` and computes a rank-eight quadratic. A separate generic
`2,3,4,5,2` witness has a nonquadratic scalar, confirming that the raw-rank
premise alone does not prohibit a quintic gate.

## Next questions at the 2026-10-20 checkpoint

No global degree-five exclusion follows from UNKNOWN or the rank-six
lemma; **487** ordered raw-input classes remain in the rank-seven/eight
cases. Nor are all quartic prefixes classified.

In the rank-seven case, a local last-operand basis change isolates the
one fresh coordinate, giving a last shifted wire of the form
`A(z)(x+B(z)) + sigma A(z) + tau(x+B(z))`. Its fresh derivative is
`A(z)+tau`. A quadratic decoded output forces `A` to be affine, but
**does not force B affine**. Replace `A` by its equal raw-affine
expression, retain the output correction or rewrite all downstream
decoders, and preserve the prefix span. This supplies a one-affine-factor
last-gate normal form for that branch, not a proof of its impossibility.
The separate finite controls distinguish this one-fresh case from the
two-fresh case and deliberately admit a nonlinear `B`.

If the first eight raw factor forms are independent, an input change
alone fixes them to coordinate units, without any operand shifts.
Neither specialized rank-seven/eight search had been executed at that
checkpoint; the 2026-10-22 follow-up above supersedes that status.

The normal form is intended to make global prefix analysis practical;
its existence and small controls do not establish that it makes the
solver faster or that a novel complete circuit has been found.
