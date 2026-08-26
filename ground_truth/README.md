# Immutable ground truth

This directory is a read-only measurement boundary. It contains the pinned
reference engine, legally redistributable Freedoom data, deterministic input,
frame oracle, benchmark definition, evaluator support files, and a SHA-256
trust manifest.

The normal experiment agent may read and execute these files but must not edit
them. On the setup host, `./lab/protect --apply` applies the macOS `uchg`
filesystem flag recursively and removes write permissions. The evaluator also
checks the manifest before and after every candidate process.

`reference_frames.bin` is a concatenation of 120 tightly packed 320x200 RGB888
frames. `benchmark.json` defines the offsets and comparison rules. The
representative RGB files are human-inspectable samples; they are not a second
source of truth.

