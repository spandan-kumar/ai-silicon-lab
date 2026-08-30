"""Dependency-free AES-256 and GCM reference model.

This is intentionally straightforward code for vector generation and
cross-checking. It is never linked into or called by the RTL simulation path.
"""

from __future__ import annotations

import hmac


SBOX = (
    0x63, 0x7C, 0x77, 0x7B, 0xF2, 0x6B, 0x6F, 0xC5, 0x30, 0x01, 0x67, 0x2B, 0xFE, 0xD7, 0xAB, 0x76,
    0xCA, 0x82, 0xC9, 0x7D, 0xFA, 0x59, 0x47, 0xF0, 0xAD, 0xD4, 0xA2, 0xAF, 0x9C, 0xA4, 0x72, 0xC0,
    0xB7, 0xFD, 0x93, 0x26, 0x36, 0x3F, 0xF7, 0xCC, 0x34, 0xA5, 0xE5, 0xF1, 0x71, 0xD8, 0x31, 0x15,
    0x04, 0xC7, 0x23, 0xC3, 0x18, 0x96, 0x05, 0x9A, 0x07, 0x12, 0x80, 0xE2, 0xEB, 0x27, 0xB2, 0x75,
    0x09, 0x83, 0x2C, 0x1A, 0x1B, 0x6E, 0x5A, 0xA0, 0x52, 0x3B, 0xD6, 0xB3, 0x29, 0xE3, 0x2F, 0x84,
    0x53, 0xD1, 0x00, 0xED, 0x20, 0xFC, 0xB1, 0x5B, 0x6A, 0xCB, 0xBE, 0x39, 0x4A, 0x4C, 0x58, 0xCF,
    0xD0, 0xEF, 0xAA, 0xFB, 0x43, 0x4D, 0x33, 0x85, 0x45, 0xF9, 0x02, 0x7F, 0x50, 0x3C, 0x9F, 0xA8,
    0x51, 0xA3, 0x40, 0x8F, 0x92, 0x9D, 0x38, 0xF5, 0xBC, 0xB6, 0xDA, 0x21, 0x10, 0xFF, 0xF3, 0xD2,
    0xCD, 0x0C, 0x13, 0xEC, 0x5F, 0x97, 0x44, 0x17, 0xC4, 0xA7, 0x7E, 0x3D, 0x64, 0x5D, 0x19, 0x73,
    0x60, 0x81, 0x4F, 0xDC, 0x22, 0x2A, 0x90, 0x88, 0x46, 0xEE, 0xB8, 0x14, 0xDE, 0x5E, 0x0B, 0xDB,
    0xE0, 0x32, 0x3A, 0x0A, 0x49, 0x06, 0x24, 0x5C, 0xC2, 0xD3, 0xAC, 0x62, 0x91, 0x95, 0xE4, 0x79,
    0xE7, 0xC8, 0x37, 0x6D, 0x8D, 0xD5, 0x4E, 0xA9, 0x6C, 0x56, 0xF4, 0xEA, 0x65, 0x7A, 0xAE, 0x08,
    0xBA, 0x78, 0x25, 0x2E, 0x1C, 0xA6, 0xB4, 0xC6, 0xE8, 0xDD, 0x74, 0x1F, 0x4B, 0xBD, 0x8B, 0x8A,
    0x70, 0x3E, 0xB5, 0x66, 0x48, 0x03, 0xF6, 0x0E, 0x61, 0x35, 0x57, 0xB9, 0x86, 0xC1, 0x1D, 0x9E,
    0xE1, 0xF8, 0x98, 0x11, 0x69, 0xD9, 0x8E, 0x94, 0x9B, 0x1E, 0x87, 0xE9, 0xCE, 0x55, 0x28, 0xDF,
    0x8C, 0xA1, 0x89, 0x0D, 0xBF, 0xE6, 0x42, 0x68, 0x41, 0x99, 0x2D, 0x0F, 0xB0, 0x54, 0xBB, 0x16,
)

INV_SBOX = tuple(SBOX.index(i) for i in range(256))
RCON = (0x00, 0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40)


def _xor(a: bytes, b: bytes) -> bytes:
    if len(a) != len(b):
        raise ValueError("XOR inputs must have equal length")
    return bytes(x ^ y for x, y in zip(a, b))


def _xtime(value: int) -> int:
    return ((value << 1) ^ (0x11B if value & 0x80 else 0)) & 0xFF


def _gf8_mul(a: int, b: int) -> int:
    result = 0
    for _ in range(8):
        if b & 1:
            result ^= a
        a = _xtime(a)
        b >>= 1
    return result


def expand_key(key: bytes) -> tuple[bytes, ...]:
    """Return the 15 round keys for one 256-bit AES key."""
    if len(key) != 32:
        raise ValueError("AES-256 requires a 32-byte key")
    words = [list(key[i : i + 4]) for i in range(0, 32, 4)]
    for i in range(8, 60):
        temp = words[i - 1].copy()
        if i % 8 == 0:
            temp = [SBOX[temp[1]] ^ RCON[i // 8], SBOX[temp[2]], SBOX[temp[3]], SBOX[temp[0]]]
        elif i % 8 == 4:
            temp = [SBOX[x] for x in temp]
        words.append([words[i - 8][j] ^ temp[j] for j in range(4)])
    return tuple(bytes(sum(words[4 * r : 4 * r + 4], [])) for r in range(15))


def _shift_rows(state: list[int], inverse: bool = False) -> list[int]:
    direction = -1 if inverse else 1
    return [state[r + 4 * ((c + direction * r) % 4)] for c in range(4) for r in range(4)]


def _mix_columns(state: list[int], inverse: bool = False) -> list[int]:
    matrix = ((14, 11, 13, 9), (9, 14, 11, 13), (13, 9, 14, 11), (11, 13, 9, 14)) if inverse else (
        (2, 3, 1, 1), (1, 2, 3, 1), (1, 1, 2, 3), (3, 1, 1, 2)
    )
    output: list[int] = []
    for column in range(4):
        source = state[4 * column : 4 * column + 4]
        for row in range(4):
            value = 0
            for i in range(4):
                value ^= _gf8_mul(matrix[row][i], source[i])
            output.append(value)
    return output


def aes256_encrypt_block(key: bytes, block: bytes) -> bytes:
    if len(block) != 16:
        raise ValueError("AES operates on a 16-byte block")
    round_keys = expand_key(key)
    state = list(_xor(block, round_keys[0]))
    for round_index in range(1, 14):
        state = [SBOX[x] for x in state]
        state = _shift_rows(state)
        state = _mix_columns(state)
        state = list(_xor(bytes(state), round_keys[round_index]))
    state = _shift_rows([SBOX[x] for x in state])
    return _xor(bytes(state), round_keys[14])


def aes256_decrypt_block(key: bytes, block: bytes) -> bytes:
    if len(block) != 16:
        raise ValueError("AES operates on a 16-byte block")
    round_keys = expand_key(key)
    state = list(_xor(block, round_keys[14]))
    for round_index in range(13, 0, -1):
        state = [INV_SBOX[x] for x in _shift_rows(state, inverse=True)]
        state = list(_xor(bytes(state), round_keys[round_index]))
        state = _mix_columns(state, inverse=True)
    state = [INV_SBOX[x] for x in _shift_rows(state, inverse=True)]
    return _xor(bytes(state), round_keys[0])


def gf128_mul(x: int, y: int) -> int:
    """SP 800-38D Algorithm 1 multiplication in the GHASH field."""
    z = 0
    v = y
    for bit_index in range(128):
        if x & (1 << (127 - bit_index)):
            z ^= v
        v = (v >> 1) ^ (0xE1000000000000000000000000000000 if v & 1 else 0)
    return z


def _blocks(data: bytes):
    for offset in range(0, len(data), 16):
        yield data[offset : offset + 16].ljust(16, b"\0")


def ghash(hash_subkey: bytes, aad: bytes, ciphertext: bytes) -> bytes:
    h = int.from_bytes(hash_subkey, "big")
    y = 0
    for block in _blocks(aad):
        y = gf128_mul(y ^ int.from_bytes(block, "big"), h)
    for block in _blocks(ciphertext):
        y = gf128_mul(y ^ int.from_bytes(block, "big"), h)
    lengths = (len(aad) * 8).to_bytes(8, "big") + (len(ciphertext) * 8).to_bytes(8, "big")
    y = gf128_mul(y ^ int.from_bytes(lengths, "big"), h)
    return y.to_bytes(16, "big")


def _j0(key: bytes, iv: bytes) -> bytes:
    h = aes256_encrypt_block(key, bytes(16))
    if len(iv) == 12:
        return iv + b"\0\0\0\x01"
    padded_length = ((len(iv) + 15) // 16) * 16
    encoded = iv.ljust(padded_length, b"\0") + bytes(8) + (len(iv) * 8).to_bytes(8, "big")
    y = 0
    h_int = int.from_bytes(h, "big")
    for block in _blocks(encoded):
        y = gf128_mul(y ^ int.from_bytes(block, "big"), h_int)
    return y.to_bytes(16, "big")


def _inc32(counter: bytes) -> bytes:
    return counter[:12] + ((int.from_bytes(counter[12:], "big") + 1) & 0xFFFFFFFF).to_bytes(4, "big")


def _gctr(key: bytes, initial_counter: bytes, data: bytes) -> bytes:
    counter = initial_counter
    output = bytearray()
    for offset in range(0, len(data), 16):
        chunk = data[offset : offset + 16]
        output.extend(_xor(chunk, aes256_encrypt_block(key, counter)[: len(chunk)]))
        counter = _inc32(counter)
    return bytes(output)


def encrypt(key: bytes, iv: bytes, plaintext: bytes, aad: bytes = b"") -> tuple[bytes, bytes]:
    j0 = _j0(key, iv)
    ciphertext = _gctr(key, _inc32(j0), plaintext)
    h = aes256_encrypt_block(key, bytes(16))
    tag = _xor(aes256_encrypt_block(key, j0), ghash(h, aad, ciphertext))
    return ciphertext, tag


def decrypt(key: bytes, iv: bytes, ciphertext: bytes, tag: bytes, aad: bytes = b"") -> bytes | None:
    if len(tag) != 16:
        raise ValueError("the frozen profile requires a 16-byte tag")
    j0 = _j0(key, iv)
    h = aes256_encrypt_block(key, bytes(16))
    expected = _xor(aes256_encrypt_block(key, j0), ghash(h, aad, ciphertext))
    if not hmac.compare_digest(expected, tag):
        return None
    return _gctr(key, _inc32(j0), ciphertext)
