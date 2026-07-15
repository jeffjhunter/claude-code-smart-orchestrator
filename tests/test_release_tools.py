from __future__ import annotations

import io
import os
from pathlib import Path
import sys
import tempfile
import unittest
import zipfile


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_release import (  # noqa: E402
    ARCHIVE,
    CHECKSUM_PATH,
    COMMIT_PATH,
    MANIFEST_PATH,
    collect_files,
    make_archive,
    make_checksum,
    make_commit_marker,
    make_manifest,
    publish_release_payloads,
    snapshot_files,
    validate_embedded_manifest,
)
from verify_release import (  # noqa: E402
    strict_json,
    validate_commit_schema,
    validate_manifest_schema,
    verify_archive,
    verify_canonical_zip_bytes,
)


class CanonicalReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.snapshots = snapshot_files(collect_files())
        cls.manifest = make_manifest(cls.snapshots)
        cls.archive = make_archive(cls.snapshots, cls.manifest)
        cls.checksum = make_checksum(cls.archive)
        cls.commit = make_commit_marker(
            cls.archive, cls.manifest, cls.checksum
        )

    def test_archive_bytes_are_repeatable(self) -> None:
        self.assertEqual(
            self.archive,
            make_archive(self.snapshots, self.manifest),
        )
        self.assertGreater(
            verify_canonical_zip_bytes(
                self.archive, self.snapshots, self.manifest
            ),
            1,
        )

    def test_embedded_root_manifest_must_match_canonical_bytes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            manifest_path = Path(temporary) / "MANIFEST.json"
            manifest_path.write_bytes(self.manifest)
            validate_embedded_manifest(manifest_path, self.manifest)

            manifest_path.write_bytes(b"{}\n")
            with self.assertRaisesRegex(RuntimeError, "does not exactly match"):
                validate_embedded_manifest(manifest_path, self.manifest)

    def test_reordered_members_are_rejected(self) -> None:
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.archive)) as source:
            infos = source.infolist()
            members = [(info, source.read(info)) for info in reversed(infos)]
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as target:
            for info, data in members:
                target.writestr(info, data)
        with self.assertRaisesRegex(ValueError, "exact canonical"):
            verify_canonical_zip_bytes(
                output.getvalue(), self.snapshots, self.manifest
            )

    def test_archive_comment_is_rejected(self) -> None:
        output = io.BytesIO(self.archive)
        with zipfile.ZipFile(output, "a") as bundle:
            bundle.comment = b"not canonical"
        with self.assertRaisesRegex(ValueError, "exact canonical"):
            verify_canonical_zip_bytes(
                output.getvalue(), self.snapshots, self.manifest
            )

    def test_reordered_archive_with_recomputed_sidecars_is_rejected(self) -> None:
        output = io.BytesIO()
        with zipfile.ZipFile(io.BytesIO(self.archive)) as source:
            infos = source.infolist()
            members = [(info, source.read(info)) for info in reversed(infos)]
        with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as target:
            for info, data in members:
                target.writestr(info, data)
        reordered = output.getvalue()
        checksum = make_checksum(reordered)
        commit = make_commit_marker(reordered, self.manifest, checksum)

        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            archive_path = directory / ARCHIVE.name
            archive_path.write_bytes(reordered)
            (directory / MANIFEST_PATH.name).write_bytes(self.manifest)
            (directory / CHECKSUM_PATH.name).write_bytes(checksum)
            (directory / COMMIT_PATH.name).write_bytes(commit)
            with self.assertRaisesRegex(ValueError, "not canonical|exact canonical"):
                verify_archive(archive_path)

    def test_manifest_unknown_field_and_bool_size_are_rejected(self) -> None:
        manifest = strict_json(self.manifest, "test manifest")
        manifest["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "exactly"):
            validate_manifest_schema(manifest)

        manifest = strict_json(self.manifest, "test manifest")
        manifest["files"][0]["bytes"] = True
        with self.assertRaisesRegex(ValueError, "byte count"):
            validate_manifest_schema(manifest)

    def test_duplicate_json_keys_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate key"):
            strict_json(b'{"format": 1, "format": 1}', "duplicate test")

    def test_commit_marker_schema_and_hashes_are_strict(self) -> None:
        actual = {
            ARCHIVE.name: self.archive,
            MANIFEST_PATH.name: self.manifest,
            CHECKSUM_PATH.name: self.checksum,
        }
        marker = strict_json(self.commit, "test commit marker")
        validate_commit_schema(marker, actual)

        marker = strict_json(self.commit, "test commit marker")
        marker["outputs"][0]["unexpected"] = "field"
        with self.assertRaisesRegex(ValueError, "unknown or missing"):
            validate_commit_schema(marker, actual)

        marker = strict_json(self.commit, "test commit marker")
        marker["outputs"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_commit_schema(marker, actual)


class CoordinatedPublicationTests(unittest.TestCase):
    def test_publish_failure_restores_last_good_set(self) -> None:
        for failure_name in (
            "archive.zip",
            "MANIFEST.json",
            "SHA256SUMS.txt",
            COMMIT_PATH.name,
        ):
            with self.subTest(failure_name=failure_name):
                with tempfile.TemporaryDirectory() as temporary:
                    directory = Path(temporary)
                    targets = [
                        directory / "archive.zip",
                        directory / "MANIFEST.json",
                        directory / "SHA256SUMS.txt",
                        directory / COMMIT_PATH.name,
                    ]
                    old_payloads = [
                        b"old archive",
                        b"old manifest",
                        b"old sum",
                        b"old commit",
                    ]
                    for target, data in zip(targets, old_payloads):
                        target.write_bytes(data)

                    failed = False

                    def fail_selected_replace(source: Path, target: Path) -> None:
                        nonlocal failed
                        if Path(target).name == failure_name and not failed:
                            failed = True
                            raise OSError("injected publication failure")
                        os.replace(source, target)

                    with self.assertRaisesRegex(OSError, "injected"):
                        publish_release_payloads(
                            [
                                (targets[0], b"new archive"),
                                (targets[1], b"new manifest"),
                                (targets[2], b"new sum"),
                                (targets[3], b"new commit"),
                            ],
                            replace=fail_selected_replace,
                        )

                    self.assertEqual(
                        [target.read_bytes() for target in targets], old_payloads
                    )
                    self.assertEqual(
                        {item.name for item in directory.iterdir()},
                        {target.name for target in targets},
                    )

    def test_commit_marker_is_published_last(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            targets = [
                directory / "archive.zip",
                directory / "MANIFEST.json",
                directory / "SHA256SUMS.txt",
                directory / COMMIT_PATH.name,
            ]
            publication_order: list[str] = []

            def record_replace(source: Path, target: Path) -> None:
                publication_order.append(Path(target).name)
                os.replace(source, target)

            publish_release_payloads(
                [(target, target.name.encode("ascii")) for target in targets],
                replace=record_replace,
            )
            self.assertEqual(publication_order, [target.name for target in targets])
            self.assertEqual(publication_order[-1], COMMIT_PATH.name)


if __name__ == "__main__":
    unittest.main()
