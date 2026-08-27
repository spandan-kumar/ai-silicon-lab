YOSYS ?= yosys
BUILD_DIR := build
SYNTH_LOG := $(BUILD_DIR)/synthesis.log

.PHONY: all synth clean

all: synth

synth: $(SYNTH_LOG)

$(SYNTH_LOG): aisl_soc.v vendor/picorv32/picorv32.v synth.ys
	@mkdir -p $(BUILD_DIR)
	$(YOSYS) -Q -s synth.ys 2>&1 | tee $(SYNTH_LOG)

clean:
	rm -rf $(BUILD_DIR)
