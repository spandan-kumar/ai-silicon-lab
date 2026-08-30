.PHONY: check reference vectors software software-benchmark rtl-functions rtl-primitives rtl-gcm lint repeatability synthesis simulation-complete verify-nist

PYTHON ?= python3
BUILD := build
GENERATED := $(BUILD)/generated
VERILATOR ?= verilator
RTL_SOURCE_ID := $(shell shasum -a 256 rtl/aes_functions.svh rtl/aes256_iterative.sv rtl/aes256_parallel.sv tests/primitive_harness.cpp tests/primitive_vectors.h | shasum -a 256 | cut -c1-16)
VERILATOR_OBJ_ROOT ?= /tmp/aisl-aes-verilator-$(shell id -u)-$(RTL_SOURCE_ID)
ITERATIVE_OBJ := $(VERILATOR_OBJ_ROOT)/iterative
PARALLEL_OBJ := $(VERILATOR_OBJ_ROOT)/parallel
KEY_SCHEDULE_OBJ := $(VERILATOR_OBJ_ROOT)/key-schedule
GCM_SOURCE_ID := $(shell shasum -a 256 rtl/*.sv rtl/aes_functions.svh tests/gcm_harness.cpp tests/gcm_vectors.h | shasum -a 256 | cut -c1-16)
GCM_OBJ_ROOT ?= /tmp/aisl-gcm-verilator-$(shell id -u)-$(GCM_SOURCE_ID)
GCM_ITERATIVE_OBJ := $(GCM_OBJ_ROOT)/iterative
GCM_PARALLEL_OBJ := $(GCM_OBJ_ROOT)/parallel
AES_ARCHIVE := $(BUILD)/KAT_AES.zip
GCM_ARCHIVE := $(BUILD)/gcmtestvectors.zip
AES_URL := https://csrc.nist.gov/CSRC/media/Projects/Cryptographic-Algorithm-Validation-Program/documents/aes/KAT_AES.zip
GCM_URL := https://csrc.nist.gov/CSRC/media/Projects/Cryptographic-Algorithm-Validation-Program/documents/mac/gcmtestvectors.zip

check: reference vectors software rtl-functions lint rtl-primitives rtl-gcm repeatability

reference:
	$(PYTHON) tests/test_reference.py

vectors:
	$(PYTHON) tests/test_vectors.py

software: $(BUILD)/openssl_baseline
	$(PYTHON) tests/test_openssl.py

software-benchmark: $(BUILD)/openssl_baseline
	$(PYTHON) tools/benchmark_software.py --binary $(BUILD)/openssl_baseline --output reports/software_baseline.json

rtl-functions:
	mkdir -p $(GENERATED)
	$(PYTHON) tools/generate_rtl_functions.py --output $(GENERATED)/aes_functions.svh
	$(PYTHON) tools/generate_harness_vectors.py --output-dir $(GENERATED)
	cmp rtl/aes_functions.svh $(GENERATED)/aes_functions.svh
	cmp tests/primitive_vectors.h $(GENERATED)/primitive_vectors.h
	cmp tests/gcm_vectors.h $(GENERATED)/gcm_vectors.h

$(BUILD)/aes256_iterative_sim: rtl/aes256_iterative.sv rtl/aes_functions.svh tests/primitive_harness.cpp tests/primitive_vectors.h | $(BUILD)
	mkdir -p $(ITERATIVE_OBJ)
	cp tests/primitive_harness.cpp tests/primitive_vectors.h $(ITERATIVE_OBJ)/
	$(VERILATOR) --cc --exe --build --sv -Wall -Irtl --Mdir $(ITERATIVE_OBJ) --top-module aes256_iterative -CFLAGS "-DITERATIVE -O3" -MAKEFLAGS "OPT_FAST=-O3 OPT_GLOBAL=-O3" rtl/aes256_iterative.sv $(ITERATIVE_OBJ)/primitive_harness.cpp
	cp $(ITERATIVE_OBJ)/Vaes256_iterative $@.new
	mv $@.new $@

$(BUILD)/aes256_parallel_sim: rtl/aes256_parallel.sv rtl/aes_functions.svh tests/primitive_harness.cpp tests/primitive_vectors.h | $(BUILD)
	mkdir -p $(PARALLEL_OBJ)
	cp tests/primitive_harness.cpp tests/primitive_vectors.h $(PARALLEL_OBJ)/
	$(VERILATOR) --cc --exe --build --sv -Wall -Irtl --Mdir $(PARALLEL_OBJ) --top-module aes256_parallel -CFLAGS -O3 -MAKEFLAGS "OPT_FAST=-O3 OPT_GLOBAL=-O3" rtl/aes256_parallel.sv $(PARALLEL_OBJ)/primitive_harness.cpp
	cp $(PARALLEL_OBJ)/Vaes256_parallel $@.new
	mv $@.new $@

$(BUILD)/aes256_key_schedule_sim: rtl/aes256_key_schedule_probe.sv rtl/aes_functions.svh tests/key_schedule_harness.cpp tests/primitive_vectors.h | $(BUILD)
	mkdir -p $(KEY_SCHEDULE_OBJ)
	cp tests/key_schedule_harness.cpp tests/primitive_vectors.h $(KEY_SCHEDULE_OBJ)/
	$(VERILATOR) --cc --exe --build --sv -Wall -Irtl --Mdir $(KEY_SCHEDULE_OBJ) --top-module aes256_key_schedule_probe -CFLAGS -O3 -MAKEFLAGS "OPT_FAST=-O3 OPT_GLOBAL=-O3" rtl/aes256_key_schedule_probe.sv $(KEY_SCHEDULE_OBJ)/key_schedule_harness.cpp
	cp $(KEY_SCHEDULE_OBJ)/Vaes256_key_schedule_probe $@.new
	mv $@.new $@

rtl-primitives: $(BUILD)/aes256_key_schedule_sim $(BUILD)/aes256_iterative_sim $(BUILD)/aes256_parallel_sim
	$(BUILD)/aes256_key_schedule_sim
	$(BUILD)/aes256_iterative_sim
	$(BUILD)/aes256_parallel_sim

GCM_RTL := rtl/aes_gcm_core.sv rtl/aes256_iterative_enc.sv rtl/aes256_parallel_enc.sv rtl/ghash_iterative.sv rtl/ghash_parallel.sv

$(BUILD)/aes_gcm_iterative_sim: $(GCM_RTL) rtl/aes_functions.svh tests/gcm_harness.cpp tests/gcm_vectors.h | $(BUILD)
	mkdir -p $(GCM_ITERATIVE_OBJ)
	cp tests/gcm_harness.cpp tests/gcm_vectors.h $(GCM_ITERATIVE_OBJ)/
	$(VERILATOR) --cc --exe --build --sv -Wall -Irtl --Mdir $(GCM_ITERATIVE_OBJ) --top-module aes_gcm_core -GARCH=0 -CFLAGS "-DITERATIVE -O3" -MAKEFLAGS "OPT_FAST=-O3 OPT_GLOBAL=-O3" $(GCM_RTL) $(GCM_ITERATIVE_OBJ)/gcm_harness.cpp
	cp $(GCM_ITERATIVE_OBJ)/Vaes_gcm_core $@.new
	mv $@.new $@

$(BUILD)/aes_gcm_parallel_sim: $(GCM_RTL) rtl/aes_functions.svh tests/gcm_harness.cpp tests/gcm_vectors.h | $(BUILD)
	mkdir -p $(GCM_PARALLEL_OBJ)
	cp tests/gcm_harness.cpp tests/gcm_vectors.h $(GCM_PARALLEL_OBJ)/
	$(VERILATOR) --cc --exe --build --sv -Wall -Irtl --Mdir $(GCM_PARALLEL_OBJ) --top-module aes_gcm_core -GARCH=1 -CFLAGS -O3 -MAKEFLAGS "OPT_FAST=-O3 OPT_GLOBAL=-O3" $(GCM_RTL) $(GCM_PARALLEL_OBJ)/gcm_harness.cpp
	cp $(GCM_PARALLEL_OBJ)/Vaes_gcm_core $@.new
	mv $@.new $@

rtl-gcm: $(BUILD)/aes_gcm_iterative_sim $(BUILD)/aes_gcm_parallel_sim
	$(BUILD)/aes_gcm_iterative_sim
	$(BUILD)/aes_gcm_parallel_sim

lint:
	$(VERILATOR) --lint-only --sv -Wall -Irtl --top-module aes256_key_schedule_probe rtl/aes256_key_schedule_probe.sv
	$(VERILATOR) --lint-only --sv -Wall -Irtl --top-module aes256_iterative rtl/aes256_iterative.sv
	$(VERILATOR) --lint-only --sv -Wall -Irtl --top-module aes256_parallel rtl/aes256_parallel.sv
	$(VERILATOR) --lint-only --sv -Wall -Irtl --top-module aes_gcm_core -GARCH=0 rtl/aes_gcm_core.sv rtl/aes256_iterative_enc.sv rtl/ghash_iterative.sv
	$(VERILATOR) --lint-only --sv -Wall -Irtl --top-module aes_gcm_core -GARCH=1 rtl/aes_gcm_core.sv rtl/aes256_parallel_enc.sv rtl/ghash_parallel.sv

repeatability: $(BUILD)/aes_gcm_iterative_sim $(BUILD)/aes_gcm_parallel_sim
	mkdir -p $(BUILD)/repeatability
	$(BUILD)/aes_gcm_iterative_sim > $(BUILD)/repeatability/iterative-a.txt
	$(BUILD)/aes_gcm_iterative_sim > $(BUILD)/repeatability/iterative-b.txt
	cmp $(BUILD)/repeatability/iterative-a.txt $(BUILD)/repeatability/iterative-b.txt
	$(BUILD)/aes_gcm_parallel_sim > $(BUILD)/repeatability/parallel-a.txt
	$(BUILD)/aes_gcm_parallel_sim > $(BUILD)/repeatability/parallel-b.txt
	cmp $(BUILD)/repeatability/parallel-a.txt $(BUILD)/repeatability/parallel-b.txt

synthesis:
	$(PYTHON) tools/run_synthesis.py --output-dir $(BUILD)/synth

simulation-complete: check synthesis

$(BUILD)/openssl_baseline: software/openssl_baseline.c | $(BUILD)
	$(CC) -std=c11 -O3 -Wall -Wextra -Werror $< -o $@ $$(pkg-config --cflags --libs openssl)

$(BUILD):
	mkdir -p $@

$(AES_ARCHIVE): | $(BUILD)
	curl -L --fail --silent --show-error -o $@ $(AES_URL)

$(GCM_ARCHIVE): | $(BUILD)
	curl -L --fail --silent --show-error -o $@ $(GCM_URL)

verify-nist: $(AES_ARCHIVE) $(GCM_ARCHIVE)
	$(PYTHON) tools/import_nist_vectors.py --aes-archive $(AES_ARCHIVE) --gcm-archive $(GCM_ARCHIVE) --output $(BUILD)/nist_subset.json
	cmp vectors/nist_subset.json $(BUILD)/nist_subset.json
