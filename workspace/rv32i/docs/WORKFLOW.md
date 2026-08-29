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
| CV32E40P, vendored in this repository | yes | not yet used; the obvious next step |
| `riscv-arch-test` | yes | unavailable: needs a RISC-V toolchain and a reference model to generate signatures |
| `sail-riscv` formal model | yes | unavailable: needs a Sail/OCaml toolchain |

**The most important limitation.** The reference model and the RTL were written
from the same specification by the same author. A misreading of the
specification would appear in both, they would agree, and the loop would report
success. The encoding layer is protected against this because `riscv-opcodes` is
independent; the execution layer is not. Every "agrees exactly" result below
should be read with that caveat attached.

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

Six of the ten defects in this section and the one above are in the tooling
rather than the RTL. That ratio is itself a finding: on this loop, the
verification apparatus was a larger source of wasted iterations than the
designs it was verifying, and the measurements that caught them -- coverage
bins, mutation survivors, the equivalence probe -- were worth more than any
single test.

## Making the loop better: tooling

Ordered by what removes the largest blind spot per unit of effort.

**1. Cross-check against CV32E40P.** *Highest value, already local.* The
repository vendors a silicon-proven RV32IMC core. Running the same programs on
it and comparing architectural state would close the one gap nothing else
closes: that the reference model and the RTL share an author. It needs an OBI
memory model and a way to observe its register file, both of which
`workspace/sim_cv/` already demonstrates. No downloads.

**2. `riscv-formal`.** *Highest value overall.* A SymbiYosys-based framework
that proves per-instruction ISA compliance rather than sampling it. It replaces
"24 of 24 mutants killed" with "no counterexample exists within N cycles",
which is a categorically stronger statement. `yosys-smtbmc` ships with the
Yosys already installed here and z3 5.1.0 is now installed; `sby` is not in
Homebrew and needs a source install from YosysHQ.

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

Median detection latency for a killable defect is 2 random programs. The
expensive part of the loop is not running it.
