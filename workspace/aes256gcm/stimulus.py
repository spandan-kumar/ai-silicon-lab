#!/usr/bin/env python3
"""Deterministic stimulus generation for the AES-256-GCM experiment.

Both sides of the comparison generate stimulus from this module, so the
reference and the RTL provably see identical inputs. The generator is a local
xorshift rather than `random`, so a corpus is reproducible across Python
versions and hosts rather than merely across runs of one interpreter.

Stimulus contains inputs only. For a decryption case the authentication tag is
an input by definition, but the expected plaintext and the expected verdict are
never part of stimulus; they exist only in the oracle.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Any, Iterator

sys.path.insert(0, str(Path(__file__).resolve().parent / "reference"))
import aes_gcm_ref as reference  # noqa: E402


class Xorshift32:
    """A small reproducible generator with an explicit, portable definition."""

    def __init__(self, seed: int) -> None:
        self.state = seed & 0xFFFFFFFF or 0x1234_5678

    def next(self) -> int:
        x = self.state
        x ^= (x << 13) & 0xFFFFFFFF
        x ^= x >> 17
        x ^= (x << 5) & 0xFFFFFFFF
        self.state = x & 0xFFFFFFFF
        return self.state

    def below(self, bound: int) -> int:
        return self.next() % bound if bound > 0 else 0

    def bytes(self, count: int) -> bytes:
        return bytes(self.next() & 0xFF for _ in range(count))


def _case(
    case_id: str,
    mode: int,
    key: bytes,
    iv: bytes,
    aad: bytes,
    text: bytes,
    tag_bytes: int,
    exp_tag: bytes | None = None,
    stall_seed: int = 0,
) -> dict[str, Any]:
    return {
        "id": case_id,
        "mode": mode,
        "key": key.hex(),
        "iv": iv.hex(),
        "aad": aad.hex(),
        "text": text.hex(),
        "tag_bytes": tag_bytes,
        "exp_tag": exp_tag.hex() if exp_tag else None,
        "stall_seed": stall_seed,
    }


def _decrypt_case(
    case_id: str,
    key: bytes,
    iv: bytes,
    aad: bytes,
    plaintext: bytes,
    tag_bytes: int,
    corrupt: int | None = None,
    stall_seed: int = 0,
) -> dict[str, Any]:
    """Build a decryption case from a valid encryption of `plaintext`.

    Constructing the ciphertext/tag pair is stimulus preparation, not oracle
    leakage: the candidate still has to derive the plaintext and the verdict
    itself, and both are withheld from it.
    """
    ciphertext, tag = reference.encrypt(key, iv, aad, plaintext, tag_bytes)
    if corrupt is not None:
        mutated = bytearray(tag)
        mutated[corrupt % len(mutated)] ^= 0x01
        tag = bytes(mutated)
    return _case(case_id, 1, key, iv, aad, ciphertext, tag_bytes, tag, stall_seed)


# --- Workload corpora -----------------------------------------------------

def block_kat() -> list[dict[str, Any]]:
    """AES-256 block known-answer cases, including the FIPS 197 C.3 example."""
    cases = [
        {"id": "fips197-c3", "key": bytes(range(32)).hex(),
         "block": "00112233445566778899aabbccddeeff"},
        {"id": "all-zero", "key": ("00" * 32), "block": "00" * 16},
        {"id": "all-ff", "key": ("ff" * 32), "block": "ff" * 16},
    ]
    rng = Xorshift32(0x0A252560)
    for index in range(125):
        cases.append(
            {
                "id": f"block-{index:03d}",
                "key": rng.bytes(32).hex(),
                "block": rng.bytes(16).hex(),
            }
        )
    return cases


def known_answer() -> list[dict[str, Any]]:
    """Structural GCM cases over the frozen profile's declared shapes."""
    rng = Xorshift32(0x6743_4D01)
    shapes = [
        (0, 0, 12, 16), (0, 16, 12, 16), (16, 0, 12, 16), (16, 16, 12, 16),
        (32, 32, 12, 16), (64, 20, 12, 16), (48, 48, 12, 16), (128, 64, 12, 16),
    ]
    cases = []
    for index, (text_len, aad_len, iv_len, tag_len) in enumerate(shapes):
        key, iv = rng.bytes(32), rng.bytes(iv_len)
        aad, text = rng.bytes(aad_len), rng.bytes(text_len)
        cases.append(_case(f"kat-enc-{index:02d}", 0, key, iv, aad, text, tag_len))
        cases.append(
            _decrypt_case(f"kat-dec-{index:02d}", key, iv, aad, text, tag_len)
        )
    return cases


def edge_cases() -> list[dict[str, Any]]:
    """Boundaries the profile calls out explicitly, including tag rejection."""
    rng = Xorshift32(0x0EDE_0001)
    cases: list[dict[str, Any]] = []

    # Empty and partial payloads and AAD around the block boundary.
    for index, (text_len, aad_len) in enumerate(
        [(0, 0), (1, 0), (0, 1), (1, 1), (15, 15), (16, 16), (17, 17), (31, 33)]
    ):
        key, iv = rng.bytes(32), rng.bytes(12)
        aad, text = rng.bytes(aad_len), rng.bytes(text_len)
        cases.append(_case(f"edge-len-{index:02d}", 0, key, iv, aad, text, 16))

    # IV lengths: the 96-bit fast path against the GHASH path.
    for index, iv_len in enumerate([1, 8, 12, 13, 16, 20, 32, 60]):
        key, iv = rng.bytes(32), rng.bytes(iv_len)
        aad, text = rng.bytes(16), rng.bytes(24)
        cases.append(_case(f"edge-iv-{index:02d}", 0, key, iv, aad, text, 16))

    # Tag truncation across the supported range.
    for index, tag_len in enumerate([4, 8, 12, 13, 14, 15, 16]):
        key, iv = rng.bytes(32), rng.bytes(12)
        aad, text = rng.bytes(16), rng.bytes(16)
        cases.append(_case(f"edge-tag-{index:02d}", 0, key, iv, aad, text, tag_len))

    # Negative decryption: every corrupted tag must be rejected and must not
    # release plaintext.
    for index in range(12):
        key, iv = rng.bytes(32), rng.bytes(12)
        aad, text = rng.bytes(rng.below(40)), rng.bytes(rng.below(64))
        cases.append(
            _decrypt_case(f"edge-badtag-{index:02d}", key, iv, aad, text, 16, corrupt=index)
        )
        cases.append(
            _decrypt_case(f"edge-goodtag-{index:02d}", key, iv, aad, text, 16)
        )
    return cases


def random_differential(count: int = 160) -> list[dict[str, Any]]:
    """Randomised encrypt/decrypt pairs over the whole declared profile."""
    rng = Xorshift32(0x5EED_1234)
    iv_lengths = [12, 12, 12, 8, 16, 1, 24]
    tag_lengths = [16, 16, 16, 15, 14, 13, 12, 8, 4]
    cases: list[dict[str, Any]] = []
    for index in range(count):
        key = rng.bytes(32)
        iv = rng.bytes(iv_lengths[rng.below(len(iv_lengths))])
        aad = rng.bytes(rng.below(48))
        text = rng.bytes(rng.below(96))
        tag_len = tag_lengths[rng.below(len(tag_lengths))]
        cases.append(_case(f"rand-enc-{index:03d}", 0, key, iv, aad, text, tag_len))
        cases.append(
            _decrypt_case(f"rand-dec-{index:03d}", key, iv, aad, text, tag_len)
        )
    return cases


def interface_stress() -> list[dict[str, Any]]:
    """Identical payloads under many stall patterns.

    Backpressure must not change a single output byte. The stall seed is the
    only thing that varies across a group.
    """
    rng = Xorshift32(0x1FACE007)
    cases: list[dict[str, Any]] = []
    for group in range(6):
        key, iv = rng.bytes(32), rng.bytes(12 if group % 2 else 8)
        aad, text = rng.bytes(20 + group), rng.bytes(33 + 7 * group)
        for index, seed in enumerate([0, 1, 7, 12345, 0xABCDEF, 0x7FFFFFFF]):
            cases.append(
                _case(
                    f"stress-{group}-{index}", 0, key, iv, aad, text, 16, stall_seed=seed
                )
            )
        cases.append(
            _decrypt_case(f"stress-dec-{group}", key, iv, aad, text, 16, stall_seed=99 + group)
        )
    return cases


def throughput_sweep() -> list[dict[str, Any]]:
    """Message-size classes for cycles-per-byte, from sub-block to streaming."""
    rng = Xorshift32(0x7047_0000)
    cases = []
    for index, text_len in enumerate([1, 8, 15, 16, 17, 32, 64, 128, 256, 384, 512]):
        key, iv = rng.bytes(32), rng.bytes(12)
        cases.append(
            _case(f"sweep-{text_len:04d}", 0, key, iv, rng.bytes(16), rng.bytes(text_len), 16)
        )
    # AAD-heavy and AAD-free variants at one size, to separate the two costs.
    key, iv = rng.bytes(32), rng.bytes(12)
    cases.append(_case("sweep-aad-none", 0, key, iv, b"", rng.bytes(256), 16))
    cases.append(_case("sweep-aad-heavy", 0, key, iv, rng.bytes(256), rng.bytes(256), 16))
    return cases


def latency_probe() -> list[dict[str, Any]]:
    """Same lengths, different secret values.

    Used to observe whether cycle count depends on key or data. A fixed count
    across these cases is evidence of data-independent latency for these
    traces; it is not a leakage-resistance claim.
    """
    rng = Xorshift32(0x1A7E_0C1)
    cases = []
    fixed_iv = bytes(12)
    for index in range(24):
        key = bytes(32) if index % 3 == 0 else (
            bytes([0xFF] * 32) if index % 3 == 1 else rng.bytes(32)
        )
        text = bytes(64) if index % 2 == 0 else rng.bytes(64)
        cases.append(_case(f"latency-{index:02d}", 0, key, fixed_iv, bytes(16), text, 16))
    return cases


CORPORA = {
    "aes-256-block-kat": block_kat,
    "gcm-known-answer": known_answer,
    "gcm-edge-cases": edge_cases,
    "gcm-random-differential": random_differential,
    "gcm-interface-stress": interface_stress,
    "gcm-throughput-sweep": throughput_sweep,
    "security-latency-probe": latency_probe,
}


def corpus(workload_id: str) -> list[dict[str, Any]]:
    if workload_id not in CORPORA:
        raise KeyError(f"no stimulus corpus for workload {workload_id!r}")
    return CORPORA[workload_id]()


def write_gcm_stimulus(cases: list[dict[str, Any]], path: Path) -> None:
    """The flat line format the RTL testbench parses."""
    lines = ["# id mode key iv aad text tag_bytes exp_tag stall_seed"]
    for case in cases:
        lines.append(
            " ".join(
                [
                    case["id"],
                    str(case["mode"]),
                    case["key"] or "-",
                    case["iv"] or "-",
                    case["aad"] or "-",
                    case["text"] or "-",
                    str(case["tag_bytes"]),
                    case["exp_tag"] or "-",
                    str(case["stall_seed"]),
                ]
            )
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def write_block_stimulus(cases: list[dict[str, Any]], path: Path) -> None:
    lines = [f"{case['id']} {case['key']} {case['block']}" for case in cases]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
