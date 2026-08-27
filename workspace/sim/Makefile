VERILATOR ?= verilator
PYTHON ?= python3
RTL_DIR := ../rtl
BUILD_DIR := build
# Verilator's generated GNU Make build cannot operate in an object directory
# whose absolute path contains spaces.  The lab checkout may legitimately do
# so, therefore keep only the generated intermediate tree in /tmp and copy the
# finished simulator back into the repository build directory.
SOURCE_ID := $(shell shasum -a 256 Makefile sim_main.cpp sha256.h \
	$(RTL_DIR)/aisl_soc.v $(RTL_DIR)/vendor/picorv32/picorv32.v | \
	shasum -a 256 | cut -c1-16)
OBJ_DIR ?= /tmp/aisl-verilator-$(shell id -u)-$(SOURCE_ID)
SIM := $(BUILD_DIR)/aisl_sim
VERILATOR_WARNINGS := --Wno-DECLFILENAME --Wno-GENUNNAMED --Wno-BLKSEQ \
	--Wno-UNUSEDSIGNAL --Wno-PINCONNECTEMPTY
HOST_OPT ?= -O3 -march=native -flto
VERILATOR_COMMON := --Wall $(VERILATOR_WARNINGS) -I$(RTL_DIR) \
	--top-module aisl_soc $(RTL_DIR)/aisl_soc.v

.PHONY: all lint test evidence clean

all: $(SIM)

lint:
	$(VERILATOR) --lint-only $(VERILATOR_COMMON)

$(SIM): Makefile sim_main.cpp sha256.h $(RTL_DIR)/aisl_soc.v $(RTL_DIR)/vendor/picorv32/picorv32.v
	@mkdir -p $(BUILD_DIR)
	@mkdir -p $(OBJ_DIR)
	cp sim_main.cpp sha256.h $(OBJ_DIR)/
	$(VERILATOR) --cc --exe --build -j 0 $(VERILATOR_COMMON) \
		--Mdir $(OBJ_DIR) --CFLAGS "-std=c++17 $(HOST_OPT)" \
		--LDFLAGS "-flto" \
		-MAKEFLAGS "OPT_FAST=-O3 OPT_GLOBAL=-O3" \
		$(OBJ_DIR)/sim_main.cpp
	cp $(OBJ_DIR)/Vaisl_soc $(SIM).new
	mv $(SIM).new $(SIM)

test: $(SIM)
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

evidence:
	./record_evidence.sh

clean:
	rm -rf $(BUILD_DIR)
	rm -rf -- $(OBJ_DIR)
