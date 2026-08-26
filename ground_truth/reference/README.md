# Trusted reference

The vendored source is pinned in `SOURCE.json`. `./lab/reference --build`
builds the headless adapter into the mutable `.aisl/reference-build/` cache on
a host where the prebuilt binary is not usable. The Makefile's direct-build
defaults use a space-free temporary path because the repository may itself
live under a path containing spaces. The checked-in binary is a convenience
for the setup host and is not used as an architectural requirement.
