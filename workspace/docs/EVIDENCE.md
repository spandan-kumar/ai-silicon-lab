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
| normalized firmware link map | `e72f9f055814b198953b780127fd4841fec8a02604b4c671bd62446b37ddf35a` |
| firmware source disassembly | `dca56f1caf54f4a2a58292900ded84629799db9168e908548c2279ed757b0ccd` |
| firmware ELF section/symbol report | `2f62efde70c73acc6d04bd70957f3a06611f8b8686a3c4010f6f58e3cb907001` |
| firmware checksum manifest | `f883355ecb3b4418f5c5e031e0c8c2a6d8d008ddf6c4dae7bc62516b9bdafcda` |
| cycle-accurate simulator | `1e0ae162d59670a25aa5bb90cc942a94a5bd1470d2b57777ba744495d60a028c` |
| simulator RTL aggregate | `fc04549e092234587ef821706847eda1b2e3022989091d7a12f0ad1823160665` |
| Freedoom 0.13.0 Phase 1 WAD | `7e3d5dbc1b11ed55c2c8aa44d4843ba1bb64780b4066f96898158d99b93fdf0f` |
| protected canonical input | `5bf11852ccc26b0b3795e63ab8f568e1fa9c22ec9484e59baca63291e2087975` |
| post-hardware-integration candidate | commit `10772a4eebe168956967a850a39503c7993280f1`, tree `385f811509dd3a4a0c3339a86cb680f40c39d7ba` |

The 489,040-byte RV32IMC image was built by GCC 14.2.0/binutils 2.43.1 with
`-O3` and link-time optimization. Its ELF contains 429,600 text bytes, 59,436
data bytes, and 240,624 BSS bytes. The build maps the worktree-dependent DWARF
compilation directory to `workspace/firmware/doom`; both the ELF and flat image
therefore reproduce byte-for-byte in linked worktrees. GCC's random LTO/debug
temporary basenames are normalized only in the textual link map, making all
six firmware evidence artifacts above byte-reproducible. Verilator 5.050
executes the synthesizable RTL at both clock phases; no host ISA emulator or
Doom renderer participates.

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

After the Verilator dependency-path correction, diagnostic evaluator run
`simulation-complete-pathfix-precommit` reproduced the same cycle, retirement,
milestone, frame, and trace values with the simulator identity above. It built
in 20.30 seconds, ran in 251.06 seconds, received all 120 frames with zero
error and zero bad pixels, and preserved all 236 protected files. The run is
deliberately not the final reproducibility record because it captured the
uncommitted Makefile correction; a clean committed run is required below.

Final authoritative run `simulation-complete-orangecrab-final` evaluated the
clean hardware-integrated commit `10772a4eebe168956967a850a39503c7993280f1`.
It built in 18.39 seconds, executed in 251.16 seconds, and passed 120/120 exact
frame comparisons after 744,664,922 cycles and 581,003,386 retired
instructions. The metrics JSON hashes to
`2504611af36ad01803a9493f731c4afdc788f24310aa1430fc5a5784072c15cf`.
`./lab/reproduce` then rebuilt the same commit in a detached linked worktree
and independently returned the same cycles and raw frame-archive SHA-256,
`07f7eecc32a52cfd424c3523184332c49bc9627168a45b67f4a57d3c18f8f833`.
Both runs preserved all 236 protected files and had an empty Git diff.

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

The final post-hardware-integration suite summary is
`.aisl/verification/rtl-suite-orangecrab-final/suite-result.json`, SHA-256
`32c1cceaecb1a857c0ea6bc9b6434fb0e617acba79e352ac28435487284806b8`.
Its process exit was zero, `correct` is true, all 736/736 comparisons passed,
and every frame, cycle, native-execution, and retirement digest above exactly
matches the earlier simulation-complete run. The committed content-addressed
summary is
`workspace/physical/orangecrab/evidence/10772a4/final-simulation-regression.json`.

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

The three Yosys-counted warnings were investigated at the converted-source
lines named by the log. They are reads of `raddr_a_i[5]`, `raddr_b_i[5]`, and
`raddr_c_i[5]` while Yosys initially parses the unused abstract register-file
module at its default `ADDR_WIDTH=5`. The live CV32E40P instance explicitly
passes `ADDR_WIDTH=6`, yielding the selected 32-word integer register file;
hierarchy removes the abstract module and both pre- and post-synthesis `check`
passes report zero problems. A diagnostic `read_verilog -defer` run derived
only the width-6 form and emitted none of the three warnings. The validated
flow was retained because deferred elaboration changes generated module names
and netlist hashes without changing this hardware.

## OrangeCrab target implementation

Commit `ea30efbccaf866e292ee4b2edefebe4125b95bac` adds a genuine physical
target profile for an OrangeCrab r0.2 with an ECP5-85F and 128 MiB DDR3L. The
verified `aisl_soc_cv` CV32E40P remains the Doom computer. A separate minimal
VexRiscv runs only the unmodified LiteDRAM initialization and destructive
memory test from integrated ROM; the board host will not load the workload
until the BIOS-written `init_done=1` and `init_error=0` CSRs are observed.

Two builds from that clean commit used the pinned open Yosys/nextpnr/Trellis
flow, nextpnr seed 1, a 48 MHz constraint, and strict timing. Both returned
zero in 197.45 and 198.87 seconds. Their bitstream, Trellis configuration,
routed JSON netlist, BIOS, and both CSR exports were byte-identical. The final
routed system-clock limit was 51.48 MHz, passing the 48 MHz constraint; the
earlier 40.23 MHz placement estimate was a pre-route failure and is retained
rather than hidden.

| Target resource | Used | Available |
| --- | ---: | ---: |
| ECP5 logic cells (`TRELLIS_COMB`) | 18,114 | 83,640 |
| flip-flops (`TRELLIS_FF`) | 5,785 | 83,640 |
| block RAMs (`DP16KD`) | 40 | 208 |
| 18x18 multipliers | 4 | 156 |

The deployable bitstream SHA-256 is
`c2d2baf32cc7aca7d1f8c099823691e9343bc40e7bb7ba8ebdebfd558252e116`.
The routed-netlist SHA-256 is
`06f119e9488e6ff079293114b77ca531336d36ba3b93c3e6607afc6b38c5ceb0`,
and the normalized CSR map SHA-256 is
`681c00150c7dffa1de15230d83789ad233b2984b2cf0cbb5eb032994a0aa2fac`.
The three Yosys-counted warnings are all unused metadata in the pinned
management VexRiscv; the final flattened netlist contains none of the named
signals and Yosys `check` reports zero problems. The exact warning analysis,
tool revisions, commands, hashes, CSR map, and repeated-build measurements are
under `workspace/physical/orangecrab/evidence/ea30efb/`.

This is implementation and place-and-route evidence, not a physical-run
claim. A read-only access audit found no attached OrangeCrab/compatible DFU
device or serial adapter and no configured authenticated remote FPGA route.
Consequently hardware execution time, physical frame agreement, achieved
on-board frequency, and power remain `null`. The overall physical-verification
gate stays open until a real board executes the same binary and declared
workloads and the captured frames compare exactly.

## Reproduction commands

From the repository root:

```sh
./lab/status
make -C workspace candidate
python3 -m unittest workspace/verification/test_oracle.py
python3 workspace/verification/oracle.py generate
python3 workspace/verification/run_rtl_suite.py \
  .aisl/verification/rtl-suite-reproduced --jobs 4
./lab/evaluate --run-id simulation-complete-orangecrab-final
./lab/reproduce simulation-complete-orangecrab-final
```

`lab/evaluate` performs the authoritative canonical build, execution, exact
oracle comparison, timeout enforcement, and protected-integrity checks.
`lab/reproduce` requires a clean committed revision and evaluates it from an
independent linked worktree. The synthesis recipe forces Yosys's temporary
directory to `/tmp`: Yosys 0.68's bundled ABC cannot parse an evaluator
temporary path containing the repository's spaces. The simulator similarly
stages its exact hashed RTL inputs beside its generated objects under `/tmp`;
its normal test target forces reuse of Verilator's generated dependency file.
