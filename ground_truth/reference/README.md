# Trusted reference

The vendored source is pinned in `SOURCE.json`. `Makefile` builds the
headless adapter into `.aisl/reference-build/` on a host where the prebuilt
binary is not usable. The checked-in binary is a convenience for the setup
host and is not used as an architectural requirement.

