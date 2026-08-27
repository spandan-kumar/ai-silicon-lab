.PHONY: all candidate firmware simulator synthesis test

all: candidate

candidate: firmware simulator synthesis test

firmware:
	$(MAKE) -C firmware/doom BUILD=build-candidate ARCH=rv32imc LTO_FLAGS=-flto

simulator:
	$(MAKE) -C sim_cv

synthesis:
	$(MAKE) -C rtl_cv synth

test: simulator
	$(MAKE) -C sim_cv test
