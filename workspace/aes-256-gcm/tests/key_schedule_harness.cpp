#include <verilated.h>
#include "Vaes256_key_schedule_probe.h"

#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <string>

#include "primitive_vectors.h"

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

int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    Vaes256_key_schedule_probe dut;
    for (const auto &vector : kPrimitiveVectors) {
        set_hex(dut.key_in, vector.key);
        dut.eval();
        std::string observed = get_hex(dut.round_keys_flat);
        if (observed != vector.round_keys) {
            std::fprintf(stderr, "AES-256 key schedule mismatch for key %s\n", vector.key);
            return 1;
        }
    }
    std::printf("key schedule RTL: PASS vectors=%zu round_keys_per_vector=15\n",
                sizeof(kPrimitiveVectors) / sizeof(kPrimitiveVectors[0]));
    return 0;
}
