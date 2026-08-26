# Experiment records

The lab deliberately uses inspectable files instead of a database. A run has
this shape:

```text
runs/<run-id>/
    metadata.json
    metrics.json
    commands.json
    git-info.json
    stdout.log
    stderr.log
    build.stdout.log
    build.stderr.log
    artifacts/
        candidate-manifest.json
        candidate-report.json       # when produced
        frame-comparison.json
    frames/
        frame-000000.rgb ...
    waveforms/                       # available for candidate-generated traces
```

`metadata.json` identifies the experiment and benchmark. `commands.json`
contains timestamps, the command form, exit status, timeout state, and elapsed
time. `git-info.json` records the revision, branch, status, and a hash of the
captured diff. `metrics.json` is the machine-readable result returned by the
evaluator.

The evaluator records failed experiments too. A failed build or run still
gets logs and source-state information, making it possible to understand what
happened rather than only preserving successes.

For additional command-level observability, wrap an exploratory command with
the future `workspace` tooling or preserve the agent session transcript. The
lab cannot infer commands that never enter its process or are run outside the
workspace.

