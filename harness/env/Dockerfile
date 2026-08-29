# Reproducible EDA environment for AI Silicon Lab.
#
# The measured results in this repository were produced with the host toolchain
# recorded in each run record. This image exists so another machine can
# reproduce them, and so an untrusted candidate can be run without host access,
# which SECURITY.md requires and host execution does not provide.
#
#   docker build -t aisl-harness -f harness/env/Dockerfile .
#   docker run --rm -v "$PWD:/lab" -w /lab aisl-harness ./harness/aisl verify aes-256-gcm

FROM debian:trixie-slim

ARG DEBIAN_FRONTEND=noninteractive

# Pinned by name here and by exact version in every run record. Debian trixie
# supplies Verilator 5.x and Yosys; the run record is the authority on which
# versions produced a given result.
RUN apt-get update && apt-get install --no-install-recommends -y \
        build-essential \
        ca-certificates \
        git \
        make \
        perl \
        python3 \
        verilator \
        yosys \
    && rm -rf /var/lib/apt/lists/*

# The harness writes only to the repository bind mount and never to lab/ or
# ground_truth/, which it asserts in code.
WORKDIR /lab

RUN printf '%s\n' \
    'Verilator:' "$(verilator --version 2>&1 | head -1)" \
    'Yosys:' "$(yosys -V 2>&1 | head -1)" \
    'Python:' "$(python3 --version)" \
    > /etc/aisl-toolchain-versions

CMD ["./harness/aisl", "experiments"]
