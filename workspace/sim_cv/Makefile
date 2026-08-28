VERILATOR ?= verilator
PYTHON ?= python3
RTL_DIR := ../rtl_cv
VENDOR := $(RTL_DIR)/vendor/cv32e40p
BUILD_DIR := build

PACKAGE_SOURCES := \
	$(VENDOR)/rtl/include/cv32e40p_apu_core_pkg.sv \
	$(VENDOR)/rtl/include/cv32e40p_fpu_pkg.sv \
	$(VENDOR)/rtl/include/cv32e40p_pkg.sv
CORE_SOURCES := $(sort $(wildcard $(VENDOR)/rtl/*.sv))
RTL_SOURCES := $(PACKAGE_SOURCES) $(CORE_SOURCES) \
	$(RTL_DIR)/clock_gate_generic.sv \
	$(RTL_DIR)/aisl_soc_cv.sv

HOST_OPT ?= -O3 -march=native -flto
HOST_LDFLAGS ?= -flto
VERILATOR_EXTRA ?= -O3 --no-assert
# Verilator's generated GNU Make build cannot operate in an object directory
# whose absolute path contains spaces, so keep intermediates under /tmp. Its
# reused dependency file resolves source paths from that directory too, so copy
# the hashed RTL inputs below it. Include build flags in the cache identity.
SOURCE_ID := $(shell { shasum -a 256 Makefile sim_main.cpp sha256.h $(RTL_SOURCES); \
	printf '%s\n' '$(HOST_OPT)' '$(HOST_LDFLAGS)' '$(VERILATOR_EXTRA)'; } | \
	shasum -a 256 | cut -c1-16)
RTL_SHA256 := $(shell shasum -a 256 $(RTL_SOURCES) | shasum -a 256 | cut -d' ' -f1)
OBJ_DIR ?= /tmp/aisl-cv-verilator-$(shell id -u)-$(SOURCE_ID)
STAGED_RTL_DIR := $(OBJ_DIR)/rtl_cv
STAGED_VENDOR := $(STAGED_RTL_DIR)/vendor/cv32e40p
STAGED_RTL_SOURCES := $(patsubst $(RTL_DIR)/%,$(STAGED_RTL_DIR)/%,$(RTL_SOURCES))
SIM := $(BUILD_DIR)/aisl_sim_cv
VERILATOR_WARNINGS := --Wno-DECLFILENAME --Wno-UNUSEDSIGNAL \
	--Wno-UNUSEDPARAM --Wno-PINCONNECTEMPTY --Wno-WIDTHEXPAND \
	--Wno-WIDTHTRUNC --Wno-CASEINCOMPLETE --Wno-COMBDLY \
	--Wno-GENUNNAMED --Wno-VARHIDDEN
VERILATOR_COMMON := --Wall -Wno-fatal $(VERILATOR_WARNINGS) \
	$(VERILATOR_EXTRA) --top-module aisl_soc_cv --prefix Vaisl_soc

.PHONY: all lint test clean

all: $(SIM)

lint:
	$(VERILATOR) --lint-only $(VERILATOR_COMMON) \
		-I$(VENDOR)/rtl/include $(RTL_SOURCES)

$(STAGED_RTL_DIR)/%: $(RTL_DIR)/%
	@mkdir -p "$(@D)"
	cp "$<" "$@"

$(SIM): Makefile sim_main.cpp sha256.h $(STAGED_RTL_SOURCES)
	@mkdir -p $(BUILD_DIR)
	@mkdir -p $(OBJ_DIR)
	cp sim_main.cpp sha256.h $(OBJ_DIR)/
	$(VERILATOR) --cc --exe --build -j 0 $(VERILATOR_COMMON) \
		-I$(STAGED_VENDOR)/rtl/include $(STAGED_RTL_SOURCES) \
		--Mdir $(OBJ_DIR) \
		--CFLAGS "-std=c++17 $(HOST_OPT) -DAISL_RTL_SHA256=\\\"$(RTL_SHA256)\\\"" \
		--LDFLAGS "$(HOST_LDFLAGS)" \
		-MAKEFLAGS "OPT_FAST=-O3 OPT_GLOBAL=-O3" \
		$(OBJ_DIR)/sim_main.cpp
	cp $(OBJ_DIR)/Vaisl_soc $(SIM).new
	mv $(SIM).new $(SIM)

test: $(SIM)
	$(MAKE) -B $(SIM)
	$(PYTHON) tests/gen_bringup.py $(BUILD_DIR)/bringup
	$(SIM) --firmware $(BUILD_DIR)/bringup/firmware.bin \
		--wad $(BUILD_DIR)/bringup/test.wad \
		--inputs $(BUILD_DIR)/bringup/input.events \
		--frames-dir $(BUILD_DIR)/bringup/frames-a \
		--result $(BUILD_DIR)/bringup/result-a.json \
		--width 2 --height 1 --frame-count 1 --warmup 0 --max-cycles 200000
	$(SIM) --firmware $(BUILD_DIR)/bringup/firmware.bin \
		--wad $(BUILD_DIR)/bringup/test.wad \
		--inputs $(BUILD_DIR)/bringup/input.events \
		--frames-dir $(BUILD_DIR)/bringup/frames-b \
		--result $(BUILD_DIR)/bringup/result-b.json \
		--width 2 --height 1 --frame-count 1 --warmup 0 --max-cycles 200000
	$(PYTHON) tests/verify_bringup.py \
		$(BUILD_DIR)/bringup/result-a.json $(BUILD_DIR)/bringup/result-b.json

clean:
	rm -rf $(BUILD_DIR)
	rm -rf -- $(OBJ_DIR)
