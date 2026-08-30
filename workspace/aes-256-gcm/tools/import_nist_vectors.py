#!/usr/bin/env python3
"""Normalize a deterministic profile-sized subset of the official CAVP archives."""

from __future__ import annotations

import argparse
import hashlib
import json
import zipfile
from pathlib import Path


AES_SHA256 = "a203b16c9246b2ebae31dee5de21a606be80cf78ceabaca37150236fa098eb60"
GCM_SHA256 = "f9fc479e134cde2980b3bb7cddbcb567b2cd96fd753835243ed067699f26a023"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def check_archive(path: Path, expected: str) -> None:
    actual = sha256(path)
    if actual != expected:
        raise ValueError(f"{path}: expected SHA-256 {expected}, got {actual}")


def parse_rsp(text: str) -> list[dict[str, str | int | bool]]:
    context: dict[str, str | int | bool] = {}
    current: dict[str, str | int | bool] | None = None
    records: list[dict[str, str | int | bool]] = []

    def flush() -> None:
        nonlocal current
        if current is not None:
            records.append(current)
            current = None

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("[") and line.endswith("]"):
            flush()
            body = line[1:-1]
            if "=" in body:
                name, value = (part.strip() for part in body.split("=", 1))
                context[name.lower()] = int(value) if value.isdigit() else value.lower()
            else:
                context["section"] = body.lower()
            continue
        if line.upper() == "FAIL":
            if current is None:
                raise ValueError("FAIL without a current vector")
            current["fail"] = True
            continue
        if "=" not in line:
            continue
        name, value = (part.strip() for part in line.split("=", 1))
        if name.lower() == "count":
            flush()
            current = dict(context)
            current["count"] = int(value)
        elif current is not None:
            current[name.lower()] = value.lower()
    flush()
    return records


def normalize_aes(records: list[dict[str, str | int | bool]]) -> list[dict[str, object]]:
    output = []
    for record in records:
        if record.get("section") != "encrypt":
            continue
        output.append({
            "id": f"nist-aes-gfsbox-256-{record['count']}",
            "key": record["key"],
            "plaintext": record["plaintext"],
            "ciphertext": record["ciphertext"],
        })
    return output


def normalize_gcm(records: list[dict[str, str | int | bool]], direction: str) -> list[dict[str, object]]:
    selected: dict[tuple[int, int, int, bool], dict[str, str | int | bool]] = {}
    for record in records:
        if record.get("keylen") != 256 or record.get("taglen") != 128:
            continue
        iv_bits = int(record["ivlen"])
        pt_bits = int(record["ptlen"])
        aad_bits = int(record["aadlen"])
        if iv_bits not in (8, 96) or pt_bits % 8 or aad_bits % 8:
            continue
        if pt_bits > 512 or aad_bits > 512:
            continue
        failed = bool(record.get("fail", False))
        group = (iv_bits, pt_bits, aad_bits, failed)
        selected.setdefault(group, record)

    output = []
    for group in sorted(selected):
        record = selected[group]
        failed = bool(record.get("fail", False))
        item: dict[str, object] = {
            "id": f"nist-gcm-{direction}-iv{record['ivlen']}-pt{record['ptlen']}-aad{record['aadlen']}-{'fail' if failed else 'pass'}",
            "direction": direction,
            "key": record["key"],
            "iv": record["iv"],
            "aad": record["aad"],
            "ciphertext": record["ct"],
            "tag": record["tag"],
            "expected_auth": not failed,
        }
        if not failed:
            item["plaintext"] = record.get("pt", "")
        output.append(item)
    return output


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--aes-archive", required=True, type=Path)
    parser.add_argument("--gcm-archive", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()

    check_archive(args.aes_archive, AES_SHA256)
    check_archive(args.gcm_archive, GCM_SHA256)
    with zipfile.ZipFile(args.aes_archive) as archive:
        aes_records = parse_rsp(archive.read("ECBGFSbox256.rsp").decode("ascii"))
    with zipfile.ZipFile(args.gcm_archive) as archive:
        enc_records = parse_rsp(archive.read("gcmEncryptExtIV256.rsp").decode("ascii"))
        dec_records = parse_rsp(archive.read("gcmDecrypt256.rsp").decode("ascii"))

    document = {
        "schema_version": 1,
        "profile_id": "aes-256-gcm-64-v1",
        "source_sha256": {"aes": AES_SHA256, "gcm": GCM_SHA256},
        "selection": "all AES-256 GFSbox encrypt cases; first CAVP GCM record per direction/IV/PT/AAD/auth group within frozen byte and tag limits",
        "aes_block": normalize_aes(aes_records),
        "gcm": normalize_gcm(enc_records, "encrypt") + normalize_gcm(dec_records, "decrypt"),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(document, indent=2, sort_keys=True) + "\n")
    print(f"wrote {len(document['aes_block'])} AES and {len(document['gcm'])} GCM vectors to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
