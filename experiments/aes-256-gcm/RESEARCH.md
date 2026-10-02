# AES-256-GCM research record

This is a dated research record for Experiment 002. It identifies the sources
that define the primitive and the verification vocabulary; it is not a
certification claim. If a source changes or a successor publication becomes
normative, update this record and the experiment manifest before changing the
profile.

Research date: 2026-08-29

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
