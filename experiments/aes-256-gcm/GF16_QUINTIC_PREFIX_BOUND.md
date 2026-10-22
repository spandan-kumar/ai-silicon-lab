# The quintic five-gate scalar branch

Date: 2026-10-22. This note separates reviewed reductions from finite
enumeration evidence. It is not a full GF(16) lower bound, a new complete
AES circuit, external peer review or a priority claim.

## Question and scope

Can five Boolean AND gates on **eight input bits**, with free affine operations, compute a
quadratic scalar of alternating polar rank eight while the fourth AND
wire has algebraic degree five? The scalar's input coordinates are free:
no fixed field-output truth table is imposed after changing coordinates.
The answer is a necessary condition for a possible eight-AND GF(16)
multiplier, not a sufficient construction of one.

The ordinary degree bound says a function computed with `k` ANDs has
degree at most `k+1`; see the prior-art discussion in
[Calik–Sonmez Turan–Peralta, Section 3](https://tsapps.nist.gov/publication/get_pdf.cfm?pub_id=928931).
Thus the first three wires have degree at most four. A rank-eight
quadratic decoder in the quintic branch must use gate five: otherwise
it must omit the unique potentially quintic fourth wire, leaving at most
three ANDs and at most six raw factor directions.

The present computation has complete producer scans and full independent-
method numerical replays for raw ranks seven and eight. All per-case or
per-relation counters and histograms agree. The finite evidence is linked
in the [retained study](../../workspace/aes-256-gcm/reports/sbox_norm_q5_quintic_study.json).

## A self-contained saturated scalar lemma

**Lemma.** If `k` actual AND gates compute a quadratic scalar of polar
rank `2k`, then every actual AND wire is a quadratic Boolean function.
Constants in its affine operands are permitted.

Proof by induction. There are only `2k` raw factor covectors in the
entire circuit. The scalar's polar rank cannot exceed their span rank:
every direction annihilating that span leaves all gate functions
unchanged, and its scalar derivative is constant. Such a direction is
in the scalar polar's radical. Consequently all `2k` covectors are
independent. Use them as input coordinates, writing the final gate as

```text
g_k = (x+A(z))*(y+B(z)),
```

where `z` comprises the earlier `2k-2` factor coordinates. Free affine
output terms can be subtracted without changing quadraticity or rank.
The final gate must participate in the scalar: the earlier gates depend
only on `z` and cannot supply a rank-`2k` polar.

The coefficients of `x` and `y` in the quadratic decoded scalar force
`B(z)` and `A(z)` to be affine. Thus `g_k` is quadratic and its polar
has rank at most two. Subtracting it leaves the actual first `k-1` gates
computing an old-coordinate quadratic of rank at least `2k-2` by rank
subadditivity, and at most `2k-2` by its support. Its rank is exactly
`2k-2`, so induction applies to those same gate wires. The base case is
one product of affine functions. This proves the lemma.

This proof establishes the property needed here without importing the
strong scalar-optimal theorem quoted in earlier notes. That theorem is
still prior art, not a discovery claimed by this lab. The lemma concerns
actual gate functions; it does not assert that every syntactically
redundant reference to an earlier gate disappears from a written circuit.

The [truth-table controls](../../workspace/aes-256-gcm/tools/verify_scalar_saturation.py)
enumerate all 64 three-gate topologies with all 64 operand-constant
variants and all eight decoders; they also enumerate all 4,096 four-gate
topologies and all 16 decoders with zero operand constants. Every
rank-saturated quadratic decode has exclusively quadratic gate truths.
Smaller cases and 1,024 affine-output invariance controls pass too.
These checks supplement the induction; they are not its proof.

## Reduction to first-four raw ranks six, seven and eight

All ten raw factor forms must together span eight dimensions, by the
same radical argument. Adding the last two forms increases rank by at
most two. The first four gates' eight raw forms therefore span six,
seven or eight dimensions. This partitions the previously retained
621 ordered raw-input classes into 134, 337 and 150, respectively.

For the finite enumerations, operand constants are removed by a
unit-triangular gate rewrite. Each old wire equals its new bare AND plus
available affine combinations of earlier new wires. Prefix spans modulo
affine functions are preserved. A later raw factor changes only by a
combination of preceding raw forms, through an invertible triangular
rewrite, so every prefix raw rank is preserved. The fourth wire's
quintic part is preserved because its correction uses earlier gates of
degree at most four. This does **not** claim to preserve each earlier
wire truth or its lower-degree terms.

### Rank six: two fresh directions

Use six old coordinates `z` and two fresh directions `x,y`. The last
gate can be written `(x+A(z))*(y+B(z))`, with any free output correction
absorbed into the scalar decoder. Quadraticity forces both `A,B`
affine, so gate five is quadratic with polar rank at most two. The
quintic fourth wire must then be omitted from the scalar decoder.

The remaining first-three-gate scalar is quadratic of rank exactly six:
at least `8-2`, and at most six on its old coordinates. Apply the
saturated scalar lemma to those actual three gates. All are quadratic,
so the product defining gate four has degree at most four, a
contradiction. This replaces the earlier rank-six proof's imported
strong-theorem dependency with a self-contained argument.

### Rank eight: no fresh direction at gate five

A global invertible input change alone sends the first eight raw forms
to the eight coordinate units. No local operand-basis change or output
shift is needed. For gate `i`, choose arbitrary left and right subsets
of its `i-1` earlier gates. There are exactly
`2^(2+4+6)=4,096` ordered first-four prefixes, without a topology or
gate-permutation quotient.

Their available nonconstant space `W` has dimension twelve. Indeed,
in any purported dependence take its latest selected gate: its mixed
derivative in its own two fresh coordinates is one, whereas all earlier
gates and raw-linear terms have mixed derivative zero.

For each nonzero left form `u` in `W`, solve the complete right kernel

```text
v -> high_degree(u*v) mod high_degree(W).
```

Every right vector in this kernel admits a quadratic correction by an
old gate combination. Retain one such correction and add every polar
offset from `W`'s quadratic subspace. This covers every quadratic
scalar from one new product plus old wires. Operand constants add only
old wires and a constant, already allowed. Commutativity permits
unordered pairs, including equal factors. Deduplication is only modulo
the **full** quadratic offset space, not an assumed fixed dimension.

Exactly 2,520 prefixes have a quintic fourth gate. Their higher-degree
image ranks are two or three, so assuming rank three would be an
unsound restriction. The producer exhausts all 4,095 nonzero left forms
for each, scanning 103,795,344 eligible unordered pairs and 27,736,020
quadratic polar cosets in total. None has a rank-eight scalar offset;
the maximum attainable ranks are four or six. A quartic positive
control is admitted by the same complete scan.

### Rank seven: one fresh direction

The first eight raw covectors have a unique nonzero binary relation.
Enumerate all 255 such relation vectors, construct the quotient by that
line, and enumerate all 4,096 earlier-gate coefficient choices in each.
This covers 1,044,480 ordered prefixes; no operand-pair orbit reduction
is used.

Recoding the last operand pair isolates the fresh coordinate `x`:
`g5=A(z)*(x+B(z))`, up to available output corrections. Its fresh
derivative forces `A` affine. Its constant part changes the new wire
only by old signals and affine terms, so retain its nonzero raw-linear
part `ell(z)`. A zero linear part cannot give rank eight: all remaining
non-affine functions would depend on only the seven old coordinates.

Write `B=b_raw(z)+b0+sum beta_i*g_i`. The invertible shear
`x'=x+b_raw(z)` fixes all first-four gate functions and their degrees,
and preserves polar rank by congruence. The constant contribution is
affine. It suffices to enumerate all 16 old-gate combinations `B` and
all 127 nonzero linear `ell`.

For each `B`, the production scanner instead solves the equivalent
seven-column linear kernel for `ell*B` modulo the old higher-degree
image, enumerates all its nonzero vectors, and tests every quadratic
offset. The fresh cross-polar vector is exactly `ell`. In particular,
**B is not forced affine**. The nonlinear-B quartic control computes a
rank-eight scalar and is admitted.

The producer finds 564,480 quintic prefixes, processes 9,031,680
`B` cases, 78,779,088 eligible nonzero factors and 192,748,032 scalar
polar-rank tests, with no rank-eight completion. A separate complete
prefix-degree census agrees for every relation. Its direct decoder
checks on 504 sampled prefixes are not a substitute for a complete
second-method scalar replay. The complete symbolic-ANF, joint-row-equation
replay also finishes and matches every counter and histogram for all 255
relations, including all 192,748,032 rank tests. Its initial comparison
script failed at a control-only histogram ownership difference after all
full enumeration comparisons had passed. That failure is retained; an
explicitly instrument-normalized control comparison passes without
altering either exhaustive result.

## Evidence boundary and next question

Both producer programs and independent replay programs are retained as
ordinary research code. Their actual command records, streams and
statuses live in the ignored run archives identified by the study report.
Algorithmic independence within the same research team is not external
peer review, a checked clausal refutation or proof-assistant verification.

The completed independent replays validate the numerical claims above,
so the three raw-rank cases exclude the quintic five-gate scalar branch
under these reviewed reductions. Every five-AND circuit on eight input
bits computing a rank-eight quadratic has actual gate degrees at most four: the fourth
gate is not quintic. If the fifth participates in the decoder, it is a
quadratic scalar plus earlier wires and affine terms. If it is omitted,
the first four gates already compute the rank-eight scalar; the saturation
lemma makes them quadratic, so even an unused fifth product has degree
at most four.
This still leaves quartic prefixes and their complete field-multiplier
continuations open. It establishes neither an unrestricted eight-AND
exclusion nor a new AES S-box.

## Portable replays

Run from the repository root, using new output paths and without
`-DNDEBUG` (the scanners use assertions for semantic controls).
The fast independent programs need a C++20 compiler, not a SAT solver
or the ignored original archive:

```sh
mkdir -p runs/quintic-replay
clang++ -std=c++20 -O3 -Wall -Wextra workspace/aes-256-gcm/tools/verify_norm_q5_first8.cpp -o runs/quintic-replay/first8
runs/quintic-replay/first8 --controls --out runs/quintic-replay/first8.json
clang++ -std=c++20 -O3 -Wall -Wextra workspace/aes-256-gcm/tools/verify_norm_q5_first7.cpp -o runs/quintic-replay/first7
runs/quintic-replay/first7 --controls runs/quintic-replay/first7-controls.json
runs/quintic-replay/first7 --scan runs/quintic-replay/first7.json 1 255
python3 -B workspace/aes-256-gcm/tools/verify_scalar_saturation.py --out runs/quintic-replay/saturation.json
```

The slower, separately implemented Python symbolic replay is also
portable:

```sh
python3 -B workspace/aes-256-gcm/tools/verify_norm_q5_first8.py --out runs/quintic-replay/first8-python.json --all-quintics --controls --jobs 4
```

Production scans are available separately to compare methods:

```sh
clang++ -std=c++20 -O3 -Wall -Wextra workspace/aes-256-gcm/tools/scan_norm_q5_first8.cpp -o runs/quintic-replay/producer8
runs/quintic-replay/producer8 runs/quintic-replay/producer8.json 0 4096
clang++ -std=c++20 -O3 -Wall -Wextra workspace/aes-256-gcm/tools/scan_norm_q5_first7.cpp -o runs/quintic-replay/producer7
runs/quintic-replay/producer7 --controls runs/quintic-replay/producer7-controls.json
runs/quintic-replay/producer7 --scan runs/quintic-replay/producer7.json 1 255
```

The programs refuse existing output files; retain old results rather
than overwriting them. Measured command times and complete count
inventories are in the study report. The two C++ independent replays
are ports of the symbolic methods, not additional independent
algorithms. No full RTL corpus is rerun by these commands.
