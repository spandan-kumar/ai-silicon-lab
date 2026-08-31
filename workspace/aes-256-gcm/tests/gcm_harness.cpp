#include <verilated.h>
#include "Vaes_gcm_core.h"

#include <cstdint>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <map>
#include <string>
#include <vector>

#include "gcm_vectors.h"

using Dut = Vaes_gcm_core;

#ifdef ITERATIVE
static constexpr const char *kArchitecture = "iterative-1r1b";
#elif defined(BALANCED)
static constexpr const char *kArchitecture = "balanced-1r8b";
#elif defined(WIDE)
static constexpr const char *kArchitecture = "wide-2r16b";
#elif defined(ULTRAWIDE)
static constexpr const char *kArchitecture = "ultrawide-2r32b";
#elif defined(BALANCED_WIDE)
static constexpr const char *kArchitecture = "balanced-wide-1r16b";
#elif defined(BALANCED_ULTRAWIDE)
static constexpr const char *kArchitecture = "balanced-ultrawide-1r32b";
#elif defined(BALANCED_XWIDE)
static constexpr const char *kArchitecture = "balanced-xwide-1r64b";
#else
static constexpr const char *kArchitecture = "unrolled-2r8b";
#endif

static uint64_t global_cycles = 0;
static uint32_t stall_prng = 0x6a09e667u;
static bool transaction_active = false;

struct Result {
    std::vector<uint8_t> output;
    std::string tag;
    uint8_t status;
    bool auth;
    uint32_t cycles;
    uint32_t stalls;
};

static int nibble(char value) {
    if (value >= '0' && value <= '9') return value - '0';
    if (value >= 'a' && value <= 'f') return value - 'a' + 10;
    return value - 'A' + 10;
}

static std::vector<uint8_t> decode_hex(const char *text) {
    size_t length = std::strlen(text);
    if (length & 1u) std::abort();
    std::vector<uint8_t> result(length / 2);
    for (size_t i = 0; i < result.size(); ++i)
        result[i] = static_cast<uint8_t>((nibble(text[2*i]) << 4) | nibble(text[2*i + 1]));
    return result;
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
    ++global_cycles;
    if (!dut.rst && transaction_active && (dut.cmd_ready || dut.key_ready)) {
        std::fprintf(stderr, "%s accepted interleaving while a transaction was active\n",
                     kArchitecture);
        std::exit(1);
    }
}

static void reset(Dut &dut) {
    transaction_active = false;
    dut.rst = 1;
    dut.zeroize = 0;
    dut.key_valid = 0;
    dut.cmd_valid = 0;
    dut.in_valid = 0;
    dut.tag_in_valid = 0;
    dut.out_ready = 0;
    dut.result_ready = 0;
    tick(dut);
    tick(dut);
    dut.rst = 0;
    tick(dut);
}

static uint32_t next_random(void) {
    stall_prng ^= stall_prng << 13;
    stall_prng ^= stall_prng >> 17;
    stall_prng ^= stall_prng << 5;
    return stall_prng;
}

static uint32_t load_key(Dut &dut, const char *key) {
    uint64_t deadline = global_cycles + 1000;
    while (!dut.key_ready && global_cycles < deadline) tick(dut);
    if (!dut.key_ready) std::abort();
    uint64_t start = global_cycles;
    set_hex(dut.key_in, key);
    dut.key_valid = 1;
    tick(dut);
    dut.key_valid = 0;
    while (!dut.key_loaded && global_cycles < deadline) tick(dut);
    if (!dut.key_loaded) std::abort();
    return static_cast<uint32_t>(global_cycles - start);
}

static void send_command(Dut &dut, bool encrypting, size_t iv, size_t aad, size_t data) {
    uint64_t deadline = global_cycles + 1000;
    while (!dut.cmd_ready && global_cycles < deadline) tick(dut);
    if (!dut.cmd_ready) std::abort();
    dut.cmd_encrypt = encrypting;
    dut.cmd_iv_bytes = static_cast<uint8_t>(iv);
    dut.cmd_aad_bytes = static_cast<uint8_t>(aad);
    dut.cmd_data_bytes = static_cast<uint8_t>(data);
    dut.cmd_valid = 1;
    tick(dut);
    dut.cmd_valid = 0;
    transaction_active = true;
}

static void send_bytes(Dut &dut, const std::vector<uint8_t> &bytes, bool stress) {
    for (uint8_t byte : bytes) {
        if (stress && (next_random() & 3u) == 0) {
            dut.in_valid = 0;
            tick(dut);
        }
        uint64_t deadline = global_cycles + 1000;
        while (!dut.in_ready && global_cycles < deadline) tick(dut);
        if (!dut.in_ready) std::abort();
        if (dut.tag_in_ready || dut.out_valid || dut.result_valid) {
            std::fprintf(stderr, "%s exposed a second channel during serialized input\n",
                         kArchitecture);
            std::exit(1);
        }
        dut.in_data = byte;
        dut.in_valid = 1;
        tick(dut);
        dut.in_valid = 0;
    }
}

static void send_tag(Dut &dut, const char *tag, bool stress) {
    if (stress) {
        dut.tag_in_valid = 0;
        tick(dut);
    }
    uint64_t deadline = global_cycles + 1000;
    while (!dut.tag_in_ready && global_cycles < deadline) tick(dut);
    if (!dut.tag_in_ready) std::abort();
    if (dut.in_ready || dut.out_valid || dut.result_valid) {
        std::fprintf(stderr, "%s exposed a second channel during tag input\n", kArchitecture);
        std::exit(1);
    }
    set_hex(dut.tag_in, tag);
    dut.tag_in_valid = 1;
    tick(dut);
    dut.tag_in_valid = 0;
}

static Result wait_result(Dut &dut, bool stress) {
    Result result;
    uint64_t deadline = global_cycles + 20000;
    while (!dut.result_valid && global_cycles < deadline) {
        bool ready = !stress || (next_random() & 3u) != 0;
        dut.out_ready = ready;
        if (dut.out_valid && dut.out_ready) result.output.push_back(dut.out_data);
        tick(dut);
    }
    dut.out_ready = 0;
    if (!dut.result_valid) {
        std::fprintf(stderr, "%s timeout at cycle %llu\n", kArchitecture,
                     static_cast<unsigned long long>(global_cycles));
        std::exit(1);
    }
    result.tag = get_hex(dut.result_tag);
    result.status = dut.result_status;
    result.auth = dut.result_auth_ok;
    result.cycles = dut.result_cycles;
    result.stalls = dut.result_stall_cycles;
    transaction_active = false;
    dut.result_ready = 1;
    tick(dut);
    dut.result_ready = 0;
    return result;
}

static Result run_case(Dut &dut, const GcmVector &vector, bool stress, bool reload = true) {
    std::vector<uint8_t> iv = decode_hex(vector.iv);
    std::vector<uint8_t> aad = decode_hex(vector.aad);
    std::vector<uint8_t> input = decode_hex(vector.input);
    if (reload) load_key(dut, vector.key);
    send_command(dut, vector.encrypt, iv.size(), aad.size(), input.size());
    if (stress) {
        dut.in_valid = 0;
        tick(dut);
    }
    send_bytes(dut, iv, stress);
    send_bytes(dut, aad, stress);
    send_bytes(dut, input, stress);
    if (!vector.encrypt) send_tag(dut, vector.tag, stress);
    return wait_result(dut, stress);
}

static void verify_case(const GcmVector &vector, const Result &result) {
    std::vector<uint8_t> expected = decode_hex(vector.output);
    uint8_t expected_status = vector.auth ? 0 : 1;
    if (result.status != expected_status || result.auth != vector.auth || result.output != expected
        || (vector.encrypt && result.tag != vector.tag) || result.cycles == 0) {
        std::fprintf(stderr,
            "%s case %s failed: status=%u/%u auth=%u/%u output=%zu/%zu tag=%s/%s cycles=%u\n",
            kArchitecture, vector.id, result.status, expected_status, result.auth, vector.auth,
            result.output.size(), expected.size(), result.tag.c_str(), vector.tag, result.cycles);
        std::exit(1);
    }
}

static void expect_command_error(Dut &dut, bool encrypting, size_t iv, size_t aad,
                                 size_t data, uint8_t status) {
    send_command(dut, encrypting, iv, aad, data);
    Result result = wait_result(dut, false);
    if (result.status != status || result.auth || !result.output.empty()) {
        std::fprintf(stderr, "%s command error mismatch: got %u expected %u\n",
                     kArchitecture, result.status, status);
        std::exit(1);
    }
}

static void expect_cleared(Dut &dut, const char *phase) {
    if (dut.key_loaded || dut.result_valid || dut.out_valid || dut.in_ready
        || dut.tag_in_ready) {
        std::fprintf(stderr, "%s reset/zeroize failed during %s\n", kArchitecture, phase);
        std::exit(1);
    }
}

static void reset_phase_tests(Dut &dut) {
    const GcmVector &encrypt = kPerformanceVectors[2];
    const GcmVector &decrypt = kPerformanceVectors[3];
    std::vector<uint8_t> iv = decode_hex(encrypt.iv);

    reset(dut);
    set_hex(dut.key_in, encrypt.key);
    dut.key_valid = 1;
    tick(dut);
    dut.key_valid = 0;
    dut.rst = 1;
    tick(dut);
    dut.rst = 0;
    tick(dut);
    expect_cleared(dut, "key setup");

    load_key(dut, encrypt.key);
    send_command(dut, true, iv.size(), 16, 0);
    send_bytes(dut, iv, false);
    dut.in_data = 0x5a;
    dut.in_valid = 1;
    tick(dut);
    dut.in_valid = 0;
    reset(dut);
    expect_cleared(dut, "AAD input");

    load_key(dut, encrypt.key);
    send_command(dut, true, iv.size(), 0, 16);
    send_bytes(dut, iv, false);
    dut.in_data = 0xa5;
    dut.in_valid = 1;
    tick(dut);
    dut.in_valid = 0;
    transaction_active = false;
    dut.zeroize = 1;
    tick(dut);
    dut.zeroize = 0;
    tick(dut);
    expect_cleared(dut, "payload input zeroize");

    load_key(dut, decrypt.key);
    send_command(dut, false, iv.size(), 0, 1);
    send_bytes(dut, iv, false);
    send_bytes(dut, decode_hex(decrypt.input), false);
    if (!dut.tag_in_ready) {
        std::fprintf(stderr, "%s did not reach tag phase\n", kArchitecture);
        std::exit(1);
    }
    reset(dut);
    expect_cleared(dut, "tag input");

    load_key(dut, encrypt.key);
    send_command(dut, true, iv.size(), 0, 1);
    send_bytes(dut, iv, false);
    send_bytes(dut, decode_hex(encrypt.input), false);
    while (!dut.out_valid) tick(dut);
    reset(dut);
    expect_cleared(dut, "output");

    load_key(dut, kPerformanceVectors[0].key);
    send_command(dut, true, iv.size(), 0, 0);
    send_bytes(dut, iv, false);
    while (!dut.result_valid) tick(dut);
    reset(dut);
    expect_cleared(dut, "result");

    load_key(dut, encrypt.key);
    send_command(dut, true, 0, 0, 0);
    if (!dut.result_valid) tick(dut);
    reset(dut);
    expect_cleared(dut, "error result");
}

static void lifecycle_tests(Dut &dut) {
    reset_phase_tests(dut);
    reset(dut);
    expect_command_error(dut, true, 12, 0, 0, 3);
    load_key(dut, kGcmVectors[0].key);
    expect_command_error(dut, true, 0, 0, 0, 2);
    expect_command_error(dut, true, 2, 0, 0, 2);
    expect_command_error(dut, true, 12, 65, 0, 2);
    expect_command_error(dut, true, 12, 0, 65, 2);

    Result first = run_case(dut, kGcmVectors[0], false, false);
    verify_case(kGcmVectors[0], first);
    Result warm = run_case(dut, kGcmVectors[0], false, false);
    verify_case(kGcmVectors[0], warm);
    if (warm.cycles != first.cycles) {
        std::fprintf(stderr, "%s warm-key repeat changed cycle count\n", kArchitecture);
        std::exit(1);
    }

    load_key(dut, kGcmVectors[4].key);
    Result replacement = run_case(dut, kGcmVectors[4], true, false);
    verify_case(kGcmVectors[4], replacement);
    if (replacement.stalls == 0) {
        std::fprintf(stderr, "%s stress run did not observe stalls\n", kArchitecture);
        std::exit(1);
    }

    load_key(dut, kGcmVectors[8].key);
    std::vector<uint8_t> iv = decode_hex(kGcmVectors[8].iv);
    send_command(dut, kGcmVectors[8].encrypt, iv.size(), 0, 0);
    dut.in_data = iv[0];
    dut.in_valid = 1;
    tick(dut);
    dut.in_valid = 0;
    transaction_active = false;
    dut.rst = 1;
    tick(dut);
    dut.rst = 0;
    tick(dut);
    if (dut.key_loaded || dut.result_valid || dut.out_valid) {
        std::fprintf(stderr, "%s reset did not abort and clear state\n", kArchitecture);
        std::exit(1);
    }

    load_key(dut, kPerformanceVectors[0].key);
    GcmVector invalid = kPerformanceVectors[1];
    std::string bad_tag = invalid.tag;
    bad_tag[0] = bad_tag[0] == '0' ? '1' : '0';
    invalid.tag = bad_tag.c_str();
    invalid.auth = false;
    invalid.output = "";
    Result rejected = run_case(dut, invalid, false, false);
    verify_case(invalid, rejected);
    Result after_reject = run_case(dut, kPerformanceVectors[1], false, false);
    verify_case(kPerformanceVectors[1], after_reject);
    if (rejected.cycles != after_reject.cycles) {
        std::fprintf(stderr, "%s zero-payload tag verdict changed comparison latency\n", kArchitecture);
        std::exit(1);
    }

    invalid = kPerformanceVectors[15];
    bad_tag = invalid.tag;
    bad_tag[0] = bad_tag[0] == '0' ? '1' : '0';
    invalid.tag = bad_tag.c_str();
    invalid.auth = false;
    invalid.output = "";
    rejected = run_case(dut, invalid, false, false);
    verify_case(invalid, rejected);
    after_reject = run_case(dut, kPerformanceVectors[15], false, false);
    verify_case(kPerformanceVectors[15], after_reject);
    if (after_reject.cycles != rejected.cycles + 64) {
        std::fprintf(stderr, "%s tag verdict timing differs before authenticated output\n", kArchitecture);
        std::exit(1);
    }

    Result before_zeroize = run_case(dut, kPerformanceVectors[0], false, false);
    verify_case(kPerformanceVectors[0], before_zeroize);
    dut.zeroize = 1;
    tick(dut);
    dut.zeroize = 0;
    tick(dut);
    if (dut.key_loaded || dut.result_valid || dut.out_valid) {
        std::fprintf(stderr, "%s zeroize did not clear state\n", kArchitecture);
        std::exit(1);
    }
}

static void performance_tests(Dut &dut) {
    reset(dut);
    uint32_t key_setup_cycles = load_key(dut, kPerformanceVectors[0].key);
    for (const auto &vector : kPerformanceVectors) {
        Result result = run_case(dut, vector, false, false);
        verify_case(vector, result);
        size_t iv_bytes = std::strlen(vector.iv) / 2;
        size_t aad_bytes = std::strlen(vector.aad) / 2;
        size_t data_bytes = std::strlen(vector.input) / 2;
        if (data_bytes == 0) {
            std::printf(
                "METRIC architecture=%s case=%s mode=%s iv_bytes=%zu aad_bytes=%zu "
                "data_bytes=0 key_setup_cycles=%u warm_cycles=%u cold_cycles=%u "
                "bytes_per_cycle=null cycles_per_byte=null stalls=%u\n",
                kArchitecture, vector.id, vector.encrypt ? "encrypt" : "decrypt", iv_bytes,
                aad_bytes, key_setup_cycles, result.cycles,
                key_setup_cycles + result.cycles, result.stalls);
        } else {
            std::printf(
                "METRIC architecture=%s case=%s mode=%s iv_bytes=%zu aad_bytes=%zu "
                "data_bytes=%zu key_setup_cycles=%u warm_cycles=%u cold_cycles=%u "
                "bytes_per_cycle=%.9f cycles_per_byte=%.9f stalls=%u\n",
                kArchitecture, vector.id, vector.encrypt ? "encrypt" : "decrypt", iv_bytes,
                aad_bytes, data_bytes, key_setup_cycles, result.cycles,
                key_setup_cycles + result.cycles,
                static_cast<double>(data_bytes) / result.cycles,
                static_cast<double>(result.cycles) / data_bytes, result.stalls);
        }
    }
}

int main(int argc, char **argv) {
    Verilated::commandArgs(argc, argv);
    Dut dut;
    reset(dut);
    uint64_t operations = 0;
    uint64_t total_cycles = 0;
    uint32_t min_cycles = UINT32_MAX;
    uint32_t max_cycles = 0;
    size_t fixed_cycle_comparisons = 0;
    std::map<std::string, uint32_t> fixed_cycles;
    for (const auto &vector : kGcmVectors) {
        Result result = run_case(dut, vector, false);
        verify_case(vector, result);
        if (vector.auth) {
            std::string signature = std::string(vector.encrypt ? "encrypt:" : "decrypt:")
                + std::to_string(std::strlen(vector.iv) / 2) + ":"
                + std::to_string(std::strlen(vector.aad) / 2) + ":"
                + std::to_string(std::strlen(vector.input) / 2);
            auto inserted = fixed_cycles.emplace(signature, result.cycles);
            if (!inserted.second) {
                ++fixed_cycle_comparisons;
                if (inserted.first->second != result.cycles) {
                    std::fprintf(stderr, "%s secret-dependent cycle count for %s\n",
                                 kArchitecture, signature.c_str());
                    return 1;
                }
            }
        }
        ++operations;
        total_cycles += result.cycles;
        if (result.cycles < min_cycles) min_cycles = result.cycles;
        if (result.cycles > max_cycles) max_cycles = result.cycles;
    }

    for (size_t index = 0; index < 32; ++index) {
        Result result = run_case(dut, kGcmVectors[index * 7], true);
        verify_case(kGcmVectors[index * 7], result);
        if (result.stalls == 0) {
            std::fprintf(stderr, "%s stalled case recorded no stalls\n", kArchitecture);
            return 1;
        }
    }
    lifecycle_tests(dut);
    performance_tests(dut);
    std::printf(
        "GCM RTL: PASS architecture=%s corpus_operations=%llu stalled_replays=32 "
        "fixed_cycle_comparisons=%zu min_cycles=%u max_cycles=%u mean_cycles=%.3f "
        "total_sim_cycles=%llu\n",
        kArchitecture, static_cast<unsigned long long>(operations), fixed_cycle_comparisons,
        min_cycles, max_cycles, static_cast<double>(total_cycles) / operations,
        static_cast<unsigned long long>(global_cycles));
    return 0;
}
