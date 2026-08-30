VERILATOR ?= verilator

ROOT := ../../..
BRIDGE_RTL := rtl/aisl_obi_wishbone_bridge.sv
BRIDGE_TB := tests/tb_obi_wishbone_bridge.sv
BRIDGE_ID := $(shell shasum -a 256 $(BRIDGE_RTL) $(BRIDGE_TB) | shasum -a 256 | cut -c1-16)
BRIDGE_OBJ := /tmp/aisl-orangecrab-bridge-$(shell id -u)-$(BRIDGE_ID)
BUILD_DIR := build
TOOLCHAIN_ROOT := $(ROOT)/.aisl/toolchains/orangecrab
TOOLCHAIN_SRC := $(TOOLCHAIN_ROOT)/src
TOOLCHAIN_ID := $(shell shasum -a 256 toolchain.lock.json | cut -c1-16)
STAGE_ROOT := /tmp/aisl-orangecrab-gateware-$(shell id -u)-$(TOOLCHAIN_ID)
STAGE_SRC := $(STAGE_ROOT)/src
STAGE_RTL := $(STAGE_ROOT)/rtl
STAGE_BUILD := $(STAGE_ROOT)/build
STAGE_PACKAGES := migen litex litedram litex-boards pythondata-cpu-vexriscv \
	pythondata-software-picolibc pythondata-software-compiler_rt
PYTHONPATH_STAGE := $(STAGE_SRC)/migen:$(STAGE_SRC)/litex:$(STAGE_SRC)/litedram:$(STAGE_SRC)/litex-boards:$(STAGE_SRC)/pythondata-cpu-vexriscv:$(STAGE_SRC)/pythondata-software-picolibc:$(STAGE_SRC)/pythondata-software-compiler_rt
PYTHONPATH_TOOLCHAIN := $(TOOLCHAIN_SRC)/migen:$(TOOLCHAIN_SRC)/litex:$(TOOLCHAIN_SRC)/litedram:$(TOOLCHAIN_SRC)/litex-boards:$(TOOLCHAIN_SRC)/pythondata-cpu-vexriscv:$(TOOLCHAIN_SRC)/pythondata-software-picolibc:$(TOOLCHAIN_SRC)/pythondata-software-compiler_rt
VENV_BIN := $(TOOLCHAIN_ROOT)/venv/bin
PYTHON := $(VENV_BIN)/python
NEXTPNR_BIN := $(TOOLCHAIN_ROOT)/install/bin
RISCV_BIN := $(ROOT)/.aisl/toolchains/xpack-riscv-none-elf-gcc-14.2.0-3/bin
TARGET_PATH := $(abspath $(VENV_BIN)):$(abspath $(NEXTPNR_BIN)):$(abspath $(RISCV_BIN)):$(PATH)

.PHONY: all toolchain toolchain-check test host-test rtl stage gateware verify-gateware program run clean

all: test

toolchain:
	python3 setup_toolchain.py

toolchain-check:
	python3 setup_toolchain.py --check

test:
	@mkdir -p $(BRIDGE_OBJ)
	cp $(BRIDGE_RTL) $(BRIDGE_TB) $(BRIDGE_OBJ)/
	$(VERILATOR) --binary --timing --Wall -Wno-fatal \
		-Wno-PROCASSINIT -Wno-UNUSEDSIGNAL \
		--top-module tb_obi_wishbone_bridge \
		--Mdir $(BRIDGE_OBJ)/obj \
		$(BRIDGE_OBJ)/aisl_obi_wishbone_bridge.sv \
		$(BRIDGE_OBJ)/tb_obi_wishbone_bridge.sv
	$(BRIDGE_OBJ)/obj/Vtb_obi_wishbone_bridge

host-test:
	"$(PYTHON)" -m unittest discover -s tests -p 'test_host.py' -v

rtl:
	$(MAKE) -C $(ROOT)/workspace/rtl_cv convert

stage: rtl
	rm -rf -- "$(STAGE_ROOT)"
	mkdir -p "$(STAGE_SRC)" "$(STAGE_RTL)"
	@for package in $(STAGE_PACKAGES); do \
		test -d "$(TOOLCHAIN_SRC)/$$package" || { echo "missing pinned source: $$package" >&2; exit 1; }; \
		cp -R "$(TOOLCHAIN_SRC)/$$package" "$(STAGE_SRC)/$$package"; \
	done
	cp "$(ROOT)/workspace/rtl_cv/build/aisl_soc.v" "$(STAGE_RTL)/aisl_soc.v"
	cp "$(BRIDGE_RTL)" "$(STAGE_RTL)/aisl_obi_wishbone_bridge.sv"

gateware: test stage
	PATH="$(TARGET_PATH)" \
	PYTHONPATH="$(PYTHONPATH_STAGE)" \
	AISL_CONVERTED_RTL="$(STAGE_RTL)/aisl_soc.v" \
	AISL_BRIDGE_RTL="$(STAGE_RTL)/aisl_obi_wishbone_bridge.sv" \
	"$(PYTHON)" target.py \
		--build \
		--output-dir "$(STAGE_BUILD)" \
		--device 85F \
		--sys-clk-freq 48000000 \
		--nextpnr-seed 1 \
		--nextpnr-timingstrict
	rm -rf -- "$(abspath $(BUILD_DIR))"
	cp -R "$(STAGE_BUILD)" "$(abspath $(BUILD_DIR))"

verify-gateware:
	"$(PYTHON)" verify_build.py

program: toolchain-check rtl
	test -f "$(abspath $(BUILD_DIR))/gateware/gsd_orangecrab.bit"
	PATH="$(TARGET_PATH)" \
	PYTHONPATH="$(PYTHONPATH_TOOLCHAIN)" \
	AISL_CONVERTED_RTL="$(abspath $(ROOT)/workspace/rtl_cv/build/aisl_soc.v)" \
	AISL_BRIDGE_RTL="$(abspath $(BRIDGE_RTL))" \
	"$(PYTHON)" target.py \
		--load \
		--output-dir "$(abspath $(BUILD_DIR))" \
		--device 85F \
		--sys-clk-freq 48000000

run:
	PYTHONPATH="$(PYTHONPATH_TOOLCHAIN)" \
		"$(PYTHON)" host.py $(ARGS)

clean:
	rm -rf -- "$(abspath $(BUILD_DIR))"
	rm -rf -- "$(STAGE_ROOT)"
	rm -rf -- $(BRIDGE_OBJ)
