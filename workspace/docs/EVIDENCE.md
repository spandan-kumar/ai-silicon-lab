# Simulation-complete evidence

This record identifies the final pre-evaluator candidate and the measured
artifacts that establish the simulation-complete milestone. Generated files
are retained below `.aisl/` and build directories but are intentionally
ignored by Git; the committed source, build commands, pinned toolchain, and
hashes make them independently reproducible. The official evaluator and its
clean-worktree reproduction add their immutable records below `runs/`.

## Candidate identity

| Artifact | SHA-256 or identity |
| --- | --- |
| OpenHW CV32E40P RTL | tag `cv32e40p_v1.8.3`, revision `360d272898d81806be3377193870dbf83a3ea79f` |
| DoomGeneric source | revision `dcb7a8dbc7a16ce3dda29382ac9aae9d77d21284`, upstream tree `413539bdaa1521af167d9b34e9db0cd193367624` plus declared local changes |
| firmware ELF | `22e430bcdd826929155c2617a965940b94a0d68ff54d1b8b0ebcbd7483b84214` |
| firmware flat image | `f92ddb3cfe23206b4b5c1a78e8e64730ff932061f6607db3b278f6da5a1239df` |
| cycle-accurate simulator | `b876dda114914251fc7f850d9447450004829bdbc1c859c9524e77b966ed5945` |
| simulator RTL aggregate | `fc04549e092234587ef821706847eda1b2e3022989091d7a12f0ad1823160665` |
| Freedoom 0.13.0 Phase 1 WAD | `7e3d5dbc1b11ed55c2c8aa44d4843ba1bb64780b4066f96898158d99b93fdf0f` |
| protected canonical input | `5bf11852ccc26b0b3795e63ab8f568e1fa9c22ec9484e59baca63291e2087975` |

The 489,040-byte RV32IMC image was built by GCC 14.2.0/binutils 2.43.1 with
`-O3` and link-time optimization. Its ELF contains 429,600 text bytes, 59,436
data bytes, and 240,624 BSS bytes. The build maps the worktree-dependent DWARF
compilation directory to `workspace/firmware/doom`; both the ELF and flat image
therefore reproduce byte-for-byte in linked worktrees. Verilator 5.050 executes
the synthesizable RTL at both clock phases; no host ISA emulator or Doom
renderer participates.

## Protected canonical workload

The final direct run under `.aisl/canonical-simulation-complete/` returned
zero, reported boot/start/finish true and trap/failure false, and produced all
120 required frames after the 64-frame warmup.

| Measurement | Value |
| --- | ---: |
| cycles | 744,664,922 |
| retired instructions | 581,003,386 |
| boot cycle | 429,298 |
| Doom-start cycle | 31,117,064 |
| first-capture cycle | 228,353,358 |
| finish cycle | 744,664,922 |
| simulated frames / game tics / captures | 184 / 145 / 120 |
| captured bytes | 23,040,000 |
| measured simulator wall interval | 259.33 seconds |

The independently concatenated RTL frames and protected archive have the same
SHA-256,
`07f7eecc32a52cfd424c3523184332c49bc9627168a45b67f4a57d3c18f8f833`,
and `cmp` returned zero. The result's internal framed-stream digest is
`e0c05401bb9dea1c6673a56e7c8560e6a9b3ee4fb8823f3c238119ae7b2899cc`.
The cycle, native-execution, and sampled-retirement trace digests are:

- `903c475602d3cff471e9569464ba94f738ee1733e6d2207c36ce09b3d239f759`;
- `fda8dc56dc6fa18118205123a005addbbd196ac8abb8da8557db3ee956349a40`;
- `77737111ad70b1a30e3f8afadc24d5954777ae839d3a6843381ffa87042025bc`.

The result JSON itself hashes to
`72cd4962350674870716e3bda0d56acd04913f0f46119754f3f021a23c8cfc9a`.

## Strengthened exact-oracle workloads

The reference executable has SHA-256
`9be615002fb670d2b5fb60be08eb2172daa772fe70b591a3ff209306047fe26b`.
Each reference archive was accepted only after two byte-identical runs from
separate sanitized homes. The final RTL suite compared every one of 736
captured frames exactly, with no missing or extra frames.

| Workload | Frames | Oracle archive SHA-256 | RTL frame-stream SHA-256 |
| --- | ---: | --- | --- |
| idle E1M1 | 96 | `876e370a300f3ddb75399b81159eebcd358c3ae669bee153c9b484680058ed8a` | `46864642902fc1986f38180a56cda8a71758bfbb60a981b8d0542dd4a4db952d` |
| movement/combat E1M1 | 256 | `15d79a47a0696201c9de005fa701068ea082f04fbb7ecfb491e3329b917e15ea` | `7d347b47f968be6865f70c37d0b914dc6cf5ca31b19bda6645e2d7491914e311` |
| alternate E1M2 skill 3 | 192 | `70654cdef1f3b00229dd0c9975ce5675b67704103dc078e8991b333a047609a4` | `c5dc4c3eac59b70b8356d3fc71246f17b7a491ca829f9d8c632448cf1f7b15c8` |
| overlap E1M3 skill 4 | 192 | `0ab52c29db0d78cf9af8a65c0968e7e8b1e04b57ec04ddb45758fed600536dc3` | `6ecd45950ec68ab5545ef6f676e9516e5b61ddea472ac3c0a53deeea7747e7b0` |

| Workload | Cycles | Retired | Cycle trace SHA-256 | Retirement trace SHA-256 |
| --- | ---: | ---: | --- | --- |
| idle E1M1 | 640,655,706 | 500,135,333 | `98b6389aedce88c8f88210c7b7a18f9965f3f4e2f8a6a02825585854e1bbc81e` | `903abc2f3274c1478f1c5128dd4bffe10c3db120ac120e8439238dfc250580c1` |
| movement/combat E1M1 | 1,236,203,544 | 969,749,015 | `66e5cb2b960b865059e051cea88d208b059a2e05c70ef5c34bb9097a0967e4e4` | `7956001a5ac06784a65da1d0018aa3b959c58dcc97638f6c8ced9f8984efe4b1` |
| alternate E1M2 skill 3 | 983,382,917 | 770,238,900 | `8aeaa9ae90105ba9668a87fe483da3007c1aecf09bdf180af003984a825aa5bb` | `995f100ba3258321c5c302232be38392a6aa3d35b4e41edd17e8ef365aabacd8` |
| overlap E1M3 skill 4 | 876,013,015 | 697,938,392 | `c20c26e666f54b3b74daa2686259e658e6e2a57718ec4cc5c2be5e296fe7c774` | `87c192bc66d9a0b2637ee6efbbe40393430038efd115e69b4891c8c12ae13c68` |

The corresponding sampled native-execution digests are
`faeab0c1cd637a444acd9e312fd3efcc2ce9ceebed2c4a0b9bf909af438afd3d`
(idle),
`2cc12918813f9a0344c778ec8ca53cd22d3a0dea456e9d7042f4901cbf22864c`
(movement/combat),
`b49234ae94684790143c86cac8aaf5e81c4b086c735d1d90e2731b8dc46cae6d`
(alternate), and
`1ceadf9993f78f121661247e9c0171fd7092003ad9a635a33929eff67addbba8`
(overlap).

The suite summary is
`.aisl/verification/rtl-suite-simulation-complete/suite-result.json`, SHA-256
`9f6d7e7e276fd00341bb653e5669a33045501f625c7fa7c10051c123f9718006`.
Its process exit was zero and `correct` is true.

## Synthesis evidence

The exact final RTL configuration was converted with sv2v 0.0.13 and
synthesized with Yosys 0.68+post. A clean run returned zero, `check` reported
no problems, and the result contains 40,209 generic cells:

| Cell class | Count |
| --- | ---: |
| sequential (`DFF*`/`DFFE*`) | 2,691 |
| mux | 4,629 |
| AND / ANDNOT / NAND | 23,402 |
| OR / ORNOT / NOR | 4,015 |
| XOR / XNOR | 5,263 |
| NOT | 209 |

There are 36,663 wires, 61,326 wire bits, and no inferred memories. The latter
is expected: the explicitly modeled 64 MiB dual-port SRAM is outside the SoC
synthesis boundary. Generated artifact SHA-256 values are:

| Artifact | SHA-256 |
| --- | --- |
| converted SystemVerilog aggregate | `b706b2bb46c3720fab5b8124840fa2efcfdf82512d39b95d9432d92baa58e16c` |
| JSON netlist | `1a24b00957d4705c1d232b7d705e56dc88f548bbf7cfd5ada0dcb1a271d4150e` |
| Verilog netlist | `16b99053f70d74147f8da8d79a09d707d6ed9d7f9568b7ec11b34938963cb542` |
| post-fix local synthesis log | `1c40deb58a0a9e522fe45e6e2d368342b059bfbb362eccee615e131630f9fb3a` |

The netlists and converted source reproduce byte-for-byte. The synthesis log
hash identifies this retained run but is not expected to match another host
run because Yosys writes elapsed time and peak-memory measurements into its
footer; the evaluator and reproducer retain and hash their own logs.

## Reproduction commands

From the repository root:

```sh
./lab/status
make -C workspace candidate
python3 -m unittest workspace/verification/test_oracle.py
python3 workspace/verification/oracle.py generate
python3 workspace/verification/run_rtl_suite.py \
  .aisl/verification/rtl-suite-reproduced --jobs 4
./lab/evaluate --run-id simulation-complete-final-3
./lab/reproduce simulation-complete-final-3
```

`lab/evaluate` performs the authoritative canonical build, execution, exact
oracle comparison, timeout enforcement, and protected-integrity checks.
`lab/reproduce` requires a clean committed revision and evaluates it from an
independent linked worktree. The synthesis recipe forces Yosys's temporary
directory to `/tmp`: Yosys 0.68's bundled ABC cannot parse an evaluator
temporary path containing the repository's spaces.
