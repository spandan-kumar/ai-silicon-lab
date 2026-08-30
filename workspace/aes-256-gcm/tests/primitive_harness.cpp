#include <verilated.h>

#ifdef ITERATIVE
#include "Vaes256_iterative.h"
using Dut = Vaes256_iterative;
static constexpr const char *kArchitecture = "iterative";
#else
#include "Vaes256_parallel.h"
using Dut = Vaes256_parallel;
static constexpr const char *kArchitecture = "parallel";
#endif

#include <cstdint>
#include <cstdio>
#include <cstring>
#include <string>

#include "primitive_vectors.h"

static uint64_t cycles = 0;

static int nibble(char value) {
    if (value >= '0' && value <= '9') return value - '0';
    if (value >= 'a' && value <= 'f') return value - 'a' + 10;
    return value - 'A' + 10;
}

template <size_t Words>
static void set_hex(VlWide<Words> &destination, const char *hex) {
    for (size_t i = 0; i < Words; ++i) destination[i] = 0;
    const size_t characters = std::strlen(hex);
    for (size_t byte_from_right = 0; byte_from_right < characters / 2; ++byte_from_right) {
        size_t position = characters - 2 * (byte_from_right + 1);
        uint32_t byte = static_cast<uint32_t>((nibble(hex[position]) << 4) | nibble(hex[position + 1]));
        destination[byte_from_right / 4] |= byte << (8 * (byte_from_right % 4));
    }
}

template <size_t Words>
static std::string get_hex(const VlWide<Words> &source) {
    static const char digits[] = "0123456789abcdef";
    std::string result(Words * 8, '0');
    for (size_t byte_from_right = 0; byte_from_right < Words * 4; ++byte_from_right) {
        uint8_t byte = static_cast<uint8_t>(source[byte_from_right / 4] >> (8 * (byte_from_right % 4)));
        size_t position = result.size() - 2 * (byte_from_right + 1);
        result[position] = digits[byte >> 4];
        result[position + 1] = digits[byte & 15];
    }
    return result;
}

static void tick(Dut &dut) {
    dut.clk = 0;
    dut.eval();
    dut.clk = 1;
    dut.eval();
    ++cycles;
}

static uint64_t load_key(Dut &dut, const char *key) {
    set_hex(dut.key_in, key);
    dut.key_valid = 1;
    uint64_t start = cycles;
    while (!dut.key_ready) tick(dut);
    tick(dut);
    dut.key_valid = 0;
    while (!dut.key_loaded) tick(dut);
    return cycles - start;
}

static uint64_t run_block(Dut &dut, const char *input, bool decrypt, const char *expected) {
    set_hex(dut.block_in, input);
    dut.decrypt = decrypt;
    dut.block_valid = 1;
    uint64_t start = cycles;
    while (!dut.block_ready) tick(dut);
    tick(dut);
    dut.block_valid = 0;
    while (!dut.block_out_valid) tick(dut);
    std::string observed = get_hex(dut.block_out);
    if (observed != expected) {
        std::fprintf(stderr, "%s AES %s mismatch: expected %s, got %s\n", kArchitecture,
                     decrypt ? "decrypt" : "encrypt", expected, observed.c_str());
        std::exit(1);
    }
    uint64_t latency = cycles - start;
    dut.block_out_ready = 1;
    tick(dut);
    dut.block_out_ready = 0;
    return latency;
}

int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    Dut dut;
    dut.rst = 1;
    dut.zeroize = 0;
    dut.key_valid = 0;
    dut.block_valid = 0;
    dut.block_out_ready = 0;
    tick(dut);
    tick(dut);
    dut.rst = 0;

    uint64_t key_cycles = 0;
    uint64_t encrypt_cycles = 0;
    uint64_t decrypt_cycles = 0;
    for (const auto &vector : kPrimitiveVectors) {
        key_cycles += load_key(dut, vector.key);
        encrypt_cycles += run_block(dut, vector.plaintext, false, vector.ciphertext);
        decrypt_cycles += run_block(dut, vector.ciphertext, true, vector.plaintext);
    }

    dut.zeroize = 1;
    tick(dut);
    dut.zeroize = 0;
    if (dut.key_loaded || dut.block_out_valid) {
        std::fprintf(stderr, "%s zeroize failed\n", kArchitecture);
        return 1;
    }
    std::printf("primitive RTL: PASS architecture=%s vectors=%zu key_setup_cycles=%llu aes_encrypt_cycles=%llu aes_decrypt_cycles=%llu\n",
                kArchitecture, sizeof(kPrimitiveVectors) / sizeof(kPrimitiveVectors[0]),
                static_cast<unsigned long long>(key_cycles / 5),
                static_cast<unsigned long long>(encrypt_cycles / 5),
                static_cast<unsigned long long>(decrypt_cycles / 5));
    return 0;
}
