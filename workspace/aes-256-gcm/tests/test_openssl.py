#!/usr/bin/env python3
"""Cross-check the committed corpus with the independent OpenSSL EVP path."""

from __future__ import annotations

import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BINARY = ROOT / "build" / "openssl_baseline"


def field(item: dict[str, object], name: str) -> str:
    return str(item[name]) or "-"


def main() -> int:
    nist = json.loads((ROOT / "vectors" / "nist_subset.json").read_text())
    generated = json.loads((ROOT / "vectors" / "generated.json").read_text())
    cases = []
    expected = []

    for item in nist["gcm"] + generated["positive"]:
        if item.get("direction") in ("encrypt", "both"):
            cases.append("\t".join(("E", field(item, "key"), field(item, "iv"), field(item, "aad"), field(item, "plaintext"))))
            expected.append("P\t" + field(item, "ciphertext").replace("-", "") + "\t" + field(item, "tag"))
        cases.append("\t".join(("D", field(item, "key"), field(item, "iv"), field(item, "aad"), field(item, "ciphertext"), field(item, "tag"))))
        if item["expected_auth"]:
            expected.append("P\t" + field(item, "plaintext").replace("-", ""))
        else:
            expected.append("F")

    for item in generated["negative"]:
        cases.append("\t".join(("D", field(item, "key"), field(item, "iv"), field(item, "aad"), field(item, "ciphertext"), field(item, "tag"))))
        expected.append("F")

    result = subprocess.run(
        [str(BINARY)], input="\n".join(cases) + "\n", text=True,
        stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(f"OpenSSL baseline failed ({result.returncode}): {result.stderr}")
    actual = result.stdout.splitlines()
    assert len(actual) == len(expected), (len(actual), len(expected))
    for index, (observed, wanted) in enumerate(zip(actual, expected)):
        assert observed == wanted, (index, observed, wanted)
    print(f"OpenSSL differential tests: PASS ({len(expected)} operations)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
