#!/usr/bin/env python3
"""Package explicit research artifacts; verify before restoring, never execute."""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import os
from pathlib import Path, PurePosixPath
import re
import stat
import sys
import tarfile


SCHEMA_VERSION = 1
MANIFEST = "BUNDLE-MANIFEST.json"
SOURCE = "SOURCE-MANIFEST.json"
METADATA_LIMIT = 1024 * 1024
CHUNK = 1024 * 1024
DEFAULT_FILES = 10_000
DEFAULT_BYTES = 100 * 1024**3
DENIED_PARTS = {
    ".git", ".ssh", ".aws", ".azure", ".kube", ".gnupg", ".docker",
    "gcloud", ".netrc", ".npmrc", ".pypirc", "credentials", "secrets",
    "id_rsa", "id_dsa", "id_ecdsa", "id_ed25519",
}


class BundleError(ValueError):
    pass


def require(condition: bool, message: str) -> None:
    if not condition:
        raise BundleError(message)


def relative_path(value: object) -> str:
    require(isinstance(value, str) and bool(value), "file path must be a nonempty string")
    require(not any(ord(c) < 32 for c in value) and len(value) <= 4096,
            f"invalid path: {value!r}")
    require("\\" not in value and ":" not in value, f"nonportable path: {value!r}")
    parts = value.split("/")
    require(not any(part in {"", ".", ".."} for part in parts),
            f"path must be canonical and relative: {value!r}")
    require(value not in {MANIFEST, SOURCE}, f"reserved path: {value}")
    for part in parts:
        lower = part.lower()
        require(lower not in DENIED_PARTS and not lower.startswith((".env", "credentials.", "secrets."))
                and not lower.endswith((".pem", ".key", ".p12", ".pfx")),
                f"sensitive credential/environment path refused: {value}")
    return value


def unique_paths(values: list[object]) -> list[str]:
    paths = [relative_path(value) for value in values]
    require(len(set(paths)) == len(paths), "duplicate file paths")
    path_set = set(paths)
    for path in paths:
        require(not any(str(parent) in path_set for parent in PurePosixPath(path).parents),
                f"file/directory path conflict: {path}")
    return paths


def parse_json(raw: bytes) -> object:
    def pairs(items):
        result = {}
        for key, value in items:
            require(key not in result, f"duplicate JSON key: {key}")
            result[key] = value
        return result
    return json.loads(raw, object_pairs_hook=pairs,
                      parse_constant=lambda value: (_ for _ in ()).throw(BundleError(value)))


def source_manifest(raw: bytes, max_files: int) -> dict:
    require(len(raw) <= METADATA_LIMIT, "source manifest is too large")
    manifest = parse_json(raw)
    require(isinstance(manifest, dict) and set(manifest) == {
        "schema_version", "campaign_id", "files", "replay_argv"}, "invalid source manifest fields")
    require(type(manifest["schema_version"]) is int and manifest["schema_version"] == SCHEMA_VERSION,
            "unsupported source manifest schema")
    require(isinstance(manifest["campaign_id"], str) and bool(manifest["campaign_id"].strip()),
            "campaign_id must be nonempty")
    require(isinstance(manifest["files"], list) and 0 < len(manifest["files"]) <= max_files,
            "file count outside allowed limit")
    unique_paths(manifest["files"])
    argv = manifest["replay_argv"]
    require(isinstance(argv, list) and bool(argv) and all(
        isinstance(arg, str) and "\0" not in arg for arg in argv) and bool(argv[0]),
        "replay_argv must be a nonempty array of strings")
    return manifest


@contextlib.contextmanager
def open_source(root: Path, path: str):
    """Open each path component without following links (including directories)."""
    descriptor = os.open(root, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW)
    try:
        parts = path.split("/")
        for part in parts[:-1]:
            child = os.open(part, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=descriptor)
            os.close(descriptor)
            descriptor = child
        file_descriptor = os.open(parts[-1], os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK,
                                  dir_fd=descriptor)
        if not stat.S_ISREG(os.fstat(file_descriptor).st_mode):
            os.close(file_descriptor)
            raise BundleError(f"not a regular file: {path}")
        with os.fdopen(file_descriptor, "rb") as stream:
            yield stream
    finally:
        os.close(descriptor)


def json_bytes(value: object) -> bytes:
    return (json.dumps(value, indent=2, sort_keys=True) + "\n").encode()


def tar_entry(archive: tarfile.TarFile, name: str, size: int, stream) -> None:
    info = tarfile.TarInfo(name)
    info.size = size
    info.mode = 0o644
    archive.addfile(info, stream)


class HashReader:
    def __init__(self, stream):
        self.stream = stream
        self.digest = hashlib.sha256()

    def read(self, size: int) -> bytes:
        data = self.stream.read(size)
        self.digest.update(data)
        return data


def create(root: Path, manifest_path: Path, output: Path, *, max_files: int = DEFAULT_FILES,
           max_bytes: int = DEFAULT_BYTES) -> dict:
    root = root.resolve(strict=True)
    raw = manifest_path.read_bytes()
    manifest = source_manifest(raw, max_files)
    total = 0
    sizes = {}
    # Reject unsafe sources before claiming the exclusive archive path.
    for path in manifest["files"]:
        with open_source(root, path) as stream:
            sizes[path] = os.fstat(stream.fileno()).st_size
        total += sizes[path]
        require(total <= max_bytes, "payload size exceeds allowed limit")
    records = []
    with output.open("xb") as stream, tarfile.open(fileobj=stream, mode="w:gz") as archive:
        for path in manifest["files"]:
            with open_source(root, path) as source:
                before = os.fstat(source.fileno())
                require(before.st_size == sizes[path], f"source size changed: {path}")
                reader = HashReader(source)
                tar_entry(archive, "files/" + path, before.st_size, reader)
                after = os.fstat(source.fileno())
                require((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                        (after.st_size, after.st_mtime_ns, after.st_ctime_ns),
                        f"source changed during capture: {path}")
                records.append({"path": path, "size": before.st_size,
                                "sha256": reader.digest.hexdigest()})
        metadata = {"schema_version": SCHEMA_VERSION, "campaign_id": manifest["campaign_id"],
                    "replay_argv": manifest["replay_argv"], "files": records,
                    "source_manifest_sha256": hashlib.sha256(raw).hexdigest()}
        encoded = json_bytes(metadata)
        require(len(encoded) <= METADATA_LIMIT, "bundle manifest is too large")
        tar_entry(archive, SOURCE, len(raw), io.BytesIO(raw))
        tar_entry(archive, MANIFEST, len(encoded), io.BytesIO(encoded))
    return {"status": "pass", "operation": "create", "bundle": str(output),
            "campaign_id": manifest["campaign_id"], "files": len(records), "payload_bytes": total}


def inspected(archive: tarfile.TarFile, max_files: int, max_bytes: int) -> tuple[dict, dict]:
    members = {}
    total = 0
    for member in archive:
        require(member.name not in members, f"duplicate archive path: {member.name}")
        require(member.isfile() and member.sparse is None and not member.pax_headers,
                f"non-regular or extended archive member: {member.name}")
        if member.name in {MANIFEST, SOURCE}:
            require(0 <= member.size <= METADATA_LIMIT, "metadata size exceeds limit")
        else:
            require(member.name.startswith("files/"), f"unexpected archive path: {member.name}")
            relative_path(member.name[6:])
            require(member.size >= 0, "negative member size")
            total += member.size
            require(total <= max_bytes, "payload size exceeds allowed limit")
        members[member.name] = member
        require(len(members) <= max_files + 2, "archive member count exceeds limit")
    require(MANIFEST in members and SOURCE in members, "archive metadata missing")
    raw = archive.extractfile(members[SOURCE]).read()
    source = source_manifest(raw, max_files)
    metadata = parse_json(archive.extractfile(members[MANIFEST]).read())
    require(isinstance(metadata, dict) and set(metadata) == {
        "schema_version", "campaign_id", "replay_argv", "files", "source_manifest_sha256"},
        "invalid bundle manifest fields")
    require(metadata["schema_version"] == SCHEMA_VERSION and type(metadata["schema_version"]) is int,
            "unsupported bundle manifest schema")
    require(metadata["source_manifest_sha256"] == hashlib.sha256(raw).hexdigest(),
            "source manifest digest mismatch")
    require(metadata["campaign_id"] == source["campaign_id"] and
            metadata["replay_argv"] == source["replay_argv"], "source/bundle metadata mismatch")
    records = metadata["files"]
    require(isinstance(records, list) and len(records) == len(source["files"]),
            "source/bundle file count mismatch")
    for path, record in zip(source["files"], records):
        require(isinstance(record, dict) and set(record) == {"path", "size", "sha256"} and
                record["path"] == path and type(record["size"]) is int and record["size"] >= 0 and
                isinstance(record["sha256"], str) and bool(re.fullmatch("[0-9a-f]{64}", record["sha256"])),
                "invalid file integrity record")
    require(set(members) == {MANIFEST, SOURCE} | {"files/" + path for path in source["files"]},
            "archive files differ from exact source manifest")
    for record in records:
        member = members["files/" + record["path"]]
        require(member.size == record["size"], f"size mismatch: {record['path']}")
        with archive.extractfile(member) as payload:
            digest = hashlib.sha256()
            while data := payload.read(CHUNK):
                digest.update(data)
        require(digest.hexdigest() == record["sha256"], f"digest mismatch: {record['path']}")
    return metadata, members


def verify_or_restore(bundle: Path, destination: Path | None = None, *,
                      max_files: int = DEFAULT_FILES, max_bytes: int = DEFAULT_BYTES) -> dict:
    if destination is not None:
        require(not os.path.lexists(destination), f"destination already exists: {destination}")
    with tarfile.open(bundle, "r:*") as archive:
        metadata, members = inspected(archive, max_files, max_bytes)
        # No destination or payload is created until *all* members have passed.
        if destination is not None:
            destination.mkdir(mode=0o700, exist_ok=False)
            for name in (SOURCE, MANIFEST, *("files/" + item["path"] for item in metadata["files"])):
                relative = name[6:] if name.startswith("files/") else name
                target = destination / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                with archive.extractfile(members[name]) as source, target.open("xb") as output:
                    digest = hashlib.sha256()
                    while data := source.read(CHUNK):
                        output.write(data)
                        digest.update(data)
                if name.startswith("files/"):
                    record = next(item for item in metadata["files"] if item["path"] == relative)
                    require(digest.hexdigest() == record["sha256"],
                            f"archive changed during restore: {relative}; retain partial destination")
    return {"status": "pass", "operation": "restore" if destination else "verify",
            "campaign_id": metadata["campaign_id"], "files": len(metadata["files"]),
            "payload_bytes": sum(item["size"] for item in metadata["files"]),
            "replay_argv": metadata["replay_argv"], "replay_executed": False}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subcommands = parser.add_subparsers(dest="operation", required=True)
    make = subcommands.add_parser("create")
    make.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    make.add_argument("--manifest", required=True, type=Path)
    make.add_argument("--out", required=True, type=Path)
    check = subcommands.add_parser("verify")
    check.add_argument("bundle", type=Path)
    restore = subcommands.add_parser("restore")
    restore.add_argument("bundle", type=Path)
    restore.add_argument("--dest", required=True, type=Path)
    for command in (make, check, restore):
        command.add_argument("--max-files", type=int, default=DEFAULT_FILES)
        command.add_argument("--max-bytes", type=int, default=DEFAULT_BYTES)
    args = parser.parse_args(argv)
    try:
        require(args.max_files > 0 and args.max_bytes >= 0, "invalid resource limit")
        limits = {"max_files": args.max_files, "max_bytes": args.max_bytes}
        if args.operation == "create":
            result = create(args.root, args.manifest, args.out, **limits)
        else:
            result = verify_or_restore(args.bundle, getattr(args, "dest", None), **limits)
        print(json.dumps(result, sort_keys=True))
        return 0
    except (BundleError, OSError, ValueError, tarfile.TarError, EOFError) as exc:
        print(f"artifact bundle error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
