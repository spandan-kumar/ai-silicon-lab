SV2V ?= sv2v
YOSYS ?= yosys
BUILD_DIR := build
VENDOR := vendor/cv32e40p

PACKAGE_SOURCES := \
	$(VENDOR)/rtl/include/cv32e40p_apu_core_pkg.sv \
	$(VENDOR)/rtl/include/cv32e40p_fpu_pkg.sv \
	$(VENDOR)/rtl/include/cv32e40p_pkg.sv
CORE_SOURCES := $(sort $(wildcard $(VENDOR)/rtl/*.sv))
SYNTH_SOURCES := $(PACKAGE_SOURCES) $(CORE_SOURCES) clock_gate_generic.sv \
	aisl_soc_cv.sv
CONVERTED := $(BUILD_DIR)/aisl_soc.v
SYNTH_LOG := $(BUILD_DIR)/synthesis.log

.PHONY: all convert synth clean

all: synth

convert: $(CONVERTED)

synth: $(SYNTH_LOG)

$(CONVERTED): Makefile $(SYNTH_SOURCES)
	@mkdir -p $(BUILD_DIR)
	$(SV2V) -I$(VENDOR)/rtl/include -DSYNTHESIS --top=aisl_soc_cv \
		--write=$@ $(SYNTH_SOURCES)

$(SYNTH_LOG): $(CONVERTED) synth.ys
	@mkdir -p $(BUILD_DIR)
	@$(YOSYS) -Q -s synth.ys > $@ 2>&1 || { cat $@; exit 1; }
	@cat $@

clean:
	rm -rf $(BUILD_DIR)
