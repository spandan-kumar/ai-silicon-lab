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
```

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

