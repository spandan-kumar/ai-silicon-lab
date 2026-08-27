#ifndef AISL_SHA256_H
#define AISL_SHA256_H

#include <array>
#include <cstddef>
#include <cstdint>
#include <iomanip>
#include <sstream>
#include <string>

class Sha256 {
public:
    Sha256()
        : state_{0x6a09e667u, 0xbb67ae85u, 0x3c6ef372u, 0xa54ff53au,
                 0x510e527fu, 0x9b05688cu, 0x1f83d9abu, 0x5be0cd19u} {}

    void update(const void* input, std::size_t length) {
        const auto* bytes = static_cast<const std::uint8_t*>(input);
        total_bytes_ += length;
        while (length != 0) {
            const std::size_t room = block_.size() - block_used_;
            const std::size_t count = length < room ? length : room;
            for (std::size_t i = 0; i < count; ++i) {
                block_[block_used_ + i] = bytes[i];
            }
            block_used_ += count;
            bytes += count;
            length -= count;
            if (block_used_ == block_.size()) {
                transform();
                block_used_ = 0;
            }
        }
    }

    void update(const std::string& value) { update(value.data(), value.size()); }

    std::string hex_digest() const {
        Sha256 copy = *this;
        const auto digest = copy.finish();
        std::ostringstream out;
        out << std::hex << std::setfill('0');
        for (std::uint8_t byte : digest) {
            out << std::setw(2) << static_cast<unsigned>(byte);
        }
        return out.str();
    }

private:
    static constexpr std::array<std::uint32_t, 64> constants_ = {
        0x428a2f98u, 0x71374491u, 0xb5c0fbcfu, 0xe9b5dba5u,
        0x3956c25bu, 0x59f111f1u, 0x923f82a4u, 0xab1c5ed5u,
        0xd807aa98u, 0x12835b01u, 0x243185beu, 0x550c7dc3u,
        0x72be5d74u, 0x80deb1feu, 0x9bdc06a7u, 0xc19bf174u,
        0xe49b69c1u, 0xefbe4786u, 0x0fc19dc6u, 0x240ca1ccu,
        0x2de92c6fu, 0x4a7484aau, 0x5cb0a9dcu, 0x76f988dau,
        0x983e5152u, 0xa831c66du, 0xb00327c8u, 0xbf597fc7u,
        0xc6e00bf3u, 0xd5a79147u, 0x06ca6351u, 0x14292967u,
        0x27b70a85u, 0x2e1b2138u, 0x4d2c6dfcu, 0x53380d13u,
        0x650a7354u, 0x766a0abbu, 0x81c2c92eu, 0x92722c85u,
        0xa2bfe8a1u, 0xa81a664bu, 0xc24b8b70u, 0xc76c51a3u,
        0xd192e819u, 0xd6990624u, 0xf40e3585u, 0x106aa070u,
        0x19a4c116u, 0x1e376c08u, 0x2748774cu, 0x34b0bcb5u,
        0x391c0cb3u, 0x4ed8aa4au, 0x5b9cca4fu, 0x682e6ff3u,
        0x748f82eeu, 0x78a5636fu, 0x84c87814u, 0x8cc70208u,
        0x90befffau, 0xa4506cebu, 0xbef9a3f7u, 0xc67178f2u,
    };

    static std::uint32_t rotate_right(std::uint32_t value, unsigned amount) {
        return (value >> amount) | (value << (32u - amount));
    }

    void transform() {
        std::array<std::uint32_t, 64> words{};
        for (std::size_t i = 0; i < 16; ++i) {
            const std::size_t p = i * 4;
            words[i] = (static_cast<std::uint32_t>(block_[p]) << 24) |
                       (static_cast<std::uint32_t>(block_[p + 1]) << 16) |
                       (static_cast<std::uint32_t>(block_[p + 2]) << 8) |
                       static_cast<std::uint32_t>(block_[p + 3]);
        }
        for (std::size_t i = 16; i < words.size(); ++i) {
            const std::uint32_t s0 = rotate_right(words[i - 15], 7) ^
                                     rotate_right(words[i - 15], 18) ^
                                     (words[i - 15] >> 3);
            const std::uint32_t s1 = rotate_right(words[i - 2], 17) ^
                                     rotate_right(words[i - 2], 19) ^
                                     (words[i - 2] >> 10);
            words[i] = words[i - 16] + s0 + words[i - 7] + s1;
        }

        std::uint32_t a = state_[0];
        std::uint32_t b = state_[1];
        std::uint32_t c = state_[2];
        std::uint32_t d = state_[3];
        std::uint32_t e = state_[4];
        std::uint32_t f = state_[5];
        std::uint32_t g = state_[6];
        std::uint32_t h = state_[7];

        for (std::size_t i = 0; i < words.size(); ++i) {
            const std::uint32_t sum1 = rotate_right(e, 6) ^ rotate_right(e, 11) ^ rotate_right(e, 25);
            const std::uint32_t choose = (e & f) ^ (~e & g);
            const std::uint32_t temp1 = h + sum1 + choose + constants_[i] + words[i];
            const std::uint32_t sum0 = rotate_right(a, 2) ^ rotate_right(a, 13) ^ rotate_right(a, 22);
            const std::uint32_t majority = (a & b) ^ (a & c) ^ (b & c);
            const std::uint32_t temp2 = sum0 + majority;
            h = g;
            g = f;
            f = e;
            e = d + temp1;
            d = c;
            c = b;
            b = a;
            a = temp1 + temp2;
        }

        state_[0] += a;
        state_[1] += b;
        state_[2] += c;
        state_[3] += d;
        state_[4] += e;
        state_[5] += f;
        state_[6] += g;
        state_[7] += h;
    }

    std::array<std::uint8_t, 32> finish() {
        const std::uint64_t bit_length = total_bytes_ * 8u;
        const std::uint8_t marker = 0x80;
        const std::uint8_t zero = 0;
        update(&marker, 1);
        while (block_used_ != 56) {
            update(&zero, 1);
        }
        std::array<std::uint8_t, 8> length_bytes{};
        for (std::size_t i = 0; i < length_bytes.size(); ++i) {
            length_bytes[7 - i] = static_cast<std::uint8_t>(bit_length >> (i * 8));
        }
        update(length_bytes.data(), length_bytes.size());

        std::array<std::uint8_t, 32> digest{};
        for (std::size_t i = 0; i < state_.size(); ++i) {
            digest[i * 4] = static_cast<std::uint8_t>(state_[i] >> 24);
            digest[i * 4 + 1] = static_cast<std::uint8_t>(state_[i] >> 16);
            digest[i * 4 + 2] = static_cast<std::uint8_t>(state_[i] >> 8);
            digest[i * 4 + 3] = static_cast<std::uint8_t>(state_[i]);
        }
        return digest;
    }

    std::array<std::uint32_t, 8> state_;
    std::array<std::uint8_t, 64> block_{};
    std::size_t block_used_ = 0;
    std::uint64_t total_bytes_ = 0;
};

#endif
