#!/usr/bin/env python3
"""Fail closed while verifying both audience-specific release archives."""

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
from typing import NoReturn, cast
import zipfile

from build_release import (
    CHECKSUM_PATH,
    COMMIT_PATH,
    DIST,
    ROOT,
    VERSION,
    BundleArtifacts,
    build_release_artifacts,
)
from validate_kit import find_secret_like_content  # pyright: ignore[reportMissingImports]

MANIFEST_KEYS = {"files", "format", "name", "note", "version"}
MANIFEST_ENTRY_KEYS = {"bytes", "path", "sha256"}
COMMIT_KEYS = {"format", "outputs", "package", "version"}
COMMIT_ENTRY_KEYS = {"bytes", "path", "sha256"}
SHA256_PATTERN = re.compile(r"[0-9a-f]{64}")
COMMIT_PACKAGE = "Claude Code Smart Orchestrator audience bundles"


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def fail(message: str) -> NoReturn:
    raise ValueError(message)


def safe_relative(name: str, package_name: str) -> PurePosixPath:
    if "\\" in name:
        fail(f"archive member uses a backslash: {name!r}")
    path = PurePosixPath(name)
    if path.is_absolute() or not path.parts or path.parts[0] != package_name:
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


def validate_manifest_schema(
    manifest: object, bundle: BundleArtifacts
) -> list[dict[str, object]]:
    if type(manifest) is not dict or set(manifest) != MANIFEST_KEYS:
        fail("manifest must contain exactly the documented top-level fields")
    manifest = cast(dict[str, object], manifest)
    if type(manifest["format"]) is not int or manifest["format"] != 1:
        fail("manifest format must be integer 1")
    if manifest["name"] != bundle.display_name:
        fail("manifest name is not canonical for this audience bundle")
    if manifest["version"] != VERSION:
        fail("manifest version does not match the release")
    if manifest["note"] != "MANIFEST.json intentionally does not hash itself.":
        fail("manifest note is not canonical")
    entries = manifest["files"]
    if type(entries) is not list:
        fail("manifest files field must be a list")

    expected_paths = [item.path for item in bundle.snapshots]
    observed_paths: list[str] = []
    expected_by_path = {item.path: item.data for item in bundle.snapshots}
    for entry in entries:
        if type(entry) is not dict or set(entry) != MANIFEST_ENTRY_KEYS:
            fail("manifest file entry has unknown or missing fields")
        entry = cast(dict[str, object], entry)
        relative = entry["path"]
        byte_count = entry["bytes"]
        content_hash = entry["sha256"]
        if type(relative) is not str:
            fail("manifest path must be a string")
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
        expected_data = expected_by_path.get(relative)
        if expected_data is None:
            fail(f"manifest contains an unexpected path: {relative!r}")
        if byte_count != len(expected_data) or content_hash != sha256(expected_data):
            fail(f"manifest does not match trusted source bytes: {relative!r}")
        observed_paths.append(relative)
    if observed_paths != expected_paths:
        fail("manifest file order or exact audience inventory is not canonical")
    return entries


def validate_commit_schema(
    marker: object,
    actual_outputs: dict[str, bytes],
    expected_names: list[str],
) -> list[dict[str, object]]:
    if type(marker) is not dict or set(marker) != COMMIT_KEYS:
        fail("release commit marker has unknown or missing top-level fields")
    marker = cast(dict[str, object], marker)
    if type(marker["format"]) is not int or marker["format"] != 1:
        fail("release commit marker format must be integer 1")
    if marker["package"] != COMMIT_PACKAGE or marker["version"] != VERSION:
        fail("release commit marker package or version is not canonical")
    entries = marker["outputs"]
    if type(entries) is not list:
        fail("release commit marker outputs must be a list")
    observed_names: list[str] = []
    for entry in entries:
        if type(entry) is not dict or set(entry) != COMMIT_ENTRY_KEYS:
            fail("release commit output has unknown or missing fields")
        entry = cast(dict[str, object], entry)
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


def verify_bundle_bytes(bundle: BundleArtifacts, archive_bytes: bytes) -> int:
    if archive_bytes != bundle.archive:
        fail(f"{bundle.key} archive bytes are not canonical")
    prefix = f"{bundle.package_name}/"
    expected_relatives = [item.path for item in bundle.snapshots] + ["MANIFEST.json"]
    expected_data = {item.path: item.data for item in bundle.snapshots}
    expected_data["MANIFEST.json"] = bundle.manifest

    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as archive:
        if archive.comment != b"":
            fail(f"{bundle.key} archive comment is not canonical")
        infos = archive.infolist()
        expected_names = [prefix + relative for relative in expected_relatives]
        if [info.filename for info in infos] != expected_names:
            fail(f"{bundle.key} archive member order or names are not canonical")
        for info, relative in zip(infos, expected_relatives):
            if info.is_dir():
                fail("archive contains an unexpected directory entry")
            if safe_relative(info.filename, bundle.package_name).as_posix() != relative:
                fail(f"archive member path is not canonical: {info.filename!r}")
            executable = relative != "MANIFEST.json" and Path(relative).suffix.casefold() in {
                ".py",
                ".ps1",
                ".sh",
            }
            expected_mode = stat.S_IFREG | (0o755 if executable else 0o644)
            if info.create_system != 3 or info.external_attr != expected_mode << 16:
                fail(f"archive mode or creator is not canonical: {info.filename!r}")
            if info.date_time != (1980, 1, 1, 0, 0, 0):
                fail(f"archive timestamp is not canonical: {info.filename!r}")
            if info.compress_type != zipfile.ZIP_STORED:
                fail(f"archive compression is not canonical: {info.filename!r}")
            if info.extra != b"" or info.comment != b"":
                fail(f"archive metadata is not canonical: {info.filename!r}")
            if info.flag_bits != 0 or info.internal_attr != 0:
                fail(f"archive flags are not canonical: {info.filename!r}")
            if info.create_version != 20 or info.extract_version != 20:
                fail(f"archive ZIP version fields are not canonical: {info.filename!r}")
            data = archive.read(info)
            if data != expected_data[relative]:
                fail(f"archive member bytes do not match source: {relative!r}")
            if relative.endswith(".md") and b"{{" in data:
                fail(f"unresolved placeholder in packaged text: {relative!r}")
            if relative not in {
                "Claude-Code-Smart-Orchestrator-Kit.pdf",
                "Claude-Code-Smart-Orchestrator-Infographic.png",
                "MANIFEST.json",
            }:
                text = data.decode("utf-8")
                findings = find_secret_like_content(text)
                if findings:
                    line, label = findings[0]
                    fail(f"possible {label} in packaged text: {relative}:{line}")
        manifest = strict_json(archive.read(prefix + "MANIFEST.json"), "embedded manifest")
        validate_manifest_schema(manifest, bundle)
        if "Claude-Code-Smart-Orchestrator-Kit.pdf" in expected_data:
            if not expected_data["Claude-Code-Smart-Orchestrator-Kit.pdf"].startswith(b"%PDF-"):
                fail("giveaway guide does not have a PDF header")
        if "Claude-Code-Smart-Orchestrator-Infographic.png" in expected_data:
            if not expected_data["Claude-Code-Smart-Orchestrator-Infographic.png"].startswith(b"\x89PNG\r\n\x1a\n"):
                fail("team infographic does not have a PNG header")
    return len(expected_relatives)


def _run_local_checks() -> None:
    commands = (
        [sys.executable, "-I", "starter/scripts/validate_kit.py"],
        [sys.executable, "-m", "unittest", "discover", "-s", "starter/tests", "-q"],
        [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-q"],
    )
    for command in commands:
        completed = subprocess.run(
            command,
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
            timeout=90,
        )
        if completed.returncode != 0:
            output = (completed.stdout + completed.stderr).strip()
            fail(f"trusted local check failed: {' '.join(command)}\n{output}")


def verify_release_set(
    directory: Path = DIST, *, run_local_checks: bool = True
) -> dict[str, tuple[int, str]]:
    trusted = build_release_artifacts()
    directory = directory.resolve()
    expected_outputs = trusted.outputs
    actual: dict[str, bytes] = {}
    for path, expected_data in expected_outputs:
        candidate = directory / path.name
        if not candidate.is_file():
            fail(f"release output is missing: {candidate.name}")
        if candidate.stat().st_size != len(expected_data):
            fail(f"release output size is not canonical: {candidate.name}")
        actual[candidate.name] = candidate.read_bytes()

    committed_names = [path.name for path, _ in expected_outputs[:-1]]
    marker = strict_json(actual[COMMIT_PATH.name], "RELEASE-COMMIT.json")
    validate_commit_schema(
        marker,
        {name: actual[name] for name in committed_names},
        committed_names,
    )
    if actual[COMMIT_PATH.name] != trusted.commit:
        fail("RELEASE-COMMIT.json bytes are not canonical")
    if actual[CHECKSUM_PATH.name] != trusted.checksum:
        fail("SHA256SUMS.txt bytes are not canonical")

    results: dict[str, tuple[int, str]] = {}
    for key, bundle in trusted.bundles.items():
        archive_bytes = actual[bundle.archive_path.name]
        manifest_bytes = actual[bundle.manifest_path.name]
        if manifest_bytes != bundle.manifest:
            fail(f"{key} adjacent manifest bytes are not canonical")
        manifest = strict_json(manifest_bytes, f"{key} manifest")
        validate_manifest_schema(manifest, bundle)
        count = verify_bundle_bytes(bundle, archive_bytes)
        results[key] = (count, sha256(archive_bytes))

    if run_local_checks:
        _run_local_checks()
    return results


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", type=Path, default=DIST)
    args = parser.parse_args(argv)
    try:
        results = verify_release_set(args.directory)
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
    for key, (count, archive_hash) in results.items():
        print(f"- {key}: {count} files, sha256 {archive_hash}")
    print("- two audience-specific archives, exact canonical bytes/order/metadata, strict manifests, coordinated commit marker, secret scan, local tests, and asset headers verified")
    print("- trust boundary: this verifier compares locally built archives with this trusted checkout; it is not a general untrusted-ZIP sandbox")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
