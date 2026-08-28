# Experiment log

## 2026-08-27: zero-warmup reference determinism

Purpose: test whether cold-start pixels can be used as a supplemental exact
oracle before the benchmark's prescribed 64-frame warmup.

Command:

```sh
PYTHONDONTWRITEBYTECODE=1 python3 workspace/verification/oracle.py generate
```

The first workload captured 96 frames from warmup zero and ran the immutable
native reference twice from separate sanitized homes. The concatenated frame
hashes differed:

- repeat 0: `f5eec7d8f5b8bee7f5567d41e77249db2df3d954800029788bcbf6616579ec28`
- repeat 1: `2804729801745bd25b2482a8a9c8ae8f193cb57ef280d649194ca84a1a132d57`

Result: failed determinism gate. Startup pixels are not a valid exact oracle.
This supports the benchmark contract's statement that the 64-frame warmup
removes the engine's initial transition. The supplemental idle workload now
uses warmup 64. Cold-reset and boot behavior remain covered by architectural
RTL traces rather than by nondeterministic pre-warmup pixels.

## 2026-08-27: first RTL-executed Doom boot and cycle bounds

The first real firmware run used the PicoRV32 SoC, one-wait-state external
memory, the RV32IMC `-Os` image, and complete cycle, native, and RVFI SHA-256
streams. It reached both firmware markers and captured one CPU-rendered
framebuffer, but honestly failed its 500,000,000-cycle bound before firmware
finish. The retained result is `.aisl/rtl-doom-smoke/result.json`:
89,263,687 retired instructions, no trap, one frame, and 279.14 seconds wall
time.

After changing only measured implementation parameters (zero-wait SRAM,
32-bit RV32IM code, GCC `-O3`, and sampled cycle checkpoints while retaining a
complete native/RVFI digest), a cold one-frame run completed successfully:

- boot cycle: 1,291,946;
- Doom-start cycle: 95,647,848;
- first capture cycle: 95,650,559;
- finish cycle: 389,282,968;
- retired instructions: 99,704,543;
- simulated frames/game tics: 41/2;
- wall time: 118.35 seconds; and
- trap/failure: false/false.

The exact result is `.aisl/rtl-doom-fw-im-one/result.json`. The pre-warmup
frame is diagnostic only: its hash differs across compiler layouts, consistent
with the separately measured cold-reference nondeterminism. No pixel claim is
made from it.

A subsequent 64-warmup run at a 700,000,000-cycle bound failed before capture
with 177,665,766 retired instructions and no trap. This disproved the naive
estimate based on the loading frames in the cold run and established that
post-start game rendering must be included in performance qualification.

## 2026-08-27: exact protected canonical frame stream from RTL

The optimized PicoRV32/RV32IM implementation completed the full protected
benchmark protocol: 64 warmup frames followed by 120 captured 320x200 RGB888
frames. This was a cycle-accurate Verilator execution of synthesizable RTL,
not an ISA emulator or native engine.

- cycles: `2,442,338,489`;
- retired instructions: `614,901,847`;
- boot / Doom-start / first-capture cycles: `1,291,946` / `95,647,964` /
  `732,598,850`;
- simulated frames / game tics / captures: `184` / `145` / `120`;
- trap/failure: `false` / `false`;
- firmware SHA-256: `d7e625584daf2ad2574e9631bd6b623e93aa82d21e9b943cb64e3fc2757757c1`;
- WAD SHA-256: `7e3d5dbc1b11ed55c2c8aa44d4843ba1bb64780b4066f96898158d99b93fdf0f`;
- canonical input SHA-256: `5bf11852ccc26b0b3795e63ab8f568e1fa9c22ec9484e59baca63291e2087975`;
- RTL frame archive SHA-256: `07f7eecc32a52cfd424c3523184332c49bc9627168a45b67f4a57d3c18f8f833`;
- protected oracle SHA-256: `07f7eecc32a52cfd424c3523184332c49bc9627168a45b67f4a57d3c18f8f833`;
- byte comparator exit: `0`; and
- measured wall interval: approximately 400 seconds (run-directory birth at
  05:45:06 and result creation at 05:51:46 local time).

The retained simulator report and frames are under `.aisl/pico-canonical/`.
The simulator's own success flag was not used as the pixel oracle: the 120
files were independently concatenated in lexical order and compared byte for
byte with the protected archive. The matching 23,040,000-byte digest and
`cmp` exit zero are the functional evidence.

## 2026-08-27: CV32E40P performance hypothesis and exact first frame

An isolated evaluation compared pinned OpenHW CV32E40P `cv32e40p_v1.8.3`
(`360d272898d81806be3377193870dbf83a3ea79f`) with PicoRV32 using an identical
19,313,265-instruction RV32IM benchmark. A deterministic single-port OBI
bridge reduced the architectural cycle count from 67,535,082 to 23,504,559
and reduced that microbenchmark's wall time from 12.08 to 8.51 seconds. This
justified a full SoC integration, but the Doom measurement was retained as the
real decision gate.

The first CV32E40P Doom run used the same RV32IM `-O3` firmware and produced
the exact first post-warmup frame hash
`dde1f01c2ca5cbcaff036b9ac8a76b3a4267ecb9aed711147bc7501121e6ff12`.
It took 290,293,323 cycles, retired 185,861,253 instructions, and measured
128.31 seconds. Merely changing cores therefore did not provide enough margin
for the official 300-second full run.

RV32IMC reduced that run to 286,427,940 cycles but measured 129.21 seconds.
GCC link-time optimization was materially better: the exact same frame was
produced after 264,265,694 cycles and 179,485,665 retired instructions in
114.16 seconds. These are measured facts; full-workload timeout compliance
remains pending until the optimized complete run is executed.

## 2026-08-27: final CV32E40P protected run

The complete CV32E40P/RV32IMC/LTO run resolved the preceding performance
gate. The synthesizable SoC booted from reset, started Doom, rendered 64
warmup frames, captured the next 120 frames, and finished without a trap or
failure. The retained artifact is `.aisl/canonical-simulation-complete/`.

- cycles / retired instructions: `744664922` / `581003386`;
- boot / Doom-start / first-capture / finish cycles: `429298` / `31117064` /
  `228353358` / `744664922`;
- simulated frames / game tics / captures: `184` / `145` / `120`;
- measured simulator wall interval: `259.33` seconds;
- firmware / simulator / RTL-source SHA-256: `f92ddb3cfe23206b4b5c1a78e8e64730ff932061f6607db3b278f6da5a1239df` /
  `b876dda114914251fc7f850d9447450004829bdbc1c859c9524e77b966ed5945` /
  `fc04549e092234587ef821706847eda1b2e3022989091d7a12f0ad1823160665`;
- cycle / native / retirement trace SHA-256: `903c475602d3cff471e9569464ba94f738ee1733e6d2207c36ce09b3d239f759` /
  `fda8dc56dc6fa18118205123a005addbbd196ac8abb8da8557db3ee956349a40` /
  `77737111ad70b1a30e3f8afadc24d5954777ae839d3a6843381ffa87042025bc`;
- concatenated RTL frame bytes: `23040000`;
- RTL and protected-oracle concatenated SHA-256:
  `07f7eecc32a52cfd424c3523184332c49bc9627168a45b67f4a57d3c18f8f833`;
- independent byte comparator: exit zero; and
- result report SHA-256:
  `72cd4962350674870716e3bda0d56acd04913f0f46119754f3f021a23c8cfc9a`.

The harness first refused a protected input path, as designed. The successful
run used a generated copy whose hash matched the canonical input
`5bf11852ccc26b0b3795e63ab8f568e1fa9c22ec9484e59baca63291e2087975`.
The simulator did not read the oracle; the comparison was performed after the
process exited.

## 2026-08-27: strengthened workloads and renderer diagnosis

Four supplemental workloads cover idle E1M1, movement/combat E1M1, alternate
E1M2 at skill 3, and overlapping-input E1M3 at skill 4. The immutable native
reference was run twice for every workload in distinct sanitized homes before
an archive was accepted. All workloads retain the measured-necessary 64-frame
warmup. The pinned archive sizes total 141,312,000 bytes.

The first RTL suite was exact on canonical, idle, movement, and overlap, but
alternate E1M2 had one RGB pixel (three bytes) wrong in frame 84. Indexed
buffers were exact through frame 83. Instrumentation localized the difference
to a masked-sprite `R_DrawColumn` sample: vanilla's 128-byte column wrap
selected offset 344 from a 238-byte cached patch lump. The byte consequently
depended on unrelated allocator contents. Signed-character changes, compiler
optimization levels, link-time optimization, and whole-WAD placement were
tested and falsified as general explanations.

A first fix rejected every wrapped read beyond the current post. That made the
alternate workload exact but changed valid vanilla reads still inside the
owning patch allocation, causing 9 wrong bytes in overlap and 33 in movement.
The final, narrower policy records the cached sprite-patch allocation, keeps
all wrapped reads inside it, and selects palette index zero only when the
sample would leave it. Ordinary wall columns and masked mid-wall columns are
unchanged. The policy is implemented in `r_draw.c`, `r_draw.h`, and
`r_things.c`; `SOURCE.json` declares those modifications. A byte-for-byte
vendor audit against upstream tree
`413539bdaa1521af167d9b34e9db0cd193367624` found no undeclared engine
changes.

## 2026-08-27: final strengthened RTL suite

The four workloads were then rerun from the final firmware. The suite process
returned zero and compared all 736 expected 320x200 RGB888 frames with no
missing, extra, or mismatched files. Evidence is retained under
`.aisl/verification/rtl-suite-simulation-complete/`; its summary SHA-256 is
`9f6d7e7e276fd00341bb653e5669a33045501f625c7fa7c10051c123f9718006`.

| Workload | Frames | Cycles | Retired | Frame-stream SHA-256 |
| --- | ---: | ---: | ---: | --- |
| idle E1M1 | 96 | 640655706 | 500135333 | `46864642902fc1986f38180a56cda8a71758bfbb60a981b8d0542dd4a4db952d` |
| movement/combat E1M1 | 256 | 1236203544 | 969749015 | `7d347b47f968be6865f70c37d0b914dc6cf5ca31b19bda6645e2d7491914e311` |
| alternate E1M2 skill 3 | 192 | 983382917 | 770238900 | `c5dc4c3eac59b70b8356d3fc71246f17b7a491ca829f9d8c632448cf1f7b15c8` |
| overlap E1M3 skill 4 | 192 | 876013015 | 697938392 | `6ecd45950ec68ab5545ef6f676e9516e5b61ddea472ac3c0a53deeea7747e7b0` |

The simulator, firmware, and WAD identities in every result were respectively
`b876dda114914251fc7f850d9447450004829bdbc1c859c9524e77b966ed5945`,
`f92ddb3cfe23206b4b5c1a78e8e64730ff932061f6607db3b278f6da5a1239df`,
and `7e3d5dbc1b11ed55c2c8aa44d4843ba1bb64780b4066f96898158d99b93fdf0f`.
Complete cycle/native/retirement digests and exact reference-archive hashes
are tabulated in `EVIDENCE.md`.

## 2026-08-27: final synthesis and local qualification

A clean `make -C workspace/rtl_cv clean synth` returned zero in 22.41 seconds
using sv2v 0.0.13 and Yosys 0.68+post. Yosys `check` reported zero problems.
The target-neutral mapped design has 40,209 generic cells, including 2,691
sequential cells, 4,629 muxes, and no inferred internal memories; the 64 MiB
SRAM is intentionally outside the SoC synthesis boundary. The JSON and
Verilog netlist SHA-256 values are
`1a24b00957d4705c1d232b7d705e56dc88f548bbf7cfd5ada0dcb1a271d4150e`
and
`16b99053f70d74147f8da8d79a09d707d6ed9d7f9568b7ec11b34938963cb542`.

The three unique Yosys warnings are out-of-range high address bits in an
unused generic register-file branch; the selected 32-register parameterized
implementation synthesizes normally. Verilator 5.050 lint returned zero, two
repeated architectural/MMIO/frame-capture tests returned identical hashes,
and all five oracle-comparator unit tests passed.

## 2026-08-27: official clean-build path failure

The first committed evaluator attempt, run ID `simulation-complete-final`,
stopped during synthesis and correctly recorded a failure without starting
the candidate. Firmware and simulator compilation had succeeded. Yosys invoked
its bundled ABC beneath the evaluator-provided temporary directory
`runs/simulation-complete-final/tmp/`; ABC split the absolute repository path
at the space in `AI Silicon Lab` and could not open its script/output files.
Protected integrity remained true before and after, and Git remained clean at
revision `353c5b3d54ee99415b6ee5639c62a4b1b1a2e2a0`.

This was a reproducible tool-path defect, not an RTL failure. The synthesis
recipe now sets `TMPDIR=/tmp` only for Yosys. Yosys continues to create its own
unique temporary subdirectory, while ABC receives a path without spaces. The
failed run and its complete logs remain under `runs/simulation-complete-final/`.
A clean post-fix synthesis returned zero, reproduced the JSON/Verilog netlist
hashes above exactly, and produced local log SHA-256
`1c40deb58a0a9e522fe45e6e2d368342b059bfbb362eccee615e131630f9fb3a`.

## 2026-08-28: official pass, reproduction, and ELF path audit

Committed revision `5abe7354b076a48c11c3702ccefb621153e01427`
passed official run `simulation-complete-final-2`. The clean build took 48.50
seconds and the protected run took 258.11 seconds. It received all 120 frames
with zero mean error and zero bad pixels; integrity checked all 236 protected
files before and after, and Git stayed clean at the same revision.

`lab/reproduce simulation-complete-final-2` created a detached linked worktree
and independently produced passing run `20260827T141858Z-6ca595bc`. Its clean
build took 47.52 seconds and run took 249.91 seconds. The reports agreed on
744,664,922 cycles, 581,003,386 retired instructions, every milestone, every
firmware counter, all 120 frame files, and all cycle/native/retirement trace
digests. Direct concatenation in both runs gave protected-oracle hash
`07f7eecc32a52cfd424c3523184332c49bc9627168a45b67f4a57d3c18f8f833`;
both byte comparisons returned zero. The simulator, flat firmware, converted
RTL, and JSON/Verilog synthesis netlists were also byte-identical.

The audit nevertheless found that `doom.elf` differed while its loadable flat
image remained identical. Section inspection localized the only size shift to
DWARF string tables: GCC recorded the absolute compilation directory, which is
longer inside `.aisl/reproduce/`. The firmware flags now use
`-fdebug-prefix-map` to canonicalize that debug-only directory without changing
`__FILE__`, code, data, or the flat image. The resulting ELF SHA-256 is
`22e430bcdd826929155c2617a965940b94a0d68ff54d1b8b0ebcbd7483b84214`;
the flat image remains
`f92ddb3cfe23206b4b5c1a78e8e64730ff932061f6607db3b278f6da5a1239df`.
An additional two-worktree check found random GCC LTO/debug temporary basenames
in the otherwise identical linker maps. The build now replaces only those
basenames with stable labels after link; the normalized maps are byte-identical
while retaining every address, size, section, symbol, and stable object name.
The normalized map and five-entry checksum manifest hash to
`e72f9f055814b198953b780127fd4841fec8a02604b4c671bd62446b37ddf35a` and
`f883355ecb3b4418f5c5e031e0c8c2a6d8d008ddf6c4dae7bc62516b9bdafcda`.
Official run `simulation-complete-final-3` passed the protected workload at
revision `f1fc9c907e1934ea5bf07a134c0bb7209fd03512`, but its evaluator `TMPDIR`
contained spaces. The first map expression left the absolute prefix before its
stable temporary label. The expression now treats the complete slash-delimited
prefix as opaque, including spaces; normalizing the retained official,
detached, and an additional spaced-`TMPDIR` map then produced the same
`e72f...f35a` digest. No executable artifact or RTL result changed.

## 2026-08-28: independent review and Verilator dependency-path correction

An independent evaluation of revision `4da0987eb8658ea5ebc755861099b69d2fe8adf6`
invalidated the claimed reproducibility milestone. Run
`review-codex-simulation-complete` returned build exit 2 before simulation:
Verilator's generated `Vaisl_soc__ver.d` named source prerequisites such as
`../rtl_cv/aisl_soc_cv.sv`, but GNU Make later evaluated that file from the
space-free `/tmp/aisl-cv-verilator-*` object directory. The protected judge and
oracle were not changed.

The defect is state-dependent. A newly empty object directory succeeds because
the dependency file does not exist when the first generated Make process is
parsed. Immediately forcing the same build a second time reproduced the exact
`No rule to make target '../rtl_cv/aisl_soc_cv.sv'` failure and exit 2. This
explains why the earlier local and official first builds passed while a later
review using the cached object directory failed.

The simulator recipe now copies every RTL input covered by `SOURCE_ID` into an
identically structured directory beneath the object directory and passes those
space-free absolute paths to Verilator. Its `test` target forces a second build
before the architectural bring-up checks. A clean first build, an immediate
forced rebuild, Verilator lint, and the repeated RV32IM/MMIO/RGB test all
returned zero. The new simulator SHA-256 is
`1e0ae162d59670a25aa5bb90cc942a94a5bd1470d2b57777ba744495d60a028c`;
the RTL aggregate remains
`fc04549e092234587ef821706847eda1b2e3022989091d7a12f0ad1823160665`.

The three Yosys warnings were also traced to the unused abstract
`cv32e40p_register_file` parsed at its default `ADDR_WIDTH=5`, where the source
names read-address bit 5. The instantiated core explicitly derives the module
at `ADDR_WIDTH=6`, hierarchy removes the abstract form, and both Yosys `check`
passes report zero problems. Deferred elaboration removed all three warnings in
a diagnostic run; it was not adopted because it needlessly changed netlist
module identities and hashes. The existing flow again produced 40,209 cells
and the exact prior JSON/Verilog netlist hashes.

All five oracle unit tests passed. The four path-corrected RTL workloads then
returned zero and independently compared all 736 320x200 RGB888 frames with no
missing, extra, wrong-sized, or mismatched files. Their cycle, retirement,
frame, cycle-trace, native-trace, and retirement-trace values exactly reproduced
the preceding suite. The retained summary is
`.aisl/verification/rtl-suite-pathfix-20260828/suite-result.json`, SHA-256
`152d13a1771552bc3e397ad1afcd60a5c5a65709e4e160c3ee3adb20ef5b7724`.

Finally, dirty-tree diagnostic run `simulation-complete-pathfix-precommit`
passed the authoritative evaluator. Its build and run returned zero in 20.30
and 251.06 seconds; the RTL reported 744,664,922 cycles and 581,003,386 retired
instructions, and all 120 frames matched with zero error and zero bad pixels.
Integrity verified all 236 protected files before and after. The evaluator
correctly marked Git reproducibility false because this correction was not yet
committed; only a subsequent clean committed run and detached reproduction can
close that gate.
