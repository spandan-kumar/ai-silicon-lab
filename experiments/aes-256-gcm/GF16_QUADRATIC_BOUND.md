# A certificate-backed boundary for the quadratic norm-stage route

Date: 2026-10-18. This is a scoped research result, **not a world-first claim**
and not an improved AES circuit.

## Result and model

Multiplication in `GF(16) = GF(2)[t]/(t^4+t+1)` needs exactly **nine ANDs**
in the following model: each AND multiplies two arbitrary affine forms of
the original eight input bits, and outputs are arbitrary affine combinations
of inputs and AND results. Factors may mix the two four-bit operands. XORs
and NOTs are free; the ANDs are parallel. This is stronger than a
bilinear-only restriction but weaker than arbitrary sequential AND circuits.

The lower bound combines independently reconstructed finite reductions with
an UNSAT certificate checked by DRAT-trim and a separate LRAT checker. The
nine-AND upper bound is an actual tower-field Karatsuba construction,
independently evaluated on all 256 input pairs. The entire semantic reduction
is not formalized in a proof assistant; the clausal UNSAT certificate is
machine-checked, while the reductions have source review and exact finite
crosschecks.

The four coordinates of the `GF(256)` norm `x^17` have the same complexity
in this model. In a quadratic tower, write `x = a + bz`, with
`z^16 + z = 1` and `nu = z^2 + z` in `GF(16)`. Then
`N(a+bz) = a^2 + ab + nu*b^2`. Squaring and field-basis changes are
GF(2)-linear, so this differs from multiplication only by free linear maps.
The explicit embedding, tower basis and identity were checked on every byte.

This closes the proposed **eight parallel affine-input ANDs** norm stage.
It does not close a stage with nonlinear intermediate operands, arbitrary
27-AND AES designs, or a changed AES construction.

## Why the normalized instance covers the model

1. All 15 nonzero output combinations have polar rank eight. One product
   of affine forms has polar rank at most two, so every nonzero decoder
   codeword must select at least four products. Decoder dimension is four.
   With at most seven products, total weight of the 15 nonzero words is at
   most `7*8 = 56`, but their minimum weights require at least `15*4 = 60`.
   Hence at least eight products are necessary. A putative eight-product
   solution cannot contain a redundant or affine product.
2. Unique-RREF enumeration checks all 200,787 dimension-four binary
   subspaces of length eight. Exactly 30 have minimum distance at least four.
   They are exactly the full coordinate-permutation orbit of the decoder
   with rows `ff, aa, cc, f0`. A separate implementation checks the same
   tables. Thus every eight-product solution can be written `C p = B f`
   modulo affine terms, with that fixed decoder `C` and invertible `B`.
3. The output basis `B` is not fixed by assumption. A field scaling of one
   input operand normalizes the first row of `B` to `e0`. The remaining
   basis matrix fixes `e0`, so its inverse permutes the eight columns of
   `C`—exactly the four-bit columns whose first coordinate is one. A product
   permutation therefore makes `B` the identity. All 20,160 invertible
   four-bit bases have explicit scaling/permutation witnesses.
4. Determinant-one `GF(16)` changes of the two field inputs preserve each
   output polar: the extra square terms are GF(2)-linear. Their action on
   the 255 nonzero input linear forms is transitive. Consequently, the
   first product's left factor can be raw input bit zero without changing
   the now-fixed target basis. All 4,080 group matrices and all 255
   covectors were checked independently.
5. A change of basis inside an operand plane changes its product only by
   affine terms. Each plane can therefore use the unique highest-pivot
   form with left pivot below right pivot and right coefficient zero at
   the left pivot. With first left factor bit zero, adding it to the right
   factor clears that right coefficient. No arbitrary global gate sorting
   is imposed after fixing `C`.
6. For each of the 28 off-diagonal input pairs, the encoder equates the
   actual product coefficients to the four fixed output polars. Diagonal
   terms are free linear corrections. Every factor choice in this exact
   normalized search is represented by Boolean selector bits. Its UNSAT
   result therefore excludes eight parallel products; the nine-product
   construction supplies the matching upper bound.

## Executed evidence

The initial unnormalized search is inconclusive: CryptoMiniSat exit 15,
93.040 seconds wall. After the justified normalization, CryptoMiniSat returns
UNSAT/20 in 8.266 seconds wall. This is not a timeout being promoted to a bound.

The signed native-XOR instance has 652 variables, 1,519 ordinary clauses
and 172 XOR constraints. A second implementation reconstructs it byte for
byte. The independent XOR-to-CNF audit enumerates 149,796 auxiliary
extensions and reproduces the ordinary CNF exactly: 1,876 variables,
6,587 clauses. All original clauses are retained; each XOR has exactly one
auxiliary extension when true and none when false.

CaDiCaL returns UNSAT/20 on that CNF in 0.558 seconds command wall and
emits a DRAT certificate. DRAT-trim returns VERIFIED/0 in 0.450 seconds
command wall. It reports two ignored unit-deletion warnings; those warnings
are retained. A derived LRAT certificate then passes the separate
`lrat-check` program, exit 0, in 0.759 seconds command wall.

| Artifact | SHA-256 |
|---|---|
| Normalized native-XOR instance | `b68fb7934669d38a10419d02ee83b3acf8919d1c4bf2b53231ec49ed567552b8` |
| Plain CNF | `0ca93bf55d3bdbca7a6c893b93ef4b6924731e52bce0bbaa7f2027b12d712887` |
| DRAT certificate | `0f1ffd1333cf58f2e92d55655570129204647ff1bc5ab41d12859a9e2d2b9895` |
| LRAT certificate | `2739a510b3af4da92b142565b20635e132605d090daba141ebcfa551a0481549` |

The solver and checkers were built locally from their official MIT-licensed
sources: [CaDiCaL](https://github.com/arminbiere/cadical) revision
`c60730422e758ef1cebe7aeddf2dda31c996bf04`, and
[DRAT-trim/LRAT-check](https://github.com/marijnheule/drat-trim) revision
`2e3b2dc0ecf938addbd779d42877b6ed69d9a985`. They are verification tools;
no downloaded candidate circuit or unreviewed prior-art search program was
executed.

## What is still unresolved

A distinct full-truth encoding allows every later AND to take arbitrary
linear combinations of all earlier signals, with zero-gate padding and free
affine output decoding. Input symmetries partition all 10,795 possible first
operand planes into three orbits of sizes 510, 85 and 10,200. Each of their
representative eight-AND probes times out, exit 15, at approximately
61.4–61.5 seconds wall. These timeouts exclude nothing.

A different solver subsequently tests all three full-truth representatives
after a separately reconstructed plain-CNF translation. Each reaches its
90-second real-time limit and explicitly reports `c UNKNOWN`, exit 0.
The original wrapper's result field remains null because it parsed only
`s`-prefixed status lines; the retained summary interprets the explicit
UNKNOWN line without rewriting that original record. Exit zero here is not
SAT, UNSAT or a completed exclusion. Two positive models and the negative
quartic control pass; all six translated instances match independent bytes.

Five actual sequential controls pass, including a two-AND cubic that really
uses a nonlinear operand and the nine-AND field multiplier. Separate review
reconstructs all eight sequential control/search CNFs byte for byte,
replays all three SAT models, and exhausts 5,616 tiny two-gate topologies.
This verifies the broader search mechanism, not its unresolved main answer.

### Counterexample and prefix-witness follow-up

A complete model need not impose all ordinary output rows immediately.
The new search fits a selected input set, then evaluates the actual masks
on all 256 inputs and adds failures. No subset SAT result is a correct field
multiplier. All nine base-campaign partial field fits fail the full table;
their first five gates also have target deficit four with only three gates
remaining, so none can extend.

For target rank m modulo affine functions, k total ANDs and i prefix ANDs,
the target/prefix intersection has dimension at least m-(k-i). At k=8,
m=4,i=5 this forces a nonzero target combination into the prefix span.
A hybrid implementation enforces that witness on every input, with its
target direction free, while ordinary outputs still use counterexample
feedback. Its six partial field fits satisfy the prefix requirement but
still fail complete multiplication. All three searches remain UNKNOWN.
The [retained study](../../workspace/aes-256-gcm/reports/sbox_norm_cegis_study.json)
includes independent byte-level CNF, model, feedback and witness checks.

### Extending the boundary to quadratic intermediate gate truths

An auxiliary reduction checks the case where AND operands may themselves
be quadratic but every produced gate truth remains degree at most two.
For quadratic P,Q whose product H=PQ is quadratic, H can be expressed as
a combination of P,Q, an affine function and at most one product of two
raw-input affine forms. The compact finite certificate handles every
non-affine P up to affine input change:

- Symplectic coordinates reduce P to a sum q_r of r disjoint products,
  plus a linear part and a constant. Translations remove paired linear
  terms. A nonzero radical linear term becomes one extra coordinate z
  and can absorb the constant. This leaves eleven cases for 1<=r<=4.
- For P=q_r, the complete quadratic-product kernel has H in span(P).
  For P=q_r+1, H+Q lies in span(q_r). For P=q_r+z with r>=2,
  H lies in span(P). For P=x0*x1+x2, H is quadratic in only those
  three coordinates, hence has polar rank at most two.
- An affine P is a separate elementary case. After taking P=x0,
  absence of cubic terms forces Q=x0*L+l with affine L,l, and
  H=x0*(L+l) is one raw-input affine product. Constant P is immediate.

Multiplication by fixed P is linear in Q. An independent implementation
recomputes all 407 high-degree map columns, checks rank/nullity and all
62 kernel-basis truth witnesses, so these image-space conclusions hold for
every admissible Q, not only sampled ones. The earlier full diagnostic also
enumerates 131,288 Q choices. Canonical coverage and the following induction
are reviewed mathematics, not machine-formalized theorem statements.

Inductively, each all-quadratic gate can be replaced by at most one parallel
raw-input product plus already available affine combinations. This preserves
the available truth span and never raises the AND count. Therefore the
certificate-backed parallel nine-AND bound also prevents an eight-AND
implementation whose every intermediate remains quadratic.

Any eight-AND escape must consequently generate degree above two. At least
two gates must use earlier nonlinear results: with only one such gate it
would be the only possible higher-degree truth, could not appear in a
quadratic output without cancellation, and could not be used by a later
gate. Removing it would leave a forbidden parallel implementation. This
condition did not apply to the earlier campaigns. The later ladder/escape
campaigns impose it but remain inconclusive; it does not exclude general
eight-AND circuits with multiple nonlinear dependencies.

### Nested prefix and higher-degree escape follow-up

The necessary target intersections at prefixes five, six and seven have
dimensions at least one, two and three. Because the intersections are nested,
three jointly independent, otherwise free target combinations can witness
them. The encoding uses full truth tables for the first seven gates and
keeps the final output fitting counterexample-guided. It imposes at least
two distinct gates with prior-AND operand coefficients, not merely two
selected coefficients in one gate.

Some gate among gates two through seven must have degree above two. If only
the last gate were nonquadratic, every quadratic output would omit it,
leaving an excluded all-quadratic seven-gate implementation. For each
zero-preserving gate truth g, the unique quadratic interpolant is determined
by singleton and pair inputs. At input support S it is
`(|S| mod 2) * XOR_{i in S} g(e_i) XOR XOR_{i<j; i,j in S} g(e_i+e_j)`.
A mismatch on any higher-weight input exactly witnesses degree above two.
This does not require two nonquadratic truths or a quadratic final gate.

The ladder-only and ladder-plus-escape campaigns each test all three
first-plane cases with 30-second real-time CNF-solver budgets; all six
return UNKNOWN. A native-XOR second solver also reaches its 30-CPU-second
limits in all three escape cases. Positive controls include an actual
dependent quartic and the nine-AND field multiplier. These bounded probes
prove no exclusion and establish no speedup. The
[retained follow-up](../../workspace/aes-256-gcm/reports/sbox_norm_escape_study.json)
records independent reconstruction and replay checks.

The algebra review exhausts 200,787 abstract target subspaces and all 32,768
zero-preserving four-input truths. Root separately checks equality of the
eight-input interpolation and high-degree-projection linear maps on all
255 truth-basis vectors and 256 inputs, plus all 4,096 rectangular 3-by-4
rank instances. The dependency cut is GF16-specific; the current scripts
dispatch it by input/budget/rank shape and must not be reused for arbitrary
targets of that shape. Canonical reductions remain reviewed mathematics,
not an end-to-end proof-assistant formalization.

### Concrete nonlinear prefixes and exact continuation

The preceding scalar counterexample supplies a constructive family:
`g1=L1*L2`, `g2=(g1+L3)*L4`, `g3=g1*L4`, `g4=L5*L6`, `g5=L7*L8`.
Their XOR is the sum of four independent pair products, chosen here to be
GF16 output bit zero. Gates two and three carry the same cubic high part.
Canonical factors, all 120 single orthogonal transvections and 32 seeded
four-step words yield 153 actual prefixes and 150 distinct available spaces.
This is a generated finite family, not all decompositions or all prefixes.

Without the constant-one function, each available space P has dimension 13;
adding the four field outputs gives an envelope T of dimension 16. Three
ANDs remain in an eight-AND implementation, exactly the target deficit.
Every new gate must therefore lie in T and add one independent direction.
An outside-T or redundant gate would consume the rank-tight budget.

For each nonzero left operand L in P, the map `R -> L*R modulo T` is linear.
Its complete kernel gives every eligible right operand. It suffices to test
the products of a kernel basis for a direction outside P. Enumerating all
8,191 nonzero left forms finds no useful product for any of the 150 spaces:
P is already closed inside T. Affine constants add only terms already in the
available affine span, so their omission does not restrict this conclusion.
This exactly excludes three-AND completion of those fixed prefixes only.

Independent review replays all 150 input spaces and their ranks, target
decoder and actual degrees. It completely repeats the canonical and one
mixed scan using different row-equation nullspaces, and compares the root
engine against brute force on 512 small nested spaces, including 58 real
extension steps. It does not claim to repeat all 150 full scans. Three
selected solver continuations also return UNSAT, without certificate checks;
the separate finite closure evidence is not dependent on those verdicts.
See the [retained concrete study](../../workspace/aes-256-gcm/reports/sbox_norm_concrete_prefix_study.json).

### Joint target/first-plane normalization

A first-five-gate target witness may be normalized to output coefficient bit
zero using field input scalings, but the first factor plane must transform
at the same time. Complete enumeration of all 15 nonzero target covectors
and 10,795 binary input planes gives 161,925 joint states and seven orbits.
The fixed-target fiber has representatives `(1,2)`, `(1,12)`, `(1,16)`,
`(1,32)`, `(1,96)`, `(1,112)`, `(1,128)`, with sizes 510, 85, 2720, 2720,
1360, 2720 and 680. Later target directions remain free and independent.

Root separately rebuilds every primal/dual action using polynomial long
division, checks 34,560 scalar target truth rows, and reconstructs the joint
orbits with union-find. The original three first-plane cases are still
complete with a free first target direction; fixing that direction while
keeping only those three would omit four classes. These seven normalized
cases are subsequently tested with free prefix gates and the first target
fixed. All seven return UNKNOWN at their 30-second real-time limits.
Independent review rebuilds 29 control/search CNFs and replays 21 SAT control
models, including the correctly normalized nine-AND construction. No speedup,
new full circuit or unrestricted exclusion follows.

### Synthesized-prefix lookahead and projected outputs

A smaller pilot synthesizes actual five-slot prefixes computing output bit
zero on all 256 inputs, then applies exact closure lookahead. Seven distinct
spaces outside the preceding 150-space family are found and excluded for
eight-AND completion. Five have genuinely nonquadratic intermediate truths;
one is all-quadratic, and one has a zero fifth gate. The actual available
ranks are used: six spaces have rank 13 and the padded space rank 12. All
have target deficit three, so the three-slot continuation remains rank-tight.
Five other bounded prefix probes end UNKNOWN and exclude nothing.

Root separately rebuilds all 13 pilot formulas and verifies all eight SAT
models including the known control, exact factor-model blocking and scalar
output truth. A different row-equation nullspace implementation completely
rescans every obtained prefix. This extends the tested fixed-space union to
157, not to every possible prefix. No separate agent audits this new glue
after delegated work reaches a provider credit limit.

The same follow-up verifies an eight-product circuit for the first three
GF16 output bits. Every three-dimensional output hyperplane is field-scale
equivalent. A complete code audit finds 30 qualifying length-seven,
dimension-three decoder spaces, all one simplex orbit; no length-six code
qualifies. A free-basis seven-product realization probe remains INDETERMINATE,
so the projected complexity is locally bounded between seven and eight, not
proved equal to eight. The author-posted MF-167 entry already addresses this
projected problem and claims the stronger lower bound; no priority is claimed.
The [retained normalized/pilot study](../../workspace/aes-256-gcm/reports/sbox_norm_normalized_search_study.json)
separates these outcomes and verification limits.

### New counterexamples and linear family barriers

The later five-gate scalar-Q counterexamples have higher-degree ranks two
and three. All three actual spaces have rank 13 and field envelope rank 16;
complete independent scans show each is already closed. Together with the
previous 157 spaces this yields 160 fixed-space exclusions.

There is also a family-wide statement. Write `A` for affine functions, `H`
for projection modulo degree at most two, and `K` for the quadratic part of
the prefix space modulo `A`. To enumerate products eligible for any quadratic
target, fix every nonzero left operand and compute the complete right kernel
of `R -> H(LR) mod H(P)`. Enumerating every kernel vector covers every actual
eligible product. Subtract a prefix function with the same high part to get
a quadratic residue `q`; its class modulo `K` is independent of that choice.

For the explicit construction
`p=ab; (p+c)d; (p+e)f; (p+g)h; p(d+f+h)`, their sum is
`Q=ab+cd+ef+gh`. Here `K=span(p,Q)` modulo affine terms. The complete inventory
contains 61,504 unordered nonzero pairs and 13,081 polar residue cosets.
Every coset has a representative of polar rank at most four. If a product
were useful inside `P+T`, with `T` a four-dimensional quadratic target space
whose every nonzero polar has rank eight and containing `Q`, its residue
would equal `t+k`, where `t` is outside `span(Q)` and `k` is in `K`.
Every representative then has polar rank at least `8-rank(p)=6`, a
contradiction. Thus `P` is closed inside `P+T`.

For each of the two synthesized rank-two spaces, the available quadratic
polar space `K` has dimension three. Exact inventories contain 54,976 and
50,080 eligible pairs, with 11,111 and 11,482 residue cosets. No coset has
any representative `t` for which both `rank(t)=8` and `rank(t+Q)=8`.
This also checks the zero coset, so `K` intersects such a target space only
in `span(Q)`. Any useful target product would require exactly such a pair;
hence these spaces are likewise closed inside every such `P+T`.

Invertible linear input substitutions preserve Boolean multiplication,
degree filtration, affine terms and quadratic polar rank. These obstructions
therefore cover every linear input version of the three specified spaces
whose `Q` maps into the target modulo affine functions. Target intersection
dimension is one, so three remaining ANDs are rank-tight and cannot escape
the envelope. This does not classify all five-gate scalar circuits or prove
an unrestricted eight-AND field lower bound. No orbit cardinality is claimed.

Root independently recomputes the complete rank-three inventory using
symbolic Boolean-ANF multiplication and different nullspaces; separate
truth-table products, Mobius transforms and high-pivot kernels reproduce
the two rank-two inventories. The rank-three calculation is reproducible
without ignored runs using
`python3 workspace/aes-256-gcm/tools/verify_norm_family.py`.
The [retained family study](../../workspace/aes-256-gcm/reports/sbox_norm_linear_family_study.json)
records scope, controls, source hashes and the subsequent unresolved
six-gate constructive probes. The semantic argument is reviewed mathematics,
not a proof-assistant formalization or a novelty claim.

### Output pairs and the global higher degree budget

Every independent two-output projection has quadratic/parallel complexity
six. All 35 explicit upper circuits are independently checked. The three
nonzero decoder words require weight at least four, but their sum is at
most `2k`, giving `k>=6`. At equality each nonzero column type occurs twice.
Field scaling alone gives plane orbits 15, 15 and 5; simultaneous Frobenius
merges the generic two, leaving 30 and 5. Neither class needs seven products.

The published Mirwald–Schnorr two-output optimality theorem, explicitly
reported in [Boyar–Find section 4](https://arxiv.org/html/1407.6169v3#S4),
transfers this bound to unrestricted pair circuits. This is an invoked
literature theorem, not a reproof from decoder weights or a locally checked
formalization. Replacing an arbitrary optimal pair prefix by a quadratic
one need not preserve its extra wires or extension cost.

Here is a useful selector-space consequence. Let `H:F2^8 -> higher-degree
ANF` map coefficient vectors to the degree-above-two part of their gate
combination. Let `E_i` be the first `i` coordinate space, `r_i=rank(H|E_i)`,
and choose the four output decoder rows as a section `D` of the target space
modulo affine functions. This section has dimension four and lies in
`ker(H)`, even if gate functions are redundant. For
`s_i=dim(D intersect E_i)`, the subspace sum with `ker(H|E_i)` gives

```text
8-r_8 >= 4+i-r_i-s_i
r_8-r_i <= 4-i+s_i
```

A full-rank scalar quadratic needs four ANDs, so `s_1=s_3=0`; since the
first gate is quadratic, `r_1=0`. Therefore `r_8<=3` and `r_8-r_3<=1`.
These conclusions do not need the two-output transfer theorem. Invoking
that theorem gives `s_5<=1`, hence `r_8=r_5` by monotonicity. In particular,
any higher-degree direction must appear by gate five. The already verified
all-quadratic eight-gate exclusion makes `r_5>0` necessary under this theorem.

Even without the pair theorem, a higher-degree gate must occur by gate six:
if the first six were quadratic, their target intersection would be exactly
two. It is at least two by the suffix budget, and cannot be three because
seven nonzero distance-four decoder words need total weight at least 28,
above the length-six total of 24. The remaining two target directions are
then rank-tight, forcing both suffix gate truths into the quadratic
prefix-plus-target envelope, contradicting the quadratic eight-gate bound.

Jointly normalizing a first scalar direction and its two-output plane gives
three flags, not two pair classes: 105 states have orbits 15, 30 and 60.
With first covector one, second covectors 12, 4 and 2 represent the three.
An independently justified determinant-one input change can also fix the
first left operand to raw bit zero without fixing its whole factor plane.
All three new nonquadratic six-prefix probes remain UNKNOWN. No unrestricted
eight-gate exclusion or measured speedup follows. See the
[pair study](../../workspace/aes-256-gcm/reports/sbox_norm_pair_frontier_study.json)
and [standalone pair verifier](../../workspace/aes-256-gcm/tools/verify_norm_pairs.py).

## Prior art and availability

The [Find–Boyar paper](https://arxiv.org/abs/1407.6169) is prior work on the
connection between quadratic circuits and codes. The elementary weight
argument and finite code classification here do not constitute a claimed
new general method.

The earlier author-posted [MF-167 entry](https://slopdealer.com/research/papers/mf-167/),
dated 2026-09-04, explicitly claims the same mixed-input quadratic nine-AND
bound. Its small archive did not provide the main enumeration/proof material
needed for our independent replay; we inspected it as data only. That gap
does not erase its earlier claim or justify calling our result a world first.
Our certificate and audited reduction are separate evidence for the scoped
bound, not a claim of priority.

The machine-readable retained summary is
[sbox_norm_stage_study.json](../../workspace/aes-256-gcm/reports/sbox_norm_stage_study.json).
The [second-solver follow-up](../../workspace/aes-256-gcm/reports/sbox_dependent_norm_solver_study.json)
retains its separate terminal UNKNOWN outcomes.
Raw scripts, CNFs, proofs, stdout/stderr and provenance remain in the local
ignored directories `runs/aes-eight-and-norm-20261018/`,
`runs/aes-eight-norm-code-audit-20261018/` and
`runs/aes-eight-norm-theory-20261018/`. They are not silently represented as
GitHub-hosted evidence. No RTL, PPA, physical-security or energy result follows.
