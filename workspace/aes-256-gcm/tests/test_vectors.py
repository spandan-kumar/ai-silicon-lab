#!/usr/bin/env python3
"""Verify every normalized and generated vector against the reference model."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))

from aes_gcm import aes256_decrypt_block, aes256_encrypt_block, decrypt, encrypt


def binary(item: dict[str, object], field: str) -> bytes:
    return bytes.fromhex(str(item[field]))


def main() -> int:
    nist = json.loads((ROOT / "vectors" / "nist_subset.json").read_text())
    generated = json.loads((ROOT / "vectors" / "generated.json").read_text())

    for item in nist["aes_block"]:
        key = binary(item, "key")
        plaintext = binary(item, "plaintext")
        ciphertext = binary(item, "ciphertext")
        assert aes256_encrypt_block(key, plaintext) == ciphertext, item["id"]
        assert aes256_decrypt_block(key, ciphertext) == plaintext, item["id"]

    for item in nist["gcm"]:
        key, iv, aad = (binary(item, field) for field in ("key", "iv", "aad"))
        ciphertext, tag = binary(item, "ciphertext"), binary(item, "tag")
        plaintext = decrypt(key, iv, ciphertext, tag, aad)
        if item["expected_auth"]:
            expected = binary(item, "plaintext")
            assert plaintext == expected, item["id"]
            assert encrypt(key, iv, expected, aad) == (ciphertext, tag), item["id"]
        else:
            assert plaintext is None, item["id"]

    for item in generated["positive"]:
        key, iv, aad, plaintext = (binary(item, field) for field in ("key", "iv", "aad", "plaintext"))
        expected = binary(item, "ciphertext"), binary(item, "tag")
        assert encrypt(key, iv, plaintext, aad) == expected, item["id"]
        assert decrypt(key, iv, expected[0], expected[1], aad) == plaintext, item["id"]

    for item in generated["negative"]:
        assert decrypt(
            binary(item, "key"), binary(item, "iv"), binary(item, "ciphertext"),
            binary(item, "tag"), binary(item, "aad")
        ) is None, item["id"]

    print(
        "vector tests: PASS "
        f"({len(nist['aes_block'])} NIST AES, {len(nist['gcm'])} NIST GCM, "
        f"{len(generated['positive'])} generated positive, {len(generated['negative'])} generated negative)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
