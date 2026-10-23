#!/usr/bin/env python3

from __future__ import annotations

import io
import json
from pathlib import Path
import tarfile
import tempfile
import unittest

from artifact_bundle import BundleError, MANIFEST, SOURCE, create, verify_or_restore


class ArtifactBundleTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.base = Path(self.temporary.name)
        self.root = self.base / "repo"
        self.root.mkdir()
        (self.root / "runs").mkdir()
        (self.root / "runs" / "result.json").write_bytes(b'{"status":"pass"}\n')
        self.manifest = self.base / "manifest.json"
        self.write_manifest(["runs/result.json"])
        self.bundle = self.base / "bundle.tar.gz"

    def write_manifest(self, files):
        self.manifest.write_text(json.dumps({"schema_version": 1, "campaign_id": "test-campaign",
            "files": files, "replay_argv": ["python3", "tools/replay.py", "--audit-only"]}))

    def make(self):
        return create(self.root, self.manifest, self.bundle)

    def rewrite(self, mutate):
        entries = []
        with tarfile.open(self.bundle) as archive:
            for member in archive:
                entries.append((member, archive.extractfile(member).read()))
        target = self.base / "mutated.tar"
        with tarfile.open(target, "w") as archive:
            for member, data in mutate(entries):
                member.size = len(data)
                archive.addfile(member, io.BytesIO(data) if member.isfile() else None)
        return target

    def rejected_without_destination(self, bundle):
        destination = self.base / "restore"
        with self.assertRaises((BundleError, tarfile.TarError, EOFError)):
            verify_or_restore(bundle, destination)
        self.assertFalse(destination.exists())

    def test_roundtrip_and_replay_is_never_executed(self):
        result = self.make()
        self.assertEqual(1, result["files"])
        verified = verify_or_restore(self.bundle)
        self.assertFalse(verified["replay_executed"])
        destination = self.base / "restored"
        restored = verify_or_restore(self.bundle, destination)
        self.assertEqual(verified["files"], restored["files"])
        self.assertEqual((self.root / "runs/result.json").read_bytes(),
                         (destination / "runs/result.json").read_bytes())
        self.assertEqual(self.manifest.read_bytes(), (destination / SOURCE).read_bytes())
        self.assertTrue((destination / MANIFEST).is_file())

    def test_create_and_restore_never_overwrite(self):
        self.make()
        previous = self.bundle.read_bytes()
        with self.assertRaises(FileExistsError):
            self.make()
        self.assertEqual(previous, self.bundle.read_bytes())
        destination = self.base / "existing"
        destination.mkdir()
        sentinel = destination / "sentinel"
        sentinel.write_text("keep")
        with self.assertRaises(BundleError):
            verify_or_restore(self.bundle, destination)
        self.assertEqual("keep", sentinel.read_text())

    def test_traversal_and_sensitive_source_paths(self):
        for path in ("../outside", "/tmp/outside", "runs/../outside", "runs//result.json",
                     "runs\\result.json", ".env", "runs/.env.production", ".ssh/id_rsa",
                     "runs/private.pem", "runs/credentials.json", "C:/outside"):
            with self.subTest(path=path):
                self.write_manifest([path])
                with self.assertRaises(BundleError):
                    self.make()
                self.assertFalse(self.bundle.exists())

    def test_source_symlink_and_symlinked_parent(self):
        (self.root / "link").symlink_to(self.root / "runs/result.json")
        (self.root / "linked").symlink_to(self.root / "runs", target_is_directory=True)
        for path in ("link", "linked/result.json"):
            with self.subTest(path=path):
                self.write_manifest([path])
                with self.assertRaises(OSError):
                    self.make()
                self.assertFalse(self.bundle.exists())

    def test_corruption_is_rejected_before_restore(self):
        self.make()
        def corrupt(entries):
            for member, data in entries:
                yield member, b"X" + data[1:] if member.name.startswith("files/") else data
        self.rejected_without_destination(self.rewrite(corrupt))

    def test_archive_traversal_links_duplicates_and_extra_files(self):
        self.make()
        def change_path(entries):
            entries[0][0].name = "files/../../outside"
            return entries
        self.rejected_without_destination(self.rewrite(change_path))
        def link(entries):
            entries[0][0].type = tarfile.SYMTYPE
            entries[0][0].linkname = "../../outside"
            return entries
        self.rejected_without_destination(self.rewrite(link))
        def duplicate(entries):
            return entries + [entries[0]]
        self.rejected_without_destination(self.rewrite(duplicate))
        def extra(entries):
            return entries + [(tarfile.TarInfo("files/unlisted"), b"unlisted")]
        self.rejected_without_destination(self.rewrite(extra))

    def test_manifest_tampering_size_mismatch_and_missing_metadata(self):
        self.make()
        def bad_metadata(entries):
            for member, data in entries:
                if member.name == MANIFEST:
                    metadata = json.loads(data)
                    metadata["files"][0]["size"] += 1
                    data = json.dumps(metadata).encode()
                yield member, data
        self.rejected_without_destination(self.rewrite(bad_metadata))
        def bad_source(entries):
            return [(member, data.replace(b"test-campaign", b"other-campaign")
                     if member.name == SOURCE else data) for member, data in entries]
        self.rejected_without_destination(self.rewrite(bad_source))
        self.rejected_without_destination(self.rewrite(
            lambda entries: [(member, data) for member, data in entries if member.name != MANIFEST]))

    def test_resource_limits(self):
        with self.assertRaises(BundleError):
            create(self.root, self.manifest, self.bundle, max_bytes=1)
        self.assertFalse(self.bundle.exists())
        self.make()
        with self.assertRaises(BundleError):
            verify_or_restore(self.bundle, max_bytes=1)
        (self.root / "another.txt").write_text("another")
        self.write_manifest(["runs/result.json", "another.txt"])
        with self.assertRaises(BundleError):
            create(self.root, self.manifest, self.base / "too-many.tar", max_files=1)

    def test_duplicate_paths_parent_conflict_and_nonregular_source(self):
        for paths in (["runs/result.json", "runs/result.json"], ["runs", "runs/result.json"], ["runs"]):
            with self.subTest(paths=paths):
                self.write_manifest(paths)
                with self.assertRaises(BundleError):
                    self.make()
                self.assertFalse(self.bundle.exists())


if __name__ == "__main__":
    unittest.main()
