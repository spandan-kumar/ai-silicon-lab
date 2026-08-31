# Laboratory guide

## Commands

```sh
./lab/status                         # core health and optional capabilities
./lab/status --json                  # machine-readable health report
./lab/evaluate                       # evaluate workspace/candidate.json
./lab/evaluate --self-test known-good
./lab/evaluate --self-test broken
./lab/reproduce <run-id>             # reproduce a clean, committed run
./lab/reference --output DIR -- ...  # run the trusted software reference
./tools/experiment list               # list versioned experiment specifications
./tools/experiment check               # validate specifications and run examples
./tools/experiment show <experiment>  # print one experiment manifest

./harness/aisl experiments            # experiments and their harness wiring
./harness/aisl env <experiment>       # toolchain the experiment declares it needs
./harness/aisl verify <experiment>    # build, reference, execute, compare
./harness/aisl gate <experiment>      # gate criteria joined to check results
./harness/aisl record <experiment>    # emit and validate a provenance run record
./harness/aisl loop step <experiment> # one iteration, stopping at the phase boundary
```

`./harness/aisl` is the experiment-agnostic layer described in
[`harness/README.md`](harness/README.md). It never writes inside `lab/` or
`ground_truth/`, and it does not replace `./lab/evaluate`, which remains the
canonical Doom judge.

`./lab/evaluate` fails clearly when `workspace/candidate.json` is absent. That
is intentional: the lab does not supply an architecture or pretend that an
empty workspace is a candidate.

## Capability inventory

The current host provides:

| Capability | Path | Notes |
| --- | --- | --- |
| C/C++ compilation | `clang`, `gcc`, `make` | Native Apple-silicon toolchain |
| RTL simulation | `verilator` | Installed and checked by the status smoke test |
| RTL synthesis | `yosys` | Installed and checked by the status smoke test |
| General scripting | Python 3, Node.js | The evaluator uses Python standard library only |
| Container/VM support | Docker, Apple Hypervisor | Available for optional isolation |
| FPGA/ASIC/physical board | unavailable | No supported board or open ASIC flow detected |

The exact discovery result is recorded in [`docs/ENVIRONMENT.md`](docs/ENVIRONMENT.md)
and in the trusted metadata file under `ground_truth/`.

## Neutral candidate interface

Create `workspace/candidate.json` with this shape:

```json
{
  "schema_version": 1,
  "name": "my-candidate",
  "build": "make -C workspace/my-design",
  "run": "./workspace/my-design/run"
}
```

`build` is optional; `run` is required. A command may be a shell command
string or an argv array. It is executed from the repository root with a
minimal deterministic environment. The evaluator supplies:

| Variable | Meaning |
| --- | --- |
| `AISL_INPUT_FILE` | Read-only copy of the canonical deterministic input schedule |
| `AISL_FRAME_DIR` | Directory in which the candidate writes captured frames |
| `AISL_RESULT_FILE` | JSON report path |
| `AISL_FRAME_WIDTH` / `AISL_FRAME_HEIGHT` | Required framebuffer dimensions |
| `AISL_FRAME_FORMAT` | Currently `rgb888`, tightly packed RGB bytes |
| `AISL_FRAME_COUNT` | Number of frames required after warmup |
| `AISL_FRAME_WARMUP` | Reference startup frames not included in the oracle |
| `AISL_RUN_ID` | Directory-safe experiment identifier |

The candidate must write `frame-000000.rgb` through the required final frame,
print `AISL_BOOTED` and `AISL_DOOM_STARTED`, and write a JSON report containing
boolean `booted` and `doom_started` fields. Optional `cycles`, `tics`, `fps`,
and `hardware` fields are recorded as candidate-reported data; they do not
become trusted merely by being present.

No interface element names a processor or ISA. A candidate can be a software
model, RTL simulator, FPGA runner, emulator, or another computer design.

Examples in this guide are illustrative context, not a required architecture or
workflow. The agent owns its process and may replace the initial layout,
commands, tools, and experiment strategy whenever evidence supports doing so;
the explicit evaluation, security, licensing, and integrity requirements remain
the binding contract.

## Agent freedom, research, and evidence

The installed capability list is a starting point, not a boundary. The future
agent may install any simulator, compiler, synthesis or place-and-route flow,
debugger, profiler, emulator, library, or other tool needed for an experiment.
It may use local packages, containers, virtual machines, or other practical
installation methods, while recording important versions and setup choices.

Internet research is explicitly encouraged whenever the work needs it. Search
for primary documentation, source code, standards, papers, DOOM internals, and
architecture or implementation techniques instead of treating uncertain memory
as fact. Record useful URLs, citations, and repository revisions with the
experiment so another session can follow the same evidence trail.

The agent may design its own process and, when supported by its runtime, create
reusable subagents, skills, prompts, harnesses, or other delegation tools. Such
delegation is optional. Every delegated result still requires independent
verification against the experiment's success criteria.

The lab's testing standard is empirical: no test or conclusion is accepted on
the basis of an assumption, a screenshot, a self-reported metric, or a claim
that something "should" work. Execute the relevant build and test, inspect its
real artifacts and exit status, compare outputs against explicit vectors or
trusted ground truth, and repeat measurements when determinism matters. Label
inferences and hypotheses as such. If a result cannot be measured, report it as
unknown or unavailable; never silently skip a check or invent a metric.

## Experiment program

The top-level [`experiments/`](experiments/) directory is the versioned
catalogue for independent hardware experiments. Each experiment freezes its
objective, design freedom, oracle/vector policy, workloads, metrics, phase
gates, research references, and provenance requirements. The current entries
are:

- `doom-rv32imc`: a verified end-to-end Doom computer baseline and future
  architecture exploration;
- `aes-256-gcm`: a not-yet-implemented accelerator study with a standards-based
  correctness profile, edge-case matrix, security-claim boundaries, and
  target-dependent optimization plan.

The protected `./lab/evaluate` command remains the canonical Doom evaluator.
It is intentionally not a universal evaluator for unrelated algorithms. A new
experiment must provide its own candidate adapter, oracle or vectors, and
metrics while reusing the common run-record and evidence conventions.

For model/agent comparisons, keep agent provenance separate from hardware
execution provenance. A display alias such as `Sol`, a reported token estimate,
and a wall-time estimate are useful only when their identity and measurement
source are explicit. See [`experiments/schema/README.md`](experiments/schema/README.md).
