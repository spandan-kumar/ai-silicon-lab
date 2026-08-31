#!/usr/bin/env python3
"""Independent AES-256-GCM reference model.

Written directly from the normative descriptions:

* NIST FIPS 197 (AES): SubBytes/ShiftRows/MixColumns/AddRoundKey and the
  256-bit key schedule.
* NIST SP 800-38D (GCM): GHASH over GF(2^128) with the reversed-bit
  convention, GCTR counter mode, J0 derivation for 96-bit and other IV
  lengths, and tag formation.

This model exists to be the oracle. It therefore uses no cryptographic
library: the S-box, the field multiply, and the mode logic are all built here
so that agreement with the candidate RTL is agreement between two independent
constructions rather than two calls into the same third-party code.

It is a correctness reference only. It is written for clarity and is not
constant-time; nothing here supports a side-channel claim.
"""

from __future__ import annotations

# --- FIPS 197 tables ------------------------------------------------------

SBOX = bytes.fromhex(
    "637c777bf26b6fc53001672bfed7ab76"
    "ca82c97dfa5947f0add4a2af9ca472c0"
    "b7fd9326363ff7cc34a5e5f171d83115"
    "04c723c31896059a071280e2eb27b275"
    "09832c1a1b6e5aa0523bd6b329e32f84"
    "53d100ed20fcb15b6acbbe394a4c58cf"
    "d0efaafb434d338545f9027f503c9fa8"
    "51a3408f929d38f5bcb6da2110fff3d2"
    "cd0c13ec5f974417c4a77e3d645d1973"
    "60814fdc222a908846eeb814de5e0bdb"
    "e0323a0a4906245cc2d3ac629195e479"
    "e7c8376d8dd54ea96c56f4ea657aae08"
    "ba78252e1ca6b4c6e8dd741f4bbd8b8a"
    "703eb5664803f60e613557b986c11d9e"
    "e1f8981169d98e949b1e87e9ce5528df"
    "8ca1890dbfe6426841992d0fb054bb16"
)

RCON = (0x01, 0x02, 0x04, 0x08, 0x10, 0x20, 0x40, 0x80, 0x1B, 0x36)


def xtime(value: int) -> int:
    value <<= 1
    return (value ^ 0x1B) & 0xFF if value & 0x100 else value


def gf_mul(a: int, b: int) -> int:
    """Multiply in GF(2^8) with the AES polynomial, for MixColumns."""
    result = 0
    for _ in range(8):
        if b & 1:
            result ^= a
        b >>= 1
        a = xtime(a)
    return result


def key_expansion_256(key: bytes) -> list[bytes]:
    """FIPS 197 key expansion for Nk=8, Nr=14: 15 round keys of 16 bytes."""
    if len(key) != 32:
        raise ValueError("AES-256 requires a 32-byte key")
    words = [list(key[i : i + 4]) for i in range(0, 32, 4)]
    for i in range(8, 60):
        temp = list(words[i - 1])
        if i % 8 == 0:
            temp = temp[1:] + temp[:1]
            temp = [SBOX[b] for b in temp]
            temp[0] ^= RCON[i // 8 - 1]
        elif i % 8 == 4:
            temp = [SBOX[b] for b in temp]
        words.append([words[i - 8][j] ^ temp[j] for j in range(4)])
    return [bytes(b for word in words[r * 4 : r * 4 + 4] for b in word) for r in range(15)]


def _sub_shift(state: list[int]) -> list[int]:
    """SubBytes then ShiftRows on a column-major AES state."""
    substituted = [SBOX[b] for b in state]
    # Column-major index c*4 + r; ShiftRows rotates row r left by r columns.
    return [substituted[((c + r) % 4) * 4 + r] for c in range(4) for r in range(4)]


def _mix_columns(state: list[int]) -> list[int]:
    out: list[int] = []
    for c in range(4):
        col = state[c * 4 : c * 4 + 4]
        out.extend(
            [
                gf_mul(col[0], 2) ^ gf_mul(col[1], 3) ^ col[2] ^ col[3],
                col[0] ^ gf_mul(col[1], 2) ^ gf_mul(col[2], 3) ^ col[3],
                col[0] ^ col[1] ^ gf_mul(col[2], 2) ^ gf_mul(col[3], 3),
                gf_mul(col[0], 3) ^ col[1] ^ col[2] ^ gf_mul(col[3], 2),
            ]
        )
    return out


def aes256_encrypt_block(round_keys: list[bytes], block: bytes) -> bytes:
    """AES-256 encryption of one 128-bit block. GCM never needs decryption."""
    if len(block) != 16:
        raise ValueError("AES operates on 16-byte blocks")
    state = [block[i] ^ round_keys[0][i] for i in range(16)]
    for round_index in range(1, 14):
        state = _mix_columns(_sub_shift(state))
        state = [state[i] ^ round_keys[round_index][i] for i in range(16)]
    state = _sub_shift(state)
    return bytes(state[i] ^ round_keys[14][i] for i in range(16))


# --- SP 800-38D GF(2^128) -------------------------------------------------

R = 0xE1 << 120


def gf128_mul(x: int, y: int) -> int:
    """The GCM field multiply, using the specification's bit ordering.

    Bit 0 of the specification is the most significant bit of the integer, so
    the reduction polynomial appears as 0xE1 in the top byte and the shift is
    to the right.
    """
    z = 0
    v = y
    for i in range(128):
        if (x >> (127 - i)) & 1:
            z ^= v
        if v & 1:
            v = (v >> 1) ^ R
        else:
            v >>= 1
    return z


def _to_int(block: bytes) -> int:
    return int.from_bytes(block, "big")


def _to_bytes(value: int) -> bytes:
    return value.to_bytes(16, "big")


def ghash(h: int, data: bytes) -> int:
    """GHASH over zero-padded data. The caller supplies the framing."""
    y = 0
    for offset in range(0, len(data), 16):
        block = data[offset : offset + 16]
        if len(block) < 16:
            block = block + b"\x00" * (16 - len(block))
        y = gf128_mul(y ^ _to_int(block), h)
    return y


def _pad16(data: bytes) -> bytes:
    remainder = len(data) % 16
    return data if remainder == 0 else data + b"\x00" * (16 - remainder)


def _inc32(block: bytes) -> bytes:
    counter = (int.from_bytes(block[12:], "big") + 1) & 0xFFFFFFFF
    return block[:12] + counter.to_bytes(4, "big")


def _gctr(round_keys: list[bytes], icb: bytes, data: bytes) -> bytes:
    if not data:
        return b""
    out = bytearray()
    counter = icb
    for offset in range(0, len(data), 16):
        chunk = data[offset : offset + 16]
        keystream = aes256_encrypt_block(round_keys, counter)
        out.extend(a ^ b for a, b in zip(chunk, keystream))
        counter = _inc32(counter)
    return bytes(out)


def derive_j0(h: int, iv: bytes) -> bytes:
    """J0 per SP 800-38D: the 96-bit fast path, or GHASH for other lengths."""
    if len(iv) == 12:
        return iv + b"\x00\x00\x00\x01"
    padded = _pad16(iv) + b"\x00" * 8 + (len(iv) * 8).to_bytes(8, "big")
    return _to_bytes(ghash(h, padded))


def _tag(round_keys: list[bytes], h: int, j0: bytes, aad: bytes, text: bytes) -> bytes:
    lengths = (len(aad) * 8).to_bytes(8, "big") + (len(text) * 8).to_bytes(8, "big")
    s = ghash(h, _pad16(aad) + _pad16(text) + lengths)
    return _gctr(round_keys, j0, _to_bytes(s))


def encrypt(key: bytes, iv: bytes, aad: bytes, plaintext: bytes, tag_bytes: int = 16):
    """Return (ciphertext, tag). Tag truncation keeps the leftmost bytes."""
    if not 1 <= tag_bytes <= 16:
        raise ValueError("tag length must be 1..16 bytes")
    round_keys = key_expansion_256(key)
    h = _to_int(aes256_encrypt_block(round_keys, b"\x00" * 16))
    j0 = derive_j0(h, iv)
    ciphertext = _gctr(round_keys, _inc32(j0), plaintext)
    tag = _tag(round_keys, h, j0, aad, ciphertext)
    return ciphertext, tag[:tag_bytes]


def decrypt(key: bytes, iv: bytes, aad: bytes, ciphertext: bytes, tag: bytes):
    """Return (plaintext_or_None, tag_ok).

    Plaintext is released only when the tag verifies. That is the profile this
    experiment freezes, and it is the behaviour the RTL must match.
    """
    round_keys = key_expansion_256(key)
    h = _to_int(aes256_encrypt_block(round_keys, b"\x00" * 16))
    j0 = derive_j0(h, iv)
    expected = _tag(round_keys, h, j0, aad, ciphertext)[: len(tag)]
    ok = expected == tag
    if not ok:
        return None, False
    return _gctr(round_keys, _inc32(j0), ciphertext), True
