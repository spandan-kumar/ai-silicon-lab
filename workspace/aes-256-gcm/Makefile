.PHONY: check reference vectors software verify-nist

PYTHON ?= python3
BUILD := build
AES_ARCHIVE := $(BUILD)/KAT_AES.zip
GCM_ARCHIVE := $(BUILD)/gcmtestvectors.zip
AES_URL := https://csrc.nist.gov/CSRC/media/Projects/Cryptographic-Algorithm-Validation-Program/documents/aes/KAT_AES.zip
GCM_URL := https://csrc.nist.gov/CSRC/media/Projects/Cryptographic-Algorithm-Validation-Program/documents/mac/gcmtestvectors.zip

check: reference vectors software

reference:
	$(PYTHON) tests/test_reference.py

vectors:
	$(PYTHON) tests/test_vectors.py

software: $(BUILD)/openssl_baseline
	$(PYTHON) tests/test_openssl.py

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
