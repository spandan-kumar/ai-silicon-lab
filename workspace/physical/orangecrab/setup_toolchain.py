#!/usr/bin/env python3
"""Install or audit the pinned open-source OrangeCrab build toolchain."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[3]
LOCK_PATH = Path(__file__).resolve().with_name("toolchain.lock.json")
TOOLCHAIN_ROOT = REPOSITORY / ".aisl/toolchains/orangecrab"
SOURCE_ROOT = TOOLCHAIN_ROOT / "src"
VENV = TOOLCHAIN_ROOT / "venv"
INSTALL = TOOLCHAIN_ROOT / "install"
BUILD_NEXTPNR = TOOLCHAIN_ROOT / "build-nextpnr"

REPOSITORIES = {
    "migen": "https://github.com/m-labs/migen.git",
    "litex": "https://github.com/enjoy-digital/litex.git",
    "litedram": "https://github.com/enjoy-digital/litedram.git",
    "litex-boards": "https://github.com/litex-hub/litex-boards.git",
    "pythondata-cpu-vexriscv": "https://github.com/litex-hub/pythondata-cpu-vexriscv.git",
    "pythondata-software-picolibc": "https://github.com/litex-hub/pythondata-software-picolibc.git",
    "pythondata-software-compiler_rt": "https://github.com/litex-hub/pythondata-software-compiler_rt.git",
    "nextpnr": "https://github.com/YosysHQ/nextpnr.git",
}

PYTHON_PACKAGES = [
    "setuptools==84.0.0",
    "wheel==0.48.0",
    "PyYAML==6.0.3",
    "requests==2.34.2",
    "packaging==26.3",
    "pyserial==3.5",
    "meson==1.12.0",
]

EDITABLE_PACKAGES = [
    "migen",
    "litex",
    "litedram",
    "litex-boards",
    "pythondata-cpu-vexriscv",
    "pythondata-software-picolibc",
    "pythondata-software-compiler_rt",
]


def run(arguments: list[str | os.PathLike[str]], **kwargs):
    command = [str(argument) for argument in arguments]
    print("+", " ".join(command), flush=True)
    return subprocess.run(command, check=True, **kwargs)


def output(arguments: list[str | os.PathLike[str]]) -> str:
    return subprocess.check_output([str(argument) for argument in arguments], text=True).strip()


def require(command: str) -> str:
    resolved = shutil.which(command)
    if resolved is None:
        raise RuntimeError(f"required command is unavailable: {command}")
    return resolved


def revision(path: Path) -> str:
    return output(["git", "-C", path, "rev-parse", "HEAD"])


def install_sources(lock: dict) -> None:
    SOURCE_ROOT.mkdir(parents=True, exist_ok=True)
    for name, url in REPOSITORIES.items():
        destination = SOURCE_ROOT / name
        wanted = lock["repositories"][name]
        created = False
        if not (destination / ".git").is_dir():
            run(["git", "clone", "--filter=blob:none", "--no-checkout", url, destination])
            created = True
        if not created:
            dirty = output(["git", "-C", destination, "status", "--porcelain"])
            if dirty:
                raise RuntimeError(f"generated source checkout is dirty; refusing to overwrite: {destination}")
        if created or revision(destination) != wanted:
            run(["git", "-C", destination, "fetch", "--depth=1", "origin", wanted])
            run(["git", "-C", destination, "checkout", "--detach", wanted])

    picolibc = SOURCE_ROOT / "pythondata-software-picolibc"
    run(["git", "-C", picolibc, "submodule", "update", "--init", "--depth=1"])


def trellis_prefix() -> str:
    configured = os.environ.get("TRELLIS_INSTALL_PREFIX")
    if configured:
        return configured
    brew = shutil.which("brew")
    if brew:
        return output([brew, "--prefix", "prjtrellis"])
    return "/usr/local"


def install_python() -> None:
    if not (VENV / "bin/python").is_file():
        run([sys.executable, "-m", "venv", VENV])
    python = VENV / "bin/python"
    run([python, "-m", "pip", "install", *PYTHON_PACKAGES])
    for name in EDITABLE_PACKAGES:
        run([python, "-m", "pip", "install", "--no-deps", "-e", SOURCE_ROOT / name])


def install_nextpnr() -> None:
    prefix = trellis_prefix()
    run(
        [
            "cmake",
            "-S",
            SOURCE_ROOT / "nextpnr",
            "-B",
            BUILD_NEXTPNR,
            "-DARCH=ecp5",
            "-DBUILD_GUI=OFF",
            "-DBUILD_TESTS=OFF",
            "-DBUILD_PYTHON=ON",
            f"-DTRELLIS_INSTALL_PREFIX={prefix}",
            f"-DCMAKE_INSTALL_PREFIX={INSTALL}",
        ]
    )
    run(["cmake", "--build", BUILD_NEXTPNR, "--parallel"])
    run(["cmake", "--install", BUILD_NEXTPNR])


def audit(lock: dict) -> dict:
    failures: list[str] = []
    observed_repositories = {}
    for name, wanted in lock["repositories"].items():
        path = SOURCE_ROOT / name
        if not (path / ".git").is_dir():
            failures.append(f"missing source repository: {name}")
            observed_repositories[name] = None
            continue
        found = revision(path)
        observed_repositories[name] = found
        if found != wanted:
            failures.append(f"{name}: expected {wanted}, found {found}")

    observed_submodules = {}
    for relative, wanted in lock.get("submodules", {}).items():
        path = SOURCE_ROOT / relative
        if not path.exists():
            found = None
        else:
            found = revision(path)
        observed_submodules[relative] = found
        if found != wanted:
            failures.append(f"{relative}: expected {wanted}, found {found}")

    commands = {}
    for name in [
        "cmake",
        "yosys",
        "ecppack",
        "dfu-util",
        "dfu-suffix",
        "riscv-none-elf-gcc",
    ]:
        search_path = os.environ.get("PATH", "")
        if name == "riscv-none-elf-gcc":
            riscv_bin = REPOSITORY / ".aisl/toolchains/xpack-riscv-none-elf-gcc-14.2.0-3/bin"
            search_path = f"{riscv_bin}{os.pathsep}{search_path}"
        commands[name] = shutil.which(name, path=search_path)
        if commands[name] is None:
            failures.append(f"missing command: {name}")

    nextpnr = INSTALL / "bin/nextpnr-ecp5"
    commands["nextpnr-ecp5"] = str(nextpnr) if nextpnr.is_file() else None
    if not nextpnr.is_file():
        failures.append("missing installed nextpnr-ecp5")

    python = VENV / "bin/python"
    imports_ok = False
    if python.is_file():
        python_roots = [str(SOURCE_ROOT / name) for name in EDITABLE_PACKAGES]
        environment = os.environ.copy()
        environment["PYTHONPATH"] = os.pathsep.join(python_roots)
        probe = subprocess.run(
            [
                python,
                "-c",
                "import migen, litex, litedram, litex_boards, pythondata_cpu_vexriscv, "
                "pythondata_software_picolibc, pythondata_software_compiler_rt",
            ],
            check=False,
            env=environment,
        )
        imports_ok = probe.returncode == 0
    if not imports_ok:
        failures.append("pinned LiteX Python environment import check failed")

    return {
        "schema_version": 1,
        "success": not failures,
        "lock_sha256": __import__("hashlib").sha256(LOCK_PATH.read_bytes()).hexdigest(),
        "repositories": observed_repositories,
        "submodules": observed_submodules,
        "commands": commands,
        "python_imports": imports_ok,
        "failures": failures,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="audit without installing")
    args = parser.parse_args()
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))

    require("git")
    if not args.check:
        require("cmake")
        require("yosys")
        require("ecppack")
        if not shutil.which("riscv-none-elf-gcc"):
            bootstrap = REPOSITORY / "workspace/tools/bootstrap-riscv-toolchain"
            run([bootstrap])
        install_sources(lock)
        install_python()
        install_nextpnr()

    report = audit(lock)
    print(json.dumps(report, indent=2))
    return 0 if report["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
