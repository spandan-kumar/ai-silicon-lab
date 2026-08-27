#!/usr/bin/env bash
set -euo pipefail

script_dir="$(cd "$(dirname "$0")" && pwd)"
repository_dir="$(cd "$script_dir/../.." && pwd)"
evidence_dir="$script_dir/evidence"
mkdir -p "$evidence_dir"

{
  date -u +'%Y-%m-%dT%H:%M:%SZ'
  git -C "$repository_dir" rev-parse HEAD
  verilator --version
  yosys -V
  c++ --version | sed -n '1p'
} | tee "$evidence_dir/versions.txt"

make -C "$script_dir" lint 2>&1 | tee "$evidence_dir/verilator-lint.log"
make -C "$script_dir" 2>&1 | tee "$evidence_dir/verilator-build.log"
make -C "$script_dir" test 2>&1 | tee "$evidence_dir/bringup-test.log"
make -C "$script_dir/../rtl" synth 2>&1 | tee "$evidence_dir/yosys-synthesis.log"

{
  shasum -a 256 "$script_dir/build/aisl_sim"
  shasum -a 256 "$script_dir/build/bringup/result-a.json"
  shasum -a 256 "$script_dir/build/bringup/frames-a/frame-000000.rgb"
  shasum -a 256 "$script_dir/../rtl/build/aisl_soc-synth.json"
} | tee "$evidence_dir/SHA256SUMS"
