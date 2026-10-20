"""Retain actual command status/streams without replacing earlier evidence."""
import json
from pathlib import Path
import subprocess
import sys
import time

HERE = Path(__file__).resolve().parent
label, *argv = sys.argv[1:]
assert not (HERE / (label + '.command.json')).exists()
start = time.monotonic()
process = subprocess.run(argv, capture_output=True, text=True)
for suffix, value in (('stdout.log', process.stdout), ('stderr.log', process.stderr)):
    with (HERE / (label + '.' + suffix)).open('x') as handle:
        handle.write(value)
with (HERE / (label + '.command.json')).open('x') as handle:
    json.dump({'argv': argv, 'exit_code': process.returncode,
               'wall_seconds': time.monotonic() - start}, handle, indent=2)
print(process.stdout, end='')
print(process.stderr, end='', file=sys.stderr)
raise SystemExit(process.returncode)
