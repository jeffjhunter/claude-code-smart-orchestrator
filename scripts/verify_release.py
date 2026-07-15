#!/usr/bin/env python3
"""Fail closed while verifying a built Smart Orchestrator release ZIP."""

from __future__ import annotations

import argparse
import hashlib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import sys
import zipfile

from build_release import (
    ALLOWED_PATHS,
    ARCHIVE,
    BINARY_PATHS,
    CHECKSUM_PATH,
    COMMIT_PATH,
    MANIFEST_PATH,
    PACKAGE_NAME,
    ROOT,
    VERSION,
    collect_files,
    make_archive,
    make_checksum,
    make_commit_marker,
    make_manifest,
    snapshot_files,
)
from validate_kit import find_secret_like_content

DEFAULT_ARCHIVE = ROOT / "dist" / f"{PACKAGE_NAME}.zip"
MANIFEST_KEYS = {"files", "format", "name", "note", "version"}
MANIFEST_ENTRY_KEYS = {"bytes", "path", "sha256"}
COMMIT_KEYS = {"format", "outputs", "package", "version"}
COMMIT_ENTRY_KEYS = {"bytes", "path", "sha256"}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fail(message: str) -> None:
    raise ValueError(message)


def safe_relative(name: str) -> PurePosixPath:
    if "\\" in name:
        fail(f"archive member uses a backslash: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or path.parts[0] != PACKAGE_NAME:
        fail(f"archive member is outside the package root: {name!r}")
    relative = PurePosixPath(*path.parts[1:])
    if not relative.parts or any(
        part in {"", ".", ".."} or ":" in part or "\x00" in part
        for part in relative.parts
    ):
        fail(f"archive member has an unsafe path: {name!r}")
    return relative


def _unique_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            fail(f"JSON object contains a duplicate key: {key!r}")
        result[key] = value
    return result


def strict_json(data: bytes, label: str) -> object:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError as exc:
        fail(f"{label} is not UTF-8: {exc}")
    try:
        return json.loads(text, object_pairs_hook=_unique_object)
    except json.JSONDecodeError as exc:
        fail(f"{label} is not valid JSON: {exc}")


def validate_manifest_schema(manifest: object) -> list[dict[str, object]]:
    if type(manifest) is not dict or set(manifest) != MANIFEST_KEYS:
        fail("manifest must contain exactly the documented top-level fields")
    if type(manifest["format"]) is not int or manifest["format"] != 1:
        fail("manifest format must be integer 1")
    if manifest["name"] != "Claude Code Smart Orchestrator Kit":
        fail("manifest name is not canonical")
    if manifest["version"] != VERSION:
        fail("manifest version does not match the release")
    if manifest["note"] != "MANIFEST.json intentionally does not hash itself.":
        fail("manifest note is not canonical")
    entries = manifest["files"]
    if type(entries) is not list:
        fail("manifest files field must be a list")

    expected_paths = sorted(ALLOWED_PATHS)
    observed_paths: list[str] = []
    for entry in entries:
        if type(entry) is not dict or set(entry) != MANIFEST_ENTRY_KEYS:
            fail("manifest file entry has unknown or missing fields")
        relative = entry["path"]
        byte_count = entry["bytes"]
        content_hash = entry["sha256"]
        if type(relative) is not str:
            fail("manifest path must be a string")
        # Apply the same path rules without permitting a package-root escape.
        candidate = PurePosixPath(relative)
        if (
            candidate.is_absolute()
            or not candidate.parts
            or candidate.as_posix() != relative
            or any(
            part in {"", ".", ".."} or ":" in part or "\x00" in part
                for part in candidate.parts
            )
        ):
            fail(f"manifest contains an unsafe path: {relative!r}")
        if type(byte_count) is not int or byte_count < 0:
            fail(f"manifest byte count is invalid: {relative!r}")
        if type(content_hash) is not str or not SHA256_PATTERN.fullmatch(content_hash):
            fail(f"manifest SHA-256 is invalid: {relative!r}")
        observed_paths.append(relative)
    if observed_paths != expected_paths:
        fail("manifest file order or exact allowlist is not canonical")
    return entries


def validate_commit_schema(
    marker: object, actual_outputs: dict[str, bytes]
) -> list[dict[str, object]]:
    if type(marker) is not dict or set(marker) != COMMIT_KEYS:
        fail("release commit marker has unknown or missing top-level fields")
    if type(marker["format"]) is not int or marker["format"] != 1:
        fail("release commit marker format must be integer 1")
    if marker["package"] != PACKAGE_NAME or marker["version"] != VERSION:
        fail("release commit marker package or version is not canonical")
    entries = marker["outputs"]
    if type(entries) is not list:
        fail("release commit marker outputs must be a list")
    expected_names = [ARCHIVE.name, MANIFEST_PATH.name, CHECKSUM_PATH.name]
    observed_names: list[str] = []
    for entry in entries:
        if type(entry) is not dict or set(entry) != COMMIT_ENTRY_KEYS:
            fail("release commit output has unknown or missing fields")
        name = entry["path"]
        byte_count = entry["bytes"]
        content_hash = entry["sha256"]
        if type(name) is not str:
            fail("release commit output path must be a string")
        if type(byte_count) is not int or byte_count < 0:
            fail(f"release commit byte count is invalid: {name!r}")
        if type(content_hash) is not str or not SHA256_PATTERN.fullmatch(content_hash):
            fail(f"release commit SHA-256 is invalid: {name!r}")
        data = actual_outputs.get(name)
        if data is None:
            fail(f"release commit references a missing output: {name!r}")
        if byte_count != len(data) or content_hash != sha256(data):
            fail(f"release commit does not match output bytes: {name!r}")
        observed_names.append(name)
    if observed_names != expected_names:
        fail("release commit output order or inventory is not canonical")
    return entries


def verify_canonical_zip_bytes(
    archive_bytes: bytes,
    snapshots: list[tuple[Path, bytes]],
    manifest_bytes: bytes,
) -> int:
    """Require exact canonical bytes, then independently inspect ZIP metadata."""
    expected_archive = make_archive(snapshots, manifest_bytes)
    if archive_bytes != expected_archive:
        fail("archive bytes are not the exact canonical release representation")

    prefix = f"{PACKAGE_NAME}/"
    expected_relatives = [
        path.relative_to(ROOT).as_posix() for path, _ in snapshots
    ] + ["MANIFEST.json"]
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as bundle:
        if bundle.comment != b"":
            fail("archive-level ZIP comment is not canonical")
        infos = bundle.infolist()
        if [info.filename for info in infos] != [
            prefix + relative for relative in expected_relatives
        ]:
            fail("archive member order or names are not canonical")

        for info, relative in zip(infos, expected_relatives):
            if info.is_dir():
                fail("archive contains an unexpected directory entry")
            if safe_relative(info.filename).as_posix() != relative:
                fail(f"archive member path is not canonical: {info.filename!r}")
            executable = relative != "MANIFEST.json" and Path(relative).suffix.casefold() in {
                ".py",
                ".ps1",
                ".sh",
            }
            expected_mode = stat.S_IFREG | (0o755 if executable else 0o644)
            expected_external = expected_mode << 16
            if info.create_system != 3 or info.external_attr != expected_external:
                fail(f"archive mode or creator is not canonical: {info.filename!r}")
            if info.date_time != (1980, 1, 1, 0, 0, 0):
                fail(f"archive timestamp is not canonical: {info.filename!r}")
            if info.compress_type != zipfile.ZIP_STORED:
                fail(f"archive compression is not canonical: {info.filename!r}")
            if info.extra != b"" or info.comment != b"":
                fail(f"archive member extra fields or comment are not canonical: {info.filename!r}")
            if info.flag_bits != 0 or info.internal_attr != 0:
                fail(f"archive flags are not canonical: {info.filename!r}")
            if info.create_version != 20 or info.extract_version != 20:
                fail(f"archive ZIP version fields are not canonical: {info.filename!r}")
            if info.reserved != 0 or info.volume != 0:
                fail(f"archive reserved metadata is not canonical: {info.filename!r}")
            if info.compress_size != info.file_size:
                fail(f"stored archive member size is not canonical: {info.filename!r}")
            # Reading verifies each CRC before any archive payload is trusted.
            bundle.read(info)
    return len(expected_relatives)


def verify_archive(path: Path) -> tuple[int, str]:
    if path.name != ARCHIVE.name:
        fail(f"archive filename must be canonical: {ARCHIVE.name}")

    snapshots = snapshot_files(collect_files())
    expected_manifest = make_manifest(snapshots)
    expected_archive = make_archive(snapshots, expected_manifest)
    expected_checksum = make_checksum(expected_archive)
    expected_commit = make_commit_marker(
        expected_archive, expected_manifest, expected_checksum
    )

    # Bound archive reads using the trusted expected size, then compare every
    # byte before opening it as a ZIP.
    if path.stat().st_size != len(expected_archive):
        fail("archive size is not canonical")
    archive_bytes = path.read_bytes()
    manifest_path = path.parent / MANIFEST_PATH.name
    checksum_path = path.parent / CHECKSUM_PATH.name
    commit_path = path.parent / COMMIT_PATH.name
    for adjacent in (manifest_path, checksum_path, commit_path):
        if not adjacent.is_file():
            fail(f"adjacent release output is missing: {adjacent.name}")
        if adjacent.stat().st_size > 1_000_000:
            fail(f"adjacent release output is unexpectedly large: {adjacent.name}")
    manifest_bytes = manifest_path.read_bytes()
    checksum_bytes = checksum_path.read_bytes()
    commit_bytes = commit_path.read_bytes()

    manifest = strict_json(manifest_bytes, "adjacent MANIFEST.json")
    entries = validate_manifest_schema(manifest)
    actual_outputs = {
        path.name: archive_bytes,
        MANIFEST_PATH.name: manifest_bytes,
        CHECKSUM_PATH.name: checksum_bytes,
    }
    marker = strict_json(commit_bytes, "RELEASE-COMMIT.json")
    validate_commit_schema(marker, actual_outputs)

    if manifest_bytes != expected_manifest:
        fail("adjacent MANIFEST.json bytes are not canonical")
    if checksum_bytes != expected_checksum:
        fail("SHA256SUMS.txt bytes are not canonical")
    if commit_bytes != expected_commit:
        fail("RELEASE-COMMIT.json bytes are not canonical")

    count = verify_canonical_zip_bytes(
        archive_bytes, snapshots, expected_manifest
    )
    archive_hash = sha256(archive_bytes)

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as bundle:
        relative_infos = {
            safe_relative(info.filename).as_posix(): info
            for info in bundle.infolist()
        }
        for entry in entries:
            relative = entry["path"]
            info = relative_infos[relative]
            data = bundle.read(info)
            if entry["bytes"] != len(data) or entry["sha256"] != sha256(data):
                fail(f"manifest size or hash mismatch: {relative!r}")
            if relative not in BINARY_PATHS:
                text = data.decode("utf-8")
                findings = find_secret_like_content(text)
                if findings:
                    line, label = findings[0]
                    fail(f"possible {label} in packaged text: {relative}:{line}")

        if not bundle.read(relative_infos["Claude-Code-Smart-Orchestrator-Kit.pdf"]).startswith(b"%PDF-"):
            fail("packaged guide does not have a PDF header")
        if not bundle.read(relative_infos["Claude-Code-Smart-Orchestrator-Infographic.png"]).startswith(b"\x89PNG\r\n\x1a\n"):
            fail("packaged infographic does not have a PNG header")

    commands = (
        [sys.executable, "-I", "starter/scripts/validate_kit.py"],
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "starter/tests",
            "-q",
        ],
        [
            sys.executable,
            "-m",
            "unittest",
            "discover",
            "-s",
            "tests",
            "-q",
        ],
    )
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=60,
        )
        if completed.returncode != 0:
            output = (completed.stdout + completed.stderr).strip()
            fail(f"trusted local check failed: {' '.join(command)}\n{output}")

    return count, archive_hash


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", nargs="?", type=Path, default=DEFAULT_ARCHIVE)
    args = parser.parse_args(argv)
    try:
        count, archive_hash = verify_archive(args.archive.resolve())
    except (
        OSError,
        RuntimeError,
        ValueError,
        zipfile.BadZipFile,
        json.JSONDecodeError,
        subprocess.TimeoutExpired,
    ) as exc:
        print("RELEASE VERIFICATION FAIL")
        print(f"- {exc}")
        return 1
    print("RELEASE VERIFICATION PASS")
    print(f"- archive: {args.archive.resolve()}")
    print(f"- files: {count}")
    print(f"- sha256: {archive_hash}")
    print("- exact canonical ZIP bytes/order/metadata, strict manifests, coordinated commit marker, trusted-source match, secret scan, local tests, and asset headers verified")
    print("- trust boundary: this verifier compares a locally built archive with this trusted checkout; it is not a general untrusted-ZIP sandbox")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
