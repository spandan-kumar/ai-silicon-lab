# Supplemental deterministic verification

The protected evaluator remains the mandatory canonical benchmark. This
directory adds independent exact comparisons for trajectories not covered by
that single benchmark. It never changes protected ground truth.

`oracle.py generate` executes the immutable native reference twice from fresh,
sanitized temporary homes. Generation fails unless both complete frame streams
are byte-identical. Generated archives, logs, and metadata live below
`.aisl/verification/oracles/`; metadata records input, WAD, reference binary,
engine revision, archive, and per-frame SHA-256 values.
`expected-oracles.json` pins the independently reproduced archive hashes and
reference identity; generation and comparison fail if those values drift.

The RTL simulator receives only its firmware, WAD, selected input schedule,
and output paths. Oracle comparison occurs after the simulator exits; the
simulator must not read these oracle archives or invoke the native engine.

Run the comparator unit tests with:

```sh
python3 -m unittest workspace/verification/test_oracle.py
```

Generate all supplemental reference oracles with:

```sh
python3 workspace/verification/oracle.py generate
```

Compare one captured frame directory with:

```sh
python3 workspace/verification/oracle.py compare WORKLOAD_ID FRAME_DIR
```

Run all workloads on the cycle-accurate RTL simulator and retain commands,
logs, reports, trace hashes, and comparisons below an empty output directory:

```sh
python3 workspace/verification/run_rtl_suite.py .aisl/verification/rtl-suite
```

Independent workloads may run concurrently with `--jobs N`. Cycle counts and
hashes remain deterministic, but concurrent wall-clock measurements are not
performance benchmarks.
