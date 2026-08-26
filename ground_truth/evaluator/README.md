# Trusted evaluator implementation

`evaluate.py` is called by `./lab/evaluate`. It uses only the Python standard
library so the judgment path does not depend on optional packages. Changes to
this directory invalidate the trusted-file manifest and, on this host, are
blocked by filesystem immutability.

