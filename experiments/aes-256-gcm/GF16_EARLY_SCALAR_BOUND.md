# The early-scalar branch of an eight-AND GF(16) multiplier

Date: 2026-10-20. Reviewed reduction plus two-method finite evidence; not a
proof-assistant formalization, global eight-AND exclusion, or novelty claim.

## Statement and dependencies

For `GF(16)=GF(2)[t]/(t^4+t+1)`, consider an eight-AND Boolean XOR/AND
circuit computing all four multiplication outputs, with free affine
operations. Under the published scalar-optimal structure theorem stated
below, no nonzero field-output combination can already belong to the
affine span of the first four AND outputs.

Equivalently, in this branch analysis the first available nonzero target
direction must appear at gate five: the three later gates can contribute
at most three of the four required target dimensions. This does not say
that such a gate-five circuit exists or that it is impossible.

Dependencies are explicit:

1. The strong scalar statement of Mirwald–Schnorr, as stated in
   [Jukna, ECCC TR05-021, Section 2, Theorem 1](https://eccc.weizmann.ac.il/report/2005/021/download/):
   every AND-count-optimal circuit for a scalar quadratic form is
   single-level. The weaker statement that some parallel optimum exists
   would **not** suffice to preserve an arbitrary prefix's extra wires.
   The primary research paper's statement was rechecked on 2026-10-20;
   the original 1992 full proof has not been independently reproduced here.
2. The [certificate-backed quadratic nine-AND bound and quadratic-gate
   flattening reduction](GF16_QUADRATIC_BOUND.md). The clausal refutation
   is checked; the semantic reductions are reviewed mathematics with
   finite crosschecks, not a formal theorem development.
3. Complete operand-plane classification and the 192-class product
   obstruction. The classification has two different algorithms; the
   entire product campaign now has a symbolic/Pfaffian second-method
   replay. Both product implementations have the same primary author;
   this is algorithmic independence, not an external peer review.

The proof below does not invoke unrestricted two-output optimality.

## 1. Normalize an actual scalar-optimal prefix

Write `A` for all affine Boolean functions. Every nonzero field-output
combination has a nondegenerate rank-eight alternating polar form. Such a
scalar needs at least four ANDs, even in an arbitrary dependent circuit:
successively setting one nonconstant affine operand to zero makes a
k-AND circuit affine on a nonempty affine subspace of codimension at most
k. A rank-eight quadratic is affine only on directions forming an
isotropic subspace of dimension at most four. Thus `k>=4`.

If a target scalar `Q` is available by gate four, those four gates are an
optimal scalar circuit; none can be unused in its actual output cone.
Invoke dependency 1 for that actual circuit, after eliminating redundant
XOR expressions. Its gates are products of raw-affine forms. All four
products participate in `Q` modulo `A`, since three have polar rank at
most six. The rank-eight sum of their four rank-two polars is supported
on those eight factor linear forms, so the eight forms are independent.

Use them as coordinates and remove operand constants. This preserves the
available span modulo `A`, leaving

```text
p_i = a_i*b_i,  i=0,1,2,3
K0 = span(p_0,p_1,p_2,p_3),   Q = p_0+p_1+p_2+p_3 mod A.
```

Transport the **whole** target space `T` by the same input change.
`T` has dimension four modulo `A`, contains `Q`, and all fifteen nonzero
members have rank eight. In `K0`, polar rank is twice the number of
selected disjoint products. Consequently `K0 intersect T=span(Q)`.
Normalizing `Q` does not justify fixing the original other field tables.

## 2. Gate five must be nonquadratic

The final three gates force at least one target direction by gate five;
the final two force at least two by gate six.

Suppose gate five is quadratic. If gate six is the first nonquadratic
gate, it cannot participate in a quadratic combination of the first six
gate truths. Hence two independent target directions are already
available after five quadratic gates. Flattening preserves that available
span with at most five parallel products. This is impossible: the three
nonzero two-output decoder words each need weight at least four, whereas
their total weight over five columns is at most ten, below twelve.

Otherwise all first six gate truths are quadratic. Their target
intersection is at least two-dimensional and cannot be three-dimensional:
seven nonzero decoder words would have total weight at least 28, whereas
six columns contribute at most 24. It is therefore exactly two-dimensional.
The last two gates have exactly the two-dimensional target deficit to
fill. Any signal outside the quadratic prefix-plus-target space would
waste a needed dimension. Both final gates must be quadratic, contradicting
dependency 2. Thus gate five is nonquadratic.

## 3. Cover every possible fifth product

Modulo constants, the four-product precursor has basis the eight raw
coordinates and four `p_i`, dimension twelve. Dependent or zero operand
pairs modulo constants produce an old wire, not a nonquadratic gate.
Independent pairs span one of `G(12,2)=2,794,155` two-planes. Changing the
ordered basis within a plane changes its product by an available operand;
it preserves the fifth-prefix space, even when that operand is quadratic.

The group `(AGL(2,2))^4 semidirect S4`, order 7,962,624, acts by affine
changes inside each input pair and pair permutations. It preserves `A`,
`K0`, and `Q mod A`. It transports `T` jointly and preserves polar ranks.
Nineteen explicit generators give 216 plane orbits; an independent
local-block-type multiset calculation identifies all representatives and
their exact orbit sizes. The nonquadratic subset comprises 192 orbits and
2,781,824 planes. This classification is finer than a classification of
fifth-prefix spaces, which is harmless for completeness.

For each representative, let `h` be its actual fifth product,
`W=A+K0+span(h)`, and `H` its nonzero degree-above-two part.
Both implementations scan all 8,191 nonzero left forms modulo constants.
For a fixed left form `L`, multiplication by each of the thirteen basis
signals gives thirteen columns. Solving the complete linear condition

```text
high_degree(L*R) belongs to span(H)
```

gives a right-operand kernel. Every kernel vector is checked and all its
combinations are enumerated. After subtracting zero or one copy of `h`,
the product residue is quadratic. Its polar is reduced modulo `K0`.
All sixteen offsets are tested, including the zero coset. No class has an
offset `r` with both `rank(r)=rank(r+Q)=8`.

The producer uses truth-table AND, a Mobius transform, high-pivot labelled
column elimination and Gaussian polar rank. The second method uses
symbolic Boolean monomial multiplication, low-pivot **row-equation**
kernels and 16-point Pfaffian truth tables from all 105 perfect matchings.
All 192 product-pair and coset counts agree. The replay finishes with
exit zero in 45.747 seconds command wall time. Independent-method controls
include 448 brute-force kernels, 33,858 Pfaffian/rank comparisons, 4,096
offset comparisons and an actual six-parallel-product positive pair.

## 4. Why the necessary-condition test excludes a completion

`W` has exactly `K0` as its quadratic part modulo `A`, so its target
intersection is just `span(Q)`. Three target directions remain and only
three gates remain. Thus every suffix gate must increase the available
span inside `W+T`; in particular the next product must be in `W+T` but
outside `W`.

Its operands are in `W`; adding operand constants changes its product by
old wires only. Its high part must be cancellable by `h`. The resulting
quadratic residue differs by `K0` and an affine function from a new target
direction `t` independent of `Q`. Both `t` and `t+Q` have rank eight.
The exhaustive scan explicitly tests that possibility and never admits it.
This contradicts the required first useful suffix gate.

Therefore the Q-by-four branch is excluded under the stated dependencies.
The remaining eight-AND problem has its first target direction at gate
five. The theorem above does not classify those five-gate prefixes and
does not imply a complete GF(16) or AES lower bound. It is not a claim of
priority over existing literature.

## Additional transfer controls: a separate result

A previously unexecuted draft is now run in a fresh directory. Its 524,800
six-input diagonal-product shadow comparisons pass, as do all 256 rows of
the embedded collision and its two-product replacement identity. Its
annihilator controls pass for rank-six/rank-eight canonical forms and all
listed affine perturbations; a rank-four boundary correctly has a larger
kernel. These are separate finite controls, not dependencies of the
192-class branch proof. In particular, replacing two gates while losing
their intermediate wire does not prove a cost-preserving arbitrary-suffix
flattening theorem.
