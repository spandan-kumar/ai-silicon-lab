# Measuring and improving the spec-to-RTL workflow

The goal of this experiment is not an RV32I core. It is the loop that produces
one: how quickly it finds defects, what classes it is blind to, and whether a
change to it actually helps. Two cores were built so the loop could be measured
on an easy design and then applied to a harder one.

Everything below is measured. Where a number could not be obtained, it says so.

## The measurement that makes the loop improvable

Coverage says what the stimulus touched. Agreement says nothing disagreed.
Neither says whether the loop would notice a defect if one existed. Mutation
testing answers that directly: inject a realistic single-point defect, run the
loop, record whether it is detected.

Mutation score is the number a workflow change is judged against. A change that
raises coverage but not mutation score has not been shown to help.

`workspace/rv32i/reference/mutation.py` rebuilds the RTL per mutant, so a
campaign takes minutes rather than seconds and is run deliberately, not on
every pass.

## Ground truth, and its limits

| Source | Independent of this repo | Status |
| --- | --- | --- |
| `riscv-opcodes` encoding tables | yes | used; 38 instructions conform |
| Instruction set simulator in `reference/` | **no** — same author as the RTL | used for all execution comparison |
| CV32E40P, vendored in this repository | yes | **used**; 621 programs agree |
| `riscv-arch-test` | yes | toolchain and Sail now present; still blocked on Zicsr and M-mode CSRs the core does not implement |
| `sail-riscv` executable model | yes | **used**; 121 programs agree, and it enforces the rule CV32E40P could not |
| `riscv-formal` proof obligations | yes | **used**; per-instruction semantics proven by bounded model checking |

**The limitation that used to matter most, and how it was closed.** The
reference model and both cores were written from the same specification by the
same author. A misreading would appear in all three, they would agree, and the
loop would report success. The encoding layer was protected because
`riscv-opcodes` is independent; the execution layer was not.

CV32E40P closes it. The same corpus runs on an OpenHW Group core that is
silicon-proven, developed elsewhere, and vendored here unmodified: **621 of 621
programs agree**. Architectural state is compared through a memory signature,
the technique `riscv-arch-test` uses, because CV32E40P exposes no register-file
read port and must not be changed to add one — the program writes its own final
register values to memory and the comparison happens afterwards on the image.

The check was verified to be capable of failing before its passing result was
believed. Injecting a single defect into the reference model — SRAI performing
a logical shift — produced disagreement in 7 of 51 programs, showing exactly
the sign-extension difference (`321` against `0xFFFFFF41`). A cross-check that
has never been seen to fail is not evidence that anything agrees.

What remains open: agreement was established for the instruction subset and
stimulus distribution used here. It is not a proof of RV32I compliance, which
is what `riscv-arch-test` and `sail-riscv` would provide, and both remain
unavailable on this host.

## What formal verification found that 1,241 test programs could not

riscv-formal generates a proof obligation per instruction and drives it with
SymbiYosys and z3. The memory response signals are left free, so the proofs
hold for every memory behaviour the interface permits rather than for the one a
testbench implements. Nothing is sampled: the solver chooses the inputs.

The first campaign failed every branch and every jump. The assertion was
`spec_trap == trap`, and the specification's own model sets `spec_trap` when a
control-flow target is not four-byte aligned.

**The core was missing the instruction-address-misaligned exception.** B- and
J-immediates encode multiples of *two*, so a branch or jump target can be 2 mod
4. RV32I without the C extension has IALIGN=32, and such a target must raise an
exception rather than being taken. Both cores simply jumped there.

Three independent-looking layers of testing had all missed it:

* **The random corpus** never built a misaligned target, because the generator
  computes offsets in whole instructions.
* **The reference model had the identical omission.** Same author, same reading
  of the specification, same blind spot. This is exactly the shared-author
  failure mode, and it survived the CV32E40P cross-check.
* **CV32E40P did not disagree**, because it is RV32IMC. With the C extension
  IALIGN=16 and a 2-mod-4 target is perfectly legal, so on this specific rule it
  implements a different ISA and is the wrong oracle.

That last point is the sharpest lesson available here. An independent
implementation is only an oracle for the specification it implements. CV32E40P
closed the shared-author gap for everything the corpus reached and for every
rule the two ISAs share, and it was silently useless for a rule where they
differ. Formal verification has no such dependency: it checks against the
specification the checker encodes, and it constructs the input itself.

Both cores now raise the exception, and the reference model does too. The
campaign then completed clean: **43 of 43 applicable obligations pass, and all
37 RV32I instructions are proven**, along with the register, forward and
backward program-counter, uniqueness, causality, and cover consistency checks.

`liveness` is the forty-fourth obligation and is reported as inapplicable rather
than removed. It asserts that another instruction always eventually retires;
this core has no trap handler and no `mtvec`, so it halts permanently on a trap
and a solver supplying an illegal instruction reaches a state with no successor.
That is the specified behaviour of a bare RV32I core with no privileged
architecture, not a defect. The reason sits next to the exclusion in
`formal_collect.py`, because deleting a failing obligation and excusing one look
identical in a summary and only the written reason separates them.

What the proofs claim: no counterexample exists **within each check's configured
depth**, for any memory behaviour the interface permits, since the memory
response signals are left free. That is far stronger than a passing corpus and
is still not an unbounded proof.

## Workflow configurations

| Name | Stimulus |
| --- | --- |
| `w1-random-v1` | Flat random programs, forward control flow only |
| `w2-random-v3` | Block-structured generation, centred data pointer, signed memory offsets |
| `w3-directed-plus-random` | w2 plus directed encoding-boundary tests |
| `w4-hazards` | w3 plus directed pipeline-hazard tests |

## Measured results

### Multi-cycle core, 26-mutant catalogue

| Workflow | Mutation score | Killed | Survivors |
| --- | ---: | ---: | --- |
| `w1-random-v1` | 0.577 | 15/26 | 11 |
| `w2-random-v3` | 0.846 | 22/26 | 4 |
| `w3-directed-plus-random` | **0.923** | 24/26 | 2, both equivalent |

Two mutants are unkillable, so w3 detects **24 of 24 killable defects**.

### Pipelined core, 10-mutant catalogue

| Workflow | Mutation score | Killed |
| --- | ---: | ---: |
| `w1-random-v1` | 0.900 | 9/10 |
| `w2-random-v3` | 0.900 | 9/10 |
| `w3-directed-plus-random` | 0.900 | 9/10 |
| `w4-hazards` | 0.900 | 9/10 |

### Coverage and agreement

| Measure | Value |
| --- | --- |
| RV32I instructions covered | 37/37 |
| Named corner bins covered | 17/17 |
| Encoding conformance | 38 instructions, 0 findings |
| Differential agreement, both cores | 620 programs, 0 failures |
| Independent agreement with CV32E40P | 621 programs, 0 disagreements |
| Cross-check negative control | 7/51 disagree when the reference is broken |
| Agreement with the Sail model | 121 programs, 0 disagreements |
| Sail negative control | 15/61 disagree when the reference is broken |
| Formal proof obligations | 43/43 applicable pass, 0 fail |
| RV32I instructions formally proven | 37/37 |
| Verilator branch coverage (pipeline) | 97.6% (41/42) |
| Verilator expression coverage (pipeline) | 98.8% (83/84) |
| Verilator toggle coverage (pipeline) | 80.7% (2239/2776) |

Toggle coverage is dominated by upper PC and address bits that cannot change
while programs are a few kilobytes. That is a property of the stimulus size,
not a defect.

## What each workflow change bought, and what it did not

**Block-structured generation (w1 to w2, +0.27).** The largest single gain, and
it came from fixing a defect in the *generator*, not from adding stimulus. w2's
first version added multi-instruction constructs to a flat generator whose
branch offsets were counted in instructions. A forward branch could land inside
a loop construct, skipping its counter initialiser, and 14 of 60 programs never
terminated. Making the block the unit of generation, with every control-flow
target a block boundary, fixed it. Centring the data pointer so memory offsets
take both signs came from a surviving mutant: with the pointer at the base of
the region, every offset was non-negative and an S-immediate sign-extension
defect was invisible.

**Directed encoding-boundary tests (w2 to w3, +0.08).** Random stimulus cannot
reach the high bits of a branch or jump immediate. A branch spanning a few
blocks encodes an offset of tens of bytes, so B-format bits 11 and 12 are always
zero and a defect in them changes nothing observable. Reaching them needs
distance, and distance is cheap: 512 instructions of padding costs about 1500
cycles. Two mutants died immediately.

**Directed hazard tests (w3 to w4, +0.00).** No measured effect. The pipeline
catalogue is saturated: even w1 kills 9 of 10, because any random program with
register dependencies exercises forwarding and interlocks constantly. The
hazard tests were written to kill a specific survivor and did not, because that
survivor turned out to be equivalent. **They are retained but unproven.**
Discriminating between workflows on pipeline defects needs a subtler catalogue
than the one used here, and building it is the honest next step rather than
claiming the tests helped.

## Survivors, and why classification matters

A surviving mutant is either a gap in the stimulus or a defect that no test can
detect. Recording the second as the first sends the next iteration chasing a
test that cannot exist.

**`x0-writable` and `x0-read-not-zero` (multi-cycle).** x0 is protected twice:
writes to index 0 are suppressed, and every read path forces zero. Either
mechanism alone suffices, so removing one is unobservable. Equivalent.

**`forward-ignores-validity` (pipeline).** This one was nearly misclassified.
The first analysis argued it was equivalent. Measurement disagreed: an
instrumented build counted the raw condition occurring **5787 times over 420
programs**. Narrowing the probe to the conjunction that can actually change a
result — an invalid MEM entry naming a register that a *valid* EX instruction
reads — gave **0 occurrences over 820 programs**. The reason is structural: on
a flush the squashed instruction reaches MEM in the same cycle that EX holds a
bubble.

So it is equivalent, but the first argument for that conclusion was wrong and
only measurement caught it. The equivalence is now a runtime assertion in
`rv32i_pipe.sv`, enabled with `AISL_ASSERTIONS`, so the judgement is re-checked
on every run and fails loudly if a later change makes the guard load-bearing.

**The general rule this produced:** when a mutant is judged equivalent, encode
the equivalence argument as an assertion. An argument in a commit message
decays; an assertion is re-verified.

## Defects the loop found in the designs

| Defect | Found by | Class |
| --- | --- | --- |
| SRA/SRAI performed a logical shift | random differential, 5 programs | Verilog signedness: a ternary with one unsigned branch makes the whole expression unsigned, silently degrading `>>>` |
| B-immediate assembled to 112 bits instead of 128 | Verilator lint, before any simulation | width error |
| Tag exposed on authentication failure (AES experiment) | first verification pass | security |

The signedness bug is the interesting one: it is invisible to review, produces
correct results for every non-negative operand, and was caught by the fifth
random program. It also existed at two sites, and finding one instance meant
fixing the class.

## Defects the loop found in itself

Worth listing separately, because a false failure costs an iteration just as a
real one does, and three of the four came from tooling rather than from RTL.

- Multi-instruction constructs were not atomic, so 14 of 60 programs hung.
- Control-flow targets could point past the terminating `ebreak` into unwritten
  memory, which decodes as an illegal instruction.
- The reference and the RTL named the same trap differently, reported as six
  divergences that were not divergences.
- Verilator overwrites `coverage.dat` per run, so an initial coverage
  measurement described one program while appearing to describe 140.
- The harness plugin passed `None` as the effective address to the coverage
  model, so the load-after-store bin could never be reached. It read as a
  stimulus gap for several iterations; it was a defect in one call.
- The `add-overflow` bin was covered by the flat generator and silently lost
  when block-structured generation changed the operand distribution. Coverage
  regressions are as real as functional ones and need the same watching.
- Directed tests used `ebreak` mid-program as a "stop here" marker. That halts
  the local cores and traps to `mtvec` on a core with a trap handler, so the
  tests were unusable for cross-checking until every program was given exactly
  one terminator.
- **The harness cached oracles without noticing when the stimulus changed.**
  Growing the RV32I corpus made four suites fail against a reference generated
  for the previous corpus. The failure was loud, but the same mechanism could
  have hidden a real divergence just as easily. Fixed in the framework: a
  plugin now declares a `stimulus_identity()` fingerprint, the runner
  invalidates a cached oracle whose fingerprint changed, and a plugin that
  cannot fingerprint its stimulus reports `staleness_detectable: false` rather
  than implying a freshness it cannot verify.

Six of the ten defects in this section and the one above are in the tooling
rather than the RTL. That ratio is itself a finding: on this loop, the
verification apparatus was a larger source of wasted iterations than the
designs it was verifying, and the measurements that caught them -- coverage
bins, mutation survivors, the equivalence probe -- were worth more than any
single test.

## Making the loop better: tooling

Ordered by what removes the largest blind spot per unit of effort.

**1. Cross-check against CV32E40P.** *Done.* Wired into the harness as
`policy:cross-check-cv32e40p` and mapped to the `independently-cross-checked`
gate, so every verification pass now includes a comparison against ground truth
this repository did not write. The OBI memory model queues responses because
CV32E40P's prefetcher keeps several transactions outstanding.

**2. `riscv-formal`.** *Done, and it paid for itself immediately.* The core
carries an RVFI interface under `RISCV_FORMAL`, so the synthesizable design is
unchanged without the macro. `workspace/rv32i/formal/run` stages the design into
a scratch clone, generates the obligations, and solves them with z3.

Two configuration notes worth keeping: riscv-formal defaults to the `boolector`
solver, which is not packaged for this host, so the config selects z3; and the
generated Makefile must be run with `-k`, or one failing obligation leaves the
rest unrun and a check that never executed looks indistinguishable from one that
was not needed.

**3. Verilator RTL coverage in the loop.** *Done, not yet wired into the
harness.* Branch and expression coverage answer a different question from ISA
coverage: whether the stimulus exercises the *implementation*, including logic
that no instruction reaches. Merging per-run files is required; a single
`coverage.dat` is overwritten.

**4. A RISC-V toolchain.** `workspace/tools/bootstrap-riscv-toolchain` installs
a pinned xPack GCC. It unlocks `riscv-arch-test`, real compiled programs, and
stimulus a hand-written generator will not produce: function prologues, stack
frames, spills, switch tables.

**5. QEMU.** In Homebrew. A third independent execution model, useful as a
tiebreaker when the ISS and the RTL disagree and it is not obvious which is
wrong.

**6. `sail-riscv`.** The official formal model and the strongest available
execution ground truth. Needs a Sail/OCaml toolchain, which is the largest
install of anything listed here.

**7. Waveform capture.** Verilator `--trace` plus GTKWave. The differential
harness reports first divergence with a disassembly, which has been sufficient
so far; waveforms become worth the cost for a bug that report cannot localise.

## Cost

The loop is cheap, which is why it can be run constantly.

| Operation | Cost |
| --- | --- |
| 1000 random programs, 178k instructions, multi-cycle | 4.9 s |
| Full workflow, both cores, 620 programs each | ~12 s |
| Encoding conformance, 38 instructions | under 1 s |
| Mutation campaign, 26 mutants with rebuilds | ~60 s |
| riscv-formal, 44 obligations with z3 | minutes, run deliberately |

Median detection latency for a killable defect is 2 random programs. The
expensive part of the loop is not running it.

Formal is the exception and is worth its cost differently. It is too slow to
run on every pass, so it is run deliberately and its results are read by the
harness rather than produced there — a proof that was not run is reported as
unavailable, never as a pass. It found in one campaign a conformance defect that
1,241 programs across two independent execution oracles had missed, because it
constructs its inputs instead of sampling them.
