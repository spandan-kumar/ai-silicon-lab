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

Five actual sequential controls pass, including a two-AND cubic that really
uses a nonlinear operand and the nine-AND field multiplier. Separate review
reconstructs all eight sequential control/search CNFs byte for byte,
replays all three SAT models, and exhausts 5,616 tiny two-gate topologies.
This verifies the broader search mechanism, not its unresolved main answer.

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
Raw scripts, CNFs, proofs, stdout/stderr and provenance remain in the local
ignored directories `runs/aes-eight-and-norm-20261018/`,
`runs/aes-eight-norm-code-audit-20261018/` and
`runs/aes-eight-norm-theory-20261018/`. They are not silently represented as
GitHub-hosted evidence. No RTL, PPA, physical-security or energy result follows.
