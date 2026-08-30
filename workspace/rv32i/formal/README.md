# Formal verification of the RV32I core

Bounded model checking of the multi-cycle core against
[riscv-formal](https://github.com/YosysHQ/riscv-formal), driven by SymbiYosys
and z3.

```sh
./workspace/rv32i/formal/run              # generate and run every obligation
./workspace/rv32i/formal/run insn_addi_ch0  # run one
python3 workspace/rv32i/formal/formal_collect.py
```

## Why this is different from the simulation loop

The simulation loop chooses stimulus and observes what happens. Formal
verification states a property and asks a solver whether any input can violate
it. The memory response signals in `wrapper.sv` are left free, so the proofs
hold for every memory behaviour the interface permits rather than for the one a
testbench happens to implement.

It earned its place immediately. The first campaign failed every branch and
every jump, because both cores were missing the instruction-address-misaligned
exception: B- and J-immediates encode multiples of two, so a target can be 2 mod
4, which RV32I without the C extension must trap on. The random corpus never
built such a target, the reference model had the identical omission, and
CV32E40P did not disagree because as an RV32IMC core it has IALIGN=16 and the
target is legal for it. See `../docs/WORKFLOW.md`.

## Setup this host needed

* `sby` is not in Homebrew. It is cloned into `temp/` and run from a virtualenv
  that supplies its one dependency, `click`.
* riscv-formal defaults to the `boolector` solver, which is not packaged here.
  `checks.cfg` selects z3 instead.
* The generated Makefile must run with `-k`. Without it one failing obligation
  leaves the rest unrun, and a check that never executed is indistinguishable in
  a summary from one that was not needed.

## What is claimed, and what is not

Each check proves that no counterexample exists **within its configured depth**.
That is far stronger than a passing corpus and is still not an unbounded proof.
Depths are recorded next to each result.

`liveness` fails and is reported as inapplicable rather than removed. It asserts
that another instruction always eventually retires; this core has no trap
handler and no `mtvec`, so it halts permanently on a trap, and a solver that
supplies an illegal instruction reaches a state with no successor. The reason is
recorded in `formal_collect.py` next to the exclusion, because deleting a
failing obligation and excusing one look identical in a summary and only the
written reason separates them.

The RVFI interface lives behind `` `RISCV_FORMAL ``, so the synthesizable core is
unchanged when the macro is absent.
