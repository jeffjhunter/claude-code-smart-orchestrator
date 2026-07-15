from __future__ import annotations

import io
import os
from pathlib import Path
import tempfile
import unittest
import zipfile
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_release import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    COMMIT_PATH,
    build_release_artifacts,
    publish_release_payloads,
)
from verify_release import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    strict_json,
    validate_commit_schema,
    validate_manifest_schema,
    verify_bundle_bytes,
    verify_release_set,
)


class CanonicalReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.release = build_release_artifacts()

    def write_release(self, directory: Path) -> None:
        for path, data in self.release.outputs:
            (directory / path.name).write_bytes(data)

    def test_public_archive_is_canonical_and_repeatable(self) -> None:
        second = build_release_artifacts()
        for key, bundle in self.release.bundles.items():
            self.assertEqual(bundle.archive, second.bundles[key].archive)
            self.assertGreater(verify_bundle_bytes(bundle, bundle.archive), 1)

    def test_reordered_members_are_rejected_for_each_bundle(self) -> None:
        for key, bundle in self.release.bundles.items():
            with self.subTest(bundle=key):
                output = io.BytesIO()
                with zipfile.ZipFile(io.BytesIO(bundle.archive)) as source:
                    members = [
                        (info, source.read(info))
                        for info in reversed(source.infolist())
                    ]
                with zipfile.ZipFile(
                    output, "w", compression=zipfile.ZIP_STORED
                ) as target:
                    for info, data in members:
                        target.writestr(info, data)
                with self.assertRaisesRegex(ValueError, "canonical"):
                    verify_bundle_bytes(bundle, output.getvalue())

    def test_manifest_unknown_field_and_bool_size_are_rejected(self) -> None:
        bundle = self.release.bundles["giveaway"]
        manifest = strict_json(bundle.manifest, "test manifest")
        manifest["unexpected"] = True
        with self.assertRaisesRegex(ValueError, "exactly"):
            validate_manifest_schema(manifest, bundle)

        manifest = strict_json(bundle.manifest, "test manifest")
        manifest["files"][0]["bytes"] = True
        with self.assertRaisesRegex(ValueError, "byte count"):
            validate_manifest_schema(manifest, bundle)

    def test_duplicate_json_keys_are_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "duplicate key"):
            strict_json(b'{"format": 1, "format": 1}', "duplicate test")

    def test_commit_marker_schema_and_hashes_are_strict(self) -> None:
        actual = {path.name: data for path, data in self.release.outputs[:-1]}
        marker = strict_json(self.release.commit, "test commit marker")
        validate_commit_schema(marker, actual, list(actual))

        marker = strict_json(self.release.commit, "test commit marker")
        marker["outputs"][0]["sha256"] = "0" * 64
        with self.assertRaisesRegex(ValueError, "does not match"):
            validate_commit_schema(marker, actual, list(actual))

    def test_complete_release_set_verifies_from_clean_directory(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.write_release(directory)
            results = verify_release_set(directory, run_local_checks=False)
            self.assertEqual(set(results), {"giveaway"})

    def test_tampered_public_archive_fails_complete_release_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.write_release(directory)
            giveaway = self.release.bundles["giveaway"].archive_path.name
            path = directory / giveaway
            path.write_bytes(path.read_bytes() + b"tampered")
            with self.assertRaisesRegex(ValueError, "canonical|size|bytes"):
                verify_release_set(directory, run_local_checks=False)

    def test_tampered_manifest_fails_complete_release_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.write_release(directory)
            manifest = self.release.bundles["giveaway"].manifest_path.name
            (directory / manifest).write_bytes(b"{}\n")
            with self.assertRaisesRegex(ValueError, "canonical|manifest|commit"):
                verify_release_set(directory, run_local_checks=False)

    def test_unexpected_output_file_fails_complete_release_verification(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            self.write_release(directory)
            (directory / "Claude-Code-Smart-Orchestrator-Full-Kit-v2.1.0.zip").write_bytes(
                b"stale"
            )
            with self.assertRaisesRegex(ValueError, "unexpected release output"):
                verify_release_set(directory, run_local_checks=False)

    def test_partial_release_set_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            for path, data in self.release.outputs[:-1]:
                (directory / path.name).write_bytes(data)
            with self.assertRaisesRegex(ValueError, "inventory|missing"):
                verify_release_set(directory, run_local_checks=False)

class CoordinatedPublicationTests(unittest.TestCase):
    NAMES = [
        "giveaway.zip",
        "manifest.json",
        "SHA256SUMS.txt",
        COMMIT_PATH.name,
    ]

    def test_publish_failure_at_every_output_restores_last_good_set(self) -> None:
        for failed_name in self.NAMES:
            with self.subTest(failed_name=failed_name), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                targets = [directory / name for name in self.NAMES]
                old_payloads = [f"old-{i}".encode() for i in range(len(targets))]
                for target, data in zip(targets, old_payloads):
                    target.write_bytes(data)
                failed = False

                def fail_one_replace(source: Path, target: Path) -> None:
                    nonlocal failed
                    if Path(target).name == failed_name and not failed:
                        failed = True
                        raise OSError("injected publication failure")
                    os.replace(source, target)

                with self.assertRaisesRegex(OSError, "injected"):
                    publish_release_payloads(
                        [
                            (target, f"new-{i}".encode())
                            for i, target in enumerate(targets)
                        ],
                        replace=fail_one_replace,
                    )
                self.assertEqual(
                    [target.read_bytes() for target in targets], old_payloads
                )
                self.assertEqual(
                    {item.name for item in directory.iterdir()}, set(self.NAMES)
                )

    def test_publish_failure_with_no_previous_outputs_leaves_directory_empty(self) -> None:
        for failed_name in self.NAMES:
            with self.subTest(failed_name=failed_name), tempfile.TemporaryDirectory() as temporary:
                directory = Path(temporary)
                targets = [directory / name for name in self.NAMES]
                failed = False

                def fail_one_replace(source: Path, target: Path) -> None:
                    nonlocal failed
                    if Path(target).name == failed_name and not failed:
                        failed = True
                        raise OSError("injected publication failure")
                    os.replace(source, target)

                with self.assertRaisesRegex(OSError, "injected"):
                    publish_release_payloads(
                        [(target, target.name.encode()) for target in targets],
                        replace=fail_one_replace,
                    )
                self.assertEqual(list(directory.iterdir()), [])

    def test_publish_rejects_stale_output_before_writing(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            targets = [directory / name for name in self.NAMES]
            stale = directory / "Claude-Code-Smart-Orchestrator-Full-Kit-v2.1.0.zip"
            stale.write_bytes(b"stale")
            with self.assertRaisesRegex(RuntimeError, "unexpected release output"):
                publish_release_payloads(
                    [(target, target.name.encode()) for target in targets]
                )
            self.assertEqual({item.name for item in directory.iterdir()}, {stale.name})

    def test_commit_marker_is_published_last(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            targets = [directory / name for name in self.NAMES]
            publication_order: list[str] = []

            def record_replace(source: Path, target: Path) -> None:
                publication_order.append(Path(target).name)
                os.replace(source, target)

            publish_release_payloads(
                [(target, target.name.encode()) for target in targets],
                replace=record_replace,
            )
            self.assertEqual(publication_order, [target.name for target in targets])
            self.assertEqual(publication_order[-1], COMMIT_PATH.name)


if __name__ == "__main__":
    unittest.main()
