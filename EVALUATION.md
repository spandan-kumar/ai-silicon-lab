# Evaluation contract

The evaluator is the single entry point at `./lab/evaluate`. Its trusted
implementation is in `ground_truth/evaluator/evaluate.py`; the wrapper and
ground-truth files are protected after setup.

## Current benchmark

The base benchmark is a legally redistributable Freedoom Phase 1 execution:

- engine: the pinned `ozkl/doomgeneric` source revision recorded in
  `ground_truth/reference/SOURCE.json`;
- game data: `freedoom1.wad`, built from the official Freedoom `v0.13.0`
  source tag and distributed under the license included with the asset;
- resolution: 320 x 200;
- pixel format: tightly packed RGB888;
- startup: a fixed 64-frame warmup to remove the engine's initial transition;
- oracle: the next 120 frames, stored as a trusted concatenated RGB archive;
- inputs: the canonical line-oriented schedule in
  `ground_truth/benchmark/input.events`;
- comparison: exact byte equality for every captured frame, with mean absolute
  error and bad-pixel fraction reported for diagnostics.

The warmup is part of the benchmark definition, not a candidate performance
budget. It makes the reference deterministic while leaving architectural and
implementation choices open.

## What the evaluator does

For every run it:

1. verifies the protected-file hashes;
2. records the current Git revision and working-tree state;
3. builds the candidate when a build command is supplied;
4. runs it with the canonical input and output paths;
5. checks process status, required markers, result JSON, frame count, frame
   sizes, and every frame against the trusted oracle;
6. records wall-clock throughput, candidate-reported counters, and nullable
   hardware metrics without inventing unavailable values; and
7. writes metadata, command records, logs, Git information, comparison data,
   candidate output, and metrics under `runs/<run-id>/`.

A result is `pass` only if all required functional checks, frame checks,
candidate exit checks, and ground-truth integrity checks pass. Missing tools,
missing frames, crashes, timeouts, malformed reports, or comparison failures
are failures, never silent skips.

## Self-tests

`--self-test known-good` runs the trusted reference engine through the same
frame protocol. `--self-test broken` runs an intentionally incorrect all-zero
frame producer. These modes validate the lab itself and are labeled in the
recorded result; they are not substitutes for an eventual autonomous design.

## Boundary and limitations

The evaluator prevents the obvious bypasses: it hashes the judge, refuses
normal candidate commands that directly invoke protected evaluator/reference
paths, supplies a copied input schedule, and checks actual frame bytes rather
than candidate-claimed correctness. No evaluator can prove the internal
intent of an arbitrary Turing-complete candidate process on the same host;
the security document therefore requires a container, VM, or separate machine
when the future agent is untrusted. A candidate that deliberately embeds a
host-side game can still imitate an allowed output protocol, so such behavior
must be excluded by experiment policy and stronger isolation when required.

