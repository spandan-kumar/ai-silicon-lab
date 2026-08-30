# AES-256-GCM experiment workspace

This workspace implements the frozen `aes-256-gcm-64-v1` profile documented in
`experiments/aes-256-gcm/PROFILE.md`.

The implementation is intentionally separate from the protected Doom
evaluator. `make check` is the AES experiment's local entry point; it builds
the independent reference/vector layer, software baseline, RTL candidates,
and evidence reports as those layers are added.
