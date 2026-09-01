.PHONY: check reference vectors software software-benchmark rtl-functions rtl-primitives rtl-gcm lint repeatability synthesis asic-synthesis sbox-circuit-study masked-sbox-study masked-sbox-fullverif gate-verify evidence-logs results simulation-complete verify-nist

PYTHON ?= python3
BUILD := build
GENERATED := $(BUILD)/generated
VERILATOR ?= verilator
RTL_SOURCE_ID := $(shell shasum -a 256 rtl/aes_functions.svh rtl/aes_sbox_probe.sv rtl/aes256_iterative.sv rtl/aes256_parallel.sv tests/sbox_harness.cpp tests/sbox_vectors.h tests/primitive_harness.cpp tests/primitive_vectors.h | shasum -a 256 | cut -c1-16)
VERILATOR_OBJ_ROOT ?= /tmp/aisl-aes-verilator-$(shell id -u)-$(RTL_SOURCE_ID)
ITERATIVE_OBJ := $(VERILATOR_OBJ_ROOT)/iterative
PARALLEL_OBJ := $(VERILATOR_OBJ_ROOT)/parallel
KEY_SCHEDULE_OBJ := $(VERILATOR_OBJ_ROOT)/key-schedule
SBOX_OBJ := $(VERILATOR_OBJ_ROOT)/sbox
GCM_SOURCE_ID := $(shell shasum -a 256 rtl/*.sv rtl/aes_functions.svh tests/gcm_harness.cpp tests/gcm_vectors.h | shasum -a 256 | cut -c1-16)
GCM_OBJ_ROOT ?= /tmp/aisl-gcm-verilator-$(shell id -u)-$(GCM_SOURCE_ID)
GCM_ITERATIVE_OBJ := $(GCM_OBJ_ROOT)/iterative
GCM_PARALLEL_OBJ := $(GCM_OBJ_ROOT)/parallel
GCM_BALANCED_OBJ := $(GCM_OBJ_ROOT)/balanced
GCM_WIDE_OBJ := $(GCM_OBJ_ROOT)/wide
GCM_ULTRAWIDE_OBJ := $(GCM_OBJ_ROOT)/ultrawide
GCM_BALANCED_WIDE_OBJ := $(GCM_OBJ_ROOT)/balanced-wide
GCM_BALANCED_ULTRAWIDE_OBJ := $(GCM_OBJ_ROOT)/balanced-ultrawide
GCM_BALANCED_XWIDE_OBJ := $(GCM_OBJ_ROOT)/balanced-xwide
AES_ARCHIVE := $(BUILD)/KAT_AES.zip
GCM_ARCHIVE := $(BUILD)/gcmtestvectors.zip
AES_URL := https://csrc.nist.gov/CSRC/media/Projects/Cryptographic-Algorithm-Validation-Program/documents/aes/KAT_AES.zip
GCM_URL := https://csrc.nist.gov/CSRC/media/Projects/Cryptographic-Algorithm-Validation-Program/documents/mac/gcmtestvectors.zip
NANGATE_LIB := $(BUILD)/technology/nangate45/NangateOpenCellLibrary_typical.lib
ASIC_SUMMARY := $(BUILD)/asic-synth/summary.json
FULLVERIF_ROOT ?= $(BUILD)/research-tools/fullverif

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
	cmp tests/sbox_vectors.h $(GENERATED)/sbox_vectors.h
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

$(BUILD)/aes_sbox_sim: rtl/aes_sbox_probe.sv rtl/aes_functions.svh tests/sbox_harness.cpp tests/sbox_vectors.h | $(BUILD)
	mkdir -p $(SBOX_OBJ)
	cp tests/sbox_harness.cpp tests/sbox_vectors.h $(SBOX_OBJ)/
	$(VERILATOR) --cc --exe --build --sv -Wall -Irtl --Mdir $(SBOX_OBJ) --top-module aes_sbox_probe -CFLAGS -O3 -MAKEFLAGS "OPT_FAST=-O3 OPT_GLOBAL=-O3" rtl/aes_sbox_probe.sv $(SBOX_OBJ)/sbox_harness.cpp
	cp $(SBOX_OBJ)/Vaes_sbox_probe $@.new
	mv $@.new $@

rtl-primitives: $(BUILD)/aes_sbox_sim $(BUILD)/aes256_key_schedule_sim $(BUILD)/aes256_iterative_sim $(BUILD)/aes256_parallel_sim
	$(BUILD)/aes_sbox_sim
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

$(BUILD)/aes_gcm_balanced_sim: $(GCM_RTL) rtl/aes_functions.svh tests/gcm_harness.cpp tests/gcm_vectors.h | $(BUILD)
	mkdir -p $(GCM_BALANCED_OBJ)
	cp tests/gcm_harness.cpp tests/gcm_vectors.h $(GCM_BALANCED_OBJ)/
	$(VERILATOR) --cc --exe --build --sv -Wall -Irtl --Mdir $(GCM_BALANCED_OBJ) --top-module aes_gcm_core -GARCH=2 -CFLAGS "-DBALANCED -O3" -MAKEFLAGS "OPT_FAST=-O3 OPT_GLOBAL=-O3" $(GCM_RTL) $(GCM_BALANCED_OBJ)/gcm_harness.cpp
	cp $(GCM_BALANCED_OBJ)/Vaes_gcm_core $@.new
	mv $@.new $@

$(BUILD)/aes_gcm_wide_sim: $(GCM_RTL) rtl/aes_functions.svh tests/gcm_harness.cpp tests/gcm_vectors.h | $(BUILD)
	mkdir -p $(GCM_WIDE_OBJ)
	cp tests/gcm_harness.cpp tests/gcm_vectors.h $(GCM_WIDE_OBJ)/
	$(VERILATOR) --cc --exe --build --sv -Wall -Irtl --Mdir $(GCM_WIDE_OBJ) --top-module aes_gcm_core -GARCH=3 -CFLAGS "-DWIDE -O3" -MAKEFLAGS "OPT_FAST=-O3 OPT_GLOBAL=-O3" $(GCM_RTL) $(GCM_WIDE_OBJ)/gcm_harness.cpp
	cp $(GCM_WIDE_OBJ)/Vaes_gcm_core $@.new
	mv $@.new $@

$(BUILD)/aes_gcm_ultrawide_sim: $(GCM_RTL) rtl/aes_functions.svh tests/gcm_harness.cpp tests/gcm_vectors.h | $(BUILD)
	mkdir -p $(GCM_ULTRAWIDE_OBJ)
	cp tests/gcm_harness.cpp tests/gcm_vectors.h $(GCM_ULTRAWIDE_OBJ)/
	$(VERILATOR) --cc --exe --build --sv -Wall -Irtl --Mdir $(GCM_ULTRAWIDE_OBJ) --top-module aes_gcm_core -GARCH=4 -CFLAGS "-DULTRAWIDE -O3" -MAKEFLAGS "OPT_FAST=-O3 OPT_GLOBAL=-O3" $(GCM_RTL) $(GCM_ULTRAWIDE_OBJ)/gcm_harness.cpp
	cp $(GCM_ULTRAWIDE_OBJ)/Vaes_gcm_core $@.new
	mv $@.new $@

$(BUILD)/aes_gcm_balanced_wide_sim: $(GCM_RTL) rtl/aes_functions.svh tests/gcm_harness.cpp tests/gcm_vectors.h | $(BUILD)
	mkdir -p $(GCM_BALANCED_WIDE_OBJ)
	cp tests/gcm_harness.cpp tests/gcm_vectors.h $(GCM_BALANCED_WIDE_OBJ)/
	$(VERILATOR) --cc --exe --build --sv -Wall -Irtl --Mdir $(GCM_BALANCED_WIDE_OBJ) --top-module aes_gcm_core -GARCH=5 -CFLAGS "-DBALANCED_WIDE -O3" -MAKEFLAGS "OPT_FAST=-O3 OPT_GLOBAL=-O3" $(GCM_RTL) $(GCM_BALANCED_WIDE_OBJ)/gcm_harness.cpp
	cp $(GCM_BALANCED_WIDE_OBJ)/Vaes_gcm_core $@.new
	mv $@.new $@

$(BUILD)/aes_gcm_balanced_ultrawide_sim: $(GCM_RTL) rtl/aes_functions.svh tests/gcm_harness.cpp tests/gcm_vectors.h | $(BUILD)
	mkdir -p $(GCM_BALANCED_ULTRAWIDE_OBJ)
	cp tests/gcm_harness.cpp tests/gcm_vectors.h $(GCM_BALANCED_ULTRAWIDE_OBJ)/
	$(VERILATOR) --cc --exe --build --sv -Wall -Irtl --Mdir $(GCM_BALANCED_ULTRAWIDE_OBJ) --top-module aes_gcm_core -GARCH=6 -CFLAGS "-DBALANCED_ULTRAWIDE -O3" -MAKEFLAGS "OPT_FAST=-O3 OPT_GLOBAL=-O3" $(GCM_RTL) $(GCM_BALANCED_ULTRAWIDE_OBJ)/gcm_harness.cpp
	cp $(GCM_BALANCED_ULTRAWIDE_OBJ)/Vaes_gcm_core $@.new
	mv $@.new $@

$(BUILD)/aes_gcm_balanced_xwide_sim: $(GCM_RTL) rtl/aes_functions.svh tests/gcm_harness.cpp tests/gcm_vectors.h | $(BUILD)
	mkdir -p $(GCM_BALANCED_XWIDE_OBJ)
	cp tests/gcm_harness.cpp tests/gcm_vectors.h $(GCM_BALANCED_XWIDE_OBJ)/
	$(VERILATOR) --cc --exe --build --sv -Wall -Irtl --Mdir $(GCM_BALANCED_XWIDE_OBJ) --top-module aes_gcm_core -GARCH=7 -CFLAGS "-DBALANCED_XWIDE -O3" -MAKEFLAGS "OPT_FAST=-O3 OPT_GLOBAL=-O3" $(GCM_RTL) $(GCM_BALANCED_XWIDE_OBJ)/gcm_harness.cpp
	cp $(GCM_BALANCED_XWIDE_OBJ)/Vaes_gcm_core $@.new
	mv $@.new $@

rtl-gcm: $(BUILD)/aes_gcm_iterative_sim $(BUILD)/aes_gcm_parallel_sim $(BUILD)/aes_gcm_balanced_sim $(BUILD)/aes_gcm_wide_sim $(BUILD)/aes_gcm_ultrawide_sim $(BUILD)/aes_gcm_balanced_wide_sim $(BUILD)/aes_gcm_balanced_ultrawide_sim $(BUILD)/aes_gcm_balanced_xwide_sim
	$(BUILD)/aes_gcm_iterative_sim
	$(BUILD)/aes_gcm_parallel_sim
	$(BUILD)/aes_gcm_balanced_sim
	$(BUILD)/aes_gcm_wide_sim
	$(BUILD)/aes_gcm_ultrawide_sim
	$(BUILD)/aes_gcm_balanced_wide_sim
	$(BUILD)/aes_gcm_balanced_ultrawide_sim
	$(BUILD)/aes_gcm_balanced_xwide_sim

lint:
	$(VERILATOR) --lint-only --sv -Wall -Irtl --top-module aes_sbox_probe rtl/aes_sbox_probe.sv
	$(VERILATOR) --lint-only --sv -Wall -Irtl --top-module aes256_key_schedule_probe rtl/aes256_key_schedule_probe.sv
	$(VERILATOR) --lint-only --sv -Wall -Irtl --top-module aes256_iterative rtl/aes256_iterative.sv
	$(VERILATOR) --lint-only --sv -Wall -Irtl --top-module aes256_parallel rtl/aes256_parallel.sv
	for arch in 0 1 2 3 4 5 6 7; do $(VERILATOR) --lint-only --sv -Wall -Irtl --top-module aes_gcm_core -GARCH=$$arch $(GCM_RTL) || exit; done

repeatability: $(BUILD)/aes_gcm_iterative_sim $(BUILD)/aes_gcm_parallel_sim $(BUILD)/aes_gcm_balanced_sim $(BUILD)/aes_gcm_wide_sim $(BUILD)/aes_gcm_ultrawide_sim $(BUILD)/aes_gcm_balanced_wide_sim $(BUILD)/aes_gcm_balanced_ultrawide_sim $(BUILD)/aes_gcm_balanced_xwide_sim
	mkdir -p $(BUILD)/repeatability
	for stem in iterative parallel balanced wide ultrawide balanced_wide balanced_ultrawide balanced_xwide; do \
	  $(BUILD)/aes_gcm_$${stem}_sim > $(BUILD)/repeatability/$${stem}-a.txt; \
	  $(BUILD)/aes_gcm_$${stem}_sim > $(BUILD)/repeatability/$${stem}-b.txt; \
	  cmp $(BUILD)/repeatability/$${stem}-a.txt $(BUILD)/repeatability/$${stem}-b.txt || exit; \
	done

synthesis:
	$(PYTHON) tools/run_synthesis.py --output-dir $(BUILD)/synth

asic-synthesis: $(NANGATE_LIB)
	$(PYTHON) tools/run_asic_synthesis.py --output-dir $(BUILD)/asic-synth --liberty $(NANGATE_LIB)

sbox-circuit-study: $(NANGATE_LIB)
	$(PYTHON) tools/benchmark_sbox_circuits.py --output-dir $(BUILD)/sbox-circuit-study --summary-output reports/sbox_circuit_study.json --liberty $(NANGATE_LIB)

masked-sbox-study: $(NANGATE_LIB)
	$(PYTHON) tools/benchmark_masked_sbox_circuits.py --output-dir $(BUILD)/masked-sbox-study --summary-output reports/masked_sbox_study.json --liberty $(NANGATE_LIB)

masked-sbox-fullverif:
	$(PYTHON) tools/verify_masked_sbox_fullverif.py --fullverif-root $(FULLVERIF_ROOT) --output-dir $(BUILD)/masked-sbox-fullverif --summary-output reports/masked_sbox_fullverif.json
	$(PYTHON) tools/verify_masked_sbox_fullverif.py --circuit classic-g113-d27 --fullverif-root $(FULLVERIF_ROOT) --output-dir $(BUILD)/masked-sbox-fullverif-classic --summary-output reports/masked_sbox_fullverif_classic.json

gate-verify: $(ASIC_SUMMARY)
	$(PYTHON) tools/verify_mapped_netlist.py --synthesis-dir $(BUILD)/asic-synth --output-dir $(BUILD)/gate-verify --architecture balanced-ultrawide-1r32b

evidence-logs: rtl-primitives rtl-gcm
	mkdir -p $(BUILD)/logs
	$(BUILD)/aes_sbox_sim > $(BUILD)/logs/sbox.txt
	$(BUILD)/aes256_key_schedule_sim > $(BUILD)/logs/key-schedule.txt
	$(BUILD)/aes256_iterative_sim > $(BUILD)/logs/primitive-iterative.txt
	$(BUILD)/aes256_parallel_sim > $(BUILD)/logs/primitive-parallel.txt
	for stem in iterative parallel balanced wide ultrawide balanced_wide balanced_ultrawide balanced_xwide; do $(BUILD)/aes_gcm_$${stem}_sim > $(BUILD)/logs/gcm-$${stem}.txt || exit; done

results: evidence-logs synthesis asic-synthesis gate-verify
	$(PYTHON) tools/collect_results.py --logs $(BUILD)/logs --synthesis $(BUILD)/synth --asic-synthesis $(BUILD)/asic-synth --gate-verification $(BUILD)/gate-verify/summary.json --output reports/results.json

simulation-complete: check synthesis asic-synthesis gate-verify

$(ASIC_SUMMARY): $(NANGATE_LIB) $(GCM_RTL) rtl/aes_functions.svh tools/run_asic_synthesis.py tools/run_synthesis.py asic/nangate45.constr
	$(PYTHON) tools/run_asic_synthesis.py --output-dir $(BUILD)/asic-synth --liberty $(NANGATE_LIB)

$(BUILD)/openssl_baseline: software/openssl_baseline.c | $(BUILD)
	$(CC) -std=c11 -O3 -Wall -Wextra -Werror $< -o $@ $$(pkg-config --cflags --libs openssl)

$(BUILD):
	mkdir -p $@

$(AES_ARCHIVE): | $(BUILD)
	curl -L --fail --silent --show-error -o $@ $(AES_URL)

$(GCM_ARCHIVE): | $(BUILD)
	curl -L --fail --silent --show-error -o $@ $(GCM_URL)

$(NANGATE_LIB): tools/fetch_nangate45.py | $(BUILD)
	$(PYTHON) tools/fetch_nangate45.py --output $@

verify-nist: $(AES_ARCHIVE) $(GCM_ARCHIVE)
	$(PYTHON) tools/import_nist_vectors.py --aes-archive $(AES_ARCHIVE) --gcm-archive $(GCM_ARCHIVE) --output $(BUILD)/nist_subset.json
	cmp vectors/nist_subset.json $(BUILD)/nist_subset.json
