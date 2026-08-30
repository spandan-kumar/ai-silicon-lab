#!/usr/bin/env python3
"""Known-answer and invariant tests for the dependency-free reference model."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))

from aes_gcm import aes256_decrypt_block, aes256_encrypt_block, decrypt, encrypt, expand_key


def from_hex(value: str) -> bytes:
    return bytes.fromhex(value)


def main() -> int:
    key = from_hex("603deb1015ca71be2b73aef0857d7781" "1f352c073b6108d72d9810a30914dff4")
    plaintext = from_hex("6bc1bee22e409f96e93d7e117393172a")
    ciphertext = from_hex("f3eed1bdb5d2a03c064b5a7e3db181f8")
    assert aes256_encrypt_block(key, plaintext) == ciphertext
    assert aes256_decrypt_block(key, ciphertext) == plaintext

    round_keys = expand_key(key)
    assert round_keys[2] == from_hex("9ba354118e6925afa51a8b5f2067fcde")
    assert round_keys[3] == from_hex("a8b09c1a93d194cdbe49846eb75d5b9a")

    cavp_key = from_hex("b52c505a37d78eda5dd34f20c22540ea1b58963cf8e5bf8ffa85f9f2492505b4")
    cavp_iv = from_hex("516c33929df5a3284ff463d7")
    ct, tag = encrypt(cavp_key, cavp_iv, b"", b"")
    assert ct == b""
    assert tag == from_hex("bdc1ac884d332457a1d2664f168c76f0")
    assert decrypt(cavp_key, cavp_iv, ct, tag, b"") == b""

    zero_key = bytes(32)
    zero_iv = bytes(12)
    zero_ct, zero_tag = encrypt(zero_key, zero_iv, bytes(16), b"")
    assert zero_ct == from_hex("cea7403d4d606b6e074ec5d3baf39d18")
    assert zero_tag == from_hex("d0d1c8a799996bf0265b98b5d48ab919")
    assert decrypt(zero_key, zero_iv, zero_ct, zero_tag, b"") == bytes(16)
    corrupt_tag = zero_tag[:-1] + bytes([zero_tag[-1] ^ 1])
    assert decrypt(zero_key, zero_iv, zero_ct, corrupt_tag, b"") is None

    for iv in (b"\xa5", bytes(range(12))):
        for aad_length in (0, 1, 15, 16, 17, 31, 32, 64):
            for data_length in (0, 1, 15, 16, 17, 31, 32, 64):
                aad = bytes((3 * i + 1) & 0xFF for i in range(aad_length))
                data = bytes((7 * i + 2) & 0xFF for i in range(data_length))
                result, result_tag = encrypt(key, iv, data, aad)
                assert decrypt(key, iv, result, result_tag, aad) == data

    print("reference tests: PASS (AES-256 KAT, GCM KAT, auth failure, 128 boundary combinations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
