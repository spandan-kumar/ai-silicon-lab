# Provisional Q-by-four source snapshot — 2026-10-20

These are frozen research programs, not candidate accelerator RTL. The
[progress document](../../../../experiments/aes-256-gcm/PROGRESS.md)
explains the question and limitations. The
[committed inventory](../../reports/sbox_norm_q4_snapshot.json) contains the
original representatives and terminal results.

The producer found no necessary rank-eight-pair escape in 192 nonquadratic
fifth-gate classes over a four-disjoint-product precursor. The orbit
classification has a separate algorithmic check. **The complete product
campaign has not had an independent replay.** Repeating the same producer
below checks reproducibility, not independence, and does not establish an
unrestricted eight-AND bound or a world-first result.

## Reproduce in a new output directory

Requirements: Python 3 with its standard library and a C++20 compiler. The
recorded compiler was Apple clang 17. Keep assertions enabled; do not use
`-DNDEBUG`. Outputs are exclusive-create and must not replace original runs.
Run from the repository root:

```sh
q4_output=$(mktemp -d)
cp workspace/aes-256-gcm/tools/norm_q4_snapshot/*.py "$q4_output/"
cp workspace/aes-256-gcm/tools/norm_q4_snapshot/*.cpp "$q4_output/"
clang++ -O3 -std=c++20 "$q4_output/orbits.cpp" -o "$q4_output/orbits"
clang++ -O3 -std=c++20 "$q4_output/scan.cpp" -o "$q4_output/scan"
python3 "$q4_output/capture.py" enumerate "$q4_output/orbits" "$q4_output/report.json"
python3 "$q4_output/capture.py" orbit-audit python3 -B "$q4_output/orbit_audit.py"
python3 "$q4_output/capture.py" canonical-control "$q4_output/scan" 256 4 "$q4_output/canonical-control.json"
python3 "$q4_output/capture.py" campaign python3 -B "$q4_output/campaign.py"
```

Expected: 216 total plane classes, 192 nonquadratic classes, 192 complete
producer scans and zero escapes. `campaign.json` deliberately retains its
independent-replay-pending status. `cases/` retains each command's exit code
and stdout/stderr. Compare exact counts, not wall times.

The 12 base coefficient bits mean raw variables `a0,b0,...,a3,b3`, then
products `a0*b0,...,a3*b3`. A scan adds the thirteenth basis wire, the product
of its two supplied base masks. Constant corrections add old wires and are
absorbed by the affine quotient. Input symmetries must transport the entire
target space jointly; fixing only `Q` is insufficient to fix the field target.

## Additional retained work

`transfer_collision.py` is the executed small diagonal-prefix collision
search. It writes `report.json`, so run a copy in a separate fresh directory,
not alongside the orbit outputs. It stops at its first counterexample; it
does not claim to exhaust all 524,800 possible products.

`transfer_verify_unexecuted.py` is an **unexecuted draft** of additional
transfer and annihilator controls, retained for handoff. Neither its
assertions nor its printed intended success fields are test evidence.

The separate bounded SAT search, its imports and CNFs remain in local ignored
`runs/aes-norm-q4-pair-search-20261019/`. Its eight-input results are one
UNKNOWN and one solver-reported UNSAT without a checked proof certificate
or complete independent encoding audit. This snapshot does not package
those earlier run-local dependencies. Original raw logs and binaries are
not included in Git; the inventory records their hashes.
