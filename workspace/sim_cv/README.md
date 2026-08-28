# CV32E40P cycle-accurate simulator

This harness drives the synthesizable `workspace/rtl_cv` SoC on every low and
high clock phase using Verilator. It provides deterministic, synchronous
dual-port 64 MiB external memory with one-cycle OBI responses, loads only the
candidate firmware/WAD/input records, and captures the
CPU-written framebuffer in the benchmark's RGB888 wire format. It contains no
Doom engine, renderer, reference frames, or oracle comparison.

Build, lint, and run the two-repeat RV32IM/MMIO/frame-capture test:

```sh
make -C workspace/sim_cv lint
make -C workspace/sim_cv test
```

Generated Verilator objects and an exact copy of the hashed RTL inputs are
kept together under a space-free `/tmp/aisl-cv-verilator-*` directory. This is
required because Verilator's reused dependency file is evaluated from its
object directory, not from this source directory. The `test` target forces a
second build so stale or incorrectly rooted generated dependencies cannot be
masked by a successful first build.

For a Doom run, supply the firmware and WAD explicitly; the remaining paths
and video counts can also arrive through the evaluator's `AISL_*` environment
variables:

```sh
workspace/sim_cv/build/aisl_sim_cv \
  --firmware workspace/firmware/doom/build-candidate/doom.bin \
  --wad workspace/assets/freedoom1.wad \
  --inputs workspace/verification/inputs/idle.events \
  --frames-dir .aisl/example/frames \
  --result .aisl/example/result.json \
  --frame-count 96 --warmup 64 --skill 1 --episode 1 --map 1 \
  --execution-trace-stride 4096
```

The report records cycle/milestone/retirement counts, firmware/WAD/input/frame
hashes, UART, bounded retirement samples, a periodic full-state digest, and a
sampled execution digest. CV32E40P's standard top does not expose formal RVFI;
the compatibility-named `rvfi_*` ports are explicitly a simulation-only
decode/`minstret` diagnostic projection. They are never represented as a
formal RVFI proof. Defining `SYNTHESIS` removes those hierarchical diagnostics
from the hardware netlist.

`--execution-trace-stride 1` hashes every diagnostic retirement. Larger
strides retain a deterministic, reproducible sampled trace with substantially
less host overhead. The report always records the selected stride and sample
counts. `--cycle-trace-stride` independently controls full-state checkpoints.

The host paths under `build/` and `.aisl/` are generated evidence and are not
trusted inputs. The harness refuses outputs or input assets located beneath
the protected `lab/` and `ground_truth/` roots; oracle comparison is performed
after RTL execution by the protected evaluator or the supplemental verifier.
