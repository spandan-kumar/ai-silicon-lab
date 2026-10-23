# Campaign artifact bundles

`artifact_bundle.py` preserves explicitly selected raw evidence outside Git.
It uses only Python's standard library. A bundle is an integrity-checked
snapshot, not a scientific verdict, a signature, or permission to trust code.
Correctness still requires the campaign's independent checker and actual
process exit records. Replaying a restored command is a separate, deliberate
operation after reviewing the code and its environment.

## Explicit capture

Prepare a JSON source manifest with exactly these fields. Paths are relative
to the repository root; there are no globs, directory recursion, or implicit
dependency discovery. Include the recipe, implementation sources, inputs,
terminal records, stdout/stderr, and audit output required to replay the claim.
The `replay_argv` array is inert metadata and is never executed by this tool.

```json
{
  "schema_version": 1,
  "campaign_id": "example-campaign",
  "files": [
    "tools/campaign.py",
    "runs/example/recipe.json",
    "runs/example/result.json",
    "runs/example/audit.json"
  ],
  "replay_argv": ["python3", "workspace/aes-256-gcm/tools/finalize_frontier_campaign.py", "--campaign", "experiments/gf16-multiplicative-complexity/campaigns/frontier-pairs.json", "--out", "fresh-comparison.json"]
}
```

```sh
python3 tools/artifact_bundle.py create --root . --manifest runs/example/bundle-source.json --out /absolute/archive/example.tar.gz
python3 tools/artifact_bundle.py verify /absolute/archive/example.tar.gz
python3 tools/artifact_bundle.py restore /absolute/archive/example.tar.gz --dest /absolute/new-restore-directory
```

Creation refuses an existing output, links in source paths, nonregular files,
paths outside the root, duplicate paths, and file/directory collisions. It
records the exact bytes' SHA-256 and size for each payload, preserves the
original source manifest, and records its digest. Source modification detected
during capture is an error. This is not an atomic cross-file filesystem
snapshot: stop writers first or capture a frozen campaign. If capture fails
after opening the output, the partial archive is retained and the command exits
nonzero; use a new output path for the next attempt. A failed output must not
be published as a verified bundle.

The source-path denylist blocks common credential/environment locations such
as `.env*`, `.ssh`, `.git`, credential files, and private-key extensions. This
is a guard, **not a content secret scanner**: review all selected files and
`replay_argv` yourself; never place credentials or unrelated personal data in
either. The tool intentionally refuses potentially legitimate scientific files
with sensitive-looking names; rename/copy reviewed nonsecret evidence to a
clear artifact path rather than weakening the guard for a broad capture.

## Verification and restore boundary

Before creating the destination, restore checks the entire archive: regular
file types only, canonical paths, no links, no duplicate/extra/missing paths,
no extended or sparse members, exact manifest correspondence, declared sizes,
and every payload digest. It never calls `tar.extract` or runs archive code.
The new directory must not exist, including as a dangling symlink. Original
repo-relative paths are recreated beneath it, alongside `BUNDLE-MANIFEST.json`
and `SOURCE-MANIFEST.json`. File permissions are not preserved as executable.

Default limits are 10,000 payload files and 100 GiB total uncompressed payload,
with each metadata document capped at 1 MiB. `--max-files` and `--max-bytes`
can deliberately tighten or expand the payload limits on all three commands.
Payload hashes detect accidental modification, not a malicious party that
rewrites both data and manifests. Use trusted storage or publish a separately
trusted archive hash when authenticity matters. Do not modify the archive
while restoring; a second payload hash check detects changes during copying,
but an I/O failure may leave a partial destination. Partial destinations and
failed archives are retained, never automatically removed or overwritten.

## Tests

```sh
python3 -m unittest discover -s tools -p test_artifact_bundle.py -v
```

Tests cover a byte-exact round trip, inert replay metadata, output/destination
overwrite refusal, source and archive links, traversal, duplicate and extra
members, source-manifest tampering, payload corruption, missing metadata,
file/directory conflicts, nonregular sources, and resource limits.
