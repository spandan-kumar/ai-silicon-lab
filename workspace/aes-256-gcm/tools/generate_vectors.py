#!/usr/bin/env python3
"""Generate deterministic edge, random differential, and negative vectors."""

from __future__ import annotations

import argparse
import hashlib
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "reference"))

from aes_gcm import encrypt


SEED = 0xA2566C64
BOUNDARIES = (0, 1, 15, 16, 17, 31, 32, 64)


def make_positive(identifier: str, key: bytes, iv: bytes, aad: bytes, plaintext: bytes) -> dict[str, object]:
    ciphertext, tag = encrypt(key, iv, plaintext, aad)
    return {
        "id": identifier,
        "direction": "both",
        "key": key.hex(),
        "iv": iv.hex(),
        "aad": aad.hex(),
        "plaintext": plaintext.hex(),
        "ciphertext": ciphertext.hex(),
        "tag": tag.hex(),
        "expected_auth": True,
    }


def flip(value: bytes, index: int = 0) -> bytes:
    if not value:
        return value
    changed = bytearray(value)
    changed[index % len(changed)] ^= 1
    return bytes(changed)


def make_negative(base: dict[str, object], field: str, serial: int) -> dict[str, object]:
    item = dict(base)
    item["id"] = f"{base['id']}-reject-{field}"
    item["direction"] = "decrypt"
    item["expected_auth"] = False
    item["plaintext"] = None
    raw = bytes.fromhex(str(item[field]))
    item[field] = flip(raw, serial).hex()
    return item


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    rng = random.Random(SEED)
    positives = []

    for iv_length in (1, 12):
        for aad_length in BOUNDARIES:
            for data_length in BOUNDARIES:
                serial = len(positives)
                key = hashlib.sha256(f"edge-key-{serial}".encode()).digest()
                iv = hashlib.sha256(f"edge-iv-{serial}".encode()).digest()[:iv_length]
                aad = bytes((3 * i + serial) & 0xFF for i in range(aad_length))
                data = bytes((7 * i + 2 * serial + 1) & 0xFF for i in range(data_length))
                positives.append(make_positive(f"edge-iv{iv_length}-aad{aad_length}-data{data_length}", key, iv, aad, data))

    for serial in range(256):
        iv_length = rng.choice((1, 12))
        aad_length = rng.randrange(65)
        data_length = rng.randrange(65)
        positives.append(make_positive(
            f"random-{serial:03d}",
            rng.randbytes(32),
            rng.randbytes(iv_length),
            rng.randbytes(aad_length),
            rng.randbytes(data_length),
        ))

    negatives = []
    for serial, base in enumerate(positives[::12]):
        negatives.append(make_negative(base, "tag", serial))
        negatives.append(make_negative(base, "key", serial + 1))
        negatives.append(make_negative(base, "iv", serial + 2))
        if base["aad"]:
            negatives.append(make_negative(base, "aad", serial + 3))
        if base["ciphertext"]:
            negatives.append(make_negative(base, "ciphertext", serial + 4))

    document = {
        "schema_version": 1,
        "generator": "tools/generate_vectors.py",
        "profile_id": "aes-256-gcm-64-v1",
        "seed": SEED,
        "boundary_lengths": list(BOUNDARIES),
        "positive": positives,
        "negative": negatives,
        "interface_only": [
            {"id": "reject-iv-zero", "iv_bytes": 0, "expected": "length_error"},
            {"id": "reject-iv-two", "iv_bytes": 2, "expected": "length_error"},
            {"id": "reject-aad-65", "aad_bytes": 65, "expected": "length_error"},
            {"id": "reject-payload-65", "payload_bytes": 65, "expected": "length_error"},
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    digest = hashlib.sha256(args.output.read_bytes()).hexdigest()
    print(f"wrote {len(positives)} positive and {len(negatives)} negative vectors; sha256={digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
