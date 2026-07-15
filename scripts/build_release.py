#!/usr/bin/env python3
"""Build a deterministic, checksummed Smart Orchestrator release archive."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
import hashlib
import io
import json
import os
from pathlib import Path
import re
import secrets
import stat
import sys
import zipfile


ROOT = Path(__file__).resolve().parents[1]
VERSION = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
if not re.fullmatch(r"\d+\.\d+\.\d+(?:-[0-9A-Za-z.-]+)?", VERSION):
    raise RuntimeError("VERSION must be a filename-safe semantic version")
PACKAGE_NAME = f"Claude-Code-Smart-Orchestrator-Full-Kit-v{VERSION}"
DIST = ROOT / "dist"
ARCHIVE = DIST / f"{PACKAGE_NAME}.zip"
MANIFEST_PATH = DIST / "MANIFEST.json"
CHECKSUM_PATH = DIST / "SHA256SUMS.txt"
COMMIT_PATH = DIST / "RELEASE-COMMIT.json"
LOCK_PATH = DIST / ".build-release.lock"

sys.path.insert(0, str(ROOT / "starter" / "scripts"))
from validate_kit import find_secret_like_content  # noqa: E402

EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    "__pycache__",
    "dist",
    "output",
    "tmp",
}
ALLOWED_PATHS = {
    ".gitattributes",
    ".gitignore",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/dependabot.yml",
    ".github/workflows/ci.yml",
    "README-FIRST.md",
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "CREDITS.md",
    "LICENSE",
    "LIVE-TEST-RESULTS.md",
    "RELEASING.md",
    "requirements-dev.txt",
    "social-post.md",
    "SECURITY.md",
    "VERSION",
    "Claude-Code-Smart-Orchestrator-Kit.pdf",
    "Claude-Code-Smart-Orchestrator-Infographic.png",
    "scripts/build_release.py",
    "scripts/build_visual_assets.ps1",
    "scripts/verify_release.py",
    "source/guide.html",
    "source/infographic.svg",
    "starter/CLAUDE.md",
    "starter/MODEL-POLICY.md",
    "starter/ROUTING-MATRIX.md",
    "starter/SETUP.md",
    "starter/TEST-PROMPTS.md",
    "starter/.claude/agents/fable-planner.md",
    "starter/.claude/agents/architect.md",
    "starter/.claude/agents/deep-reasoner.md",
    "starter/.claude/agents/fast-worker.md",
    "starter/.claude/agents/qa-reviewer.md",
    "starter/scripts/validate_kit.py",
    "starter/scripts/verify_direct_model_trace.py",
    "starter/scripts/verify_runtime_trace.py",
    "starter/tests/test_verify_direct_model_trace.py",
    "starter/tests/test_validate_kit.py",
    "starter/tests/test_verify_runtime_trace.py",
    "tests/test_release_tools.py",
}
BINARY_PATHS = {
    "Claude-Code-Smart-Orchestrator-Kit.pdf",
    "Claude-Code-Smart-Orchestrator-Infographic.png",
}
SENSITIVE_SUFFIXES = {
    ".bak",
    ".backup",
    ".env",
    ".jsonl",
    ".key",
    ".orig",
    ".p12",
    ".pem",
    ".pfx",
}


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def validate_embedded_manifest(path: Path, expected_manifest: bytes) -> None:
    """Accept a package-root manifest only when it is the canonical one."""
    if path.read_bytes() != expected_manifest:
        raise RuntimeError(
            "Root MANIFEST.json is present but does not exactly match "
            "the current canonical package manifest"
        )


def collect_files() -> list[Path]:
    files: list[Path] = []
    embedded_manifest = ROOT / "MANIFEST.json"
    embedded_manifest_present = False
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise RuntimeError(f"Refusing to package symbolic link: {relative.as_posix()}")
        if path.is_file():
            if path == embedded_manifest:
                embedded_manifest_present = True
                continue
            relative_name = relative.as_posix()
            lowered_name = path.name.casefold()
            if (
                lowered_name == ".env"
                or lowered_name.startswith(".env.")
                or path.suffix.casefold() in SENSITIVE_SUFFIXES
                or lowered_name.endswith("~")
            ):
                raise RuntimeError(
                    f"Refusing sensitive or backup release source: {relative_name}"
                )
            if relative_name not in ALLOWED_PATHS:
                raise RuntimeError(f"Unallowlisted release source file: {relative_name}")
            files.append(path)

    files.sort(key=lambda item: item.relative_to(ROOT).as_posix())
    present = {path.relative_to(ROOT).as_posix() for path in files}
    missing = sorted(ALLOWED_PATHS - present)
    if missing:
        raise RuntimeError("Release is missing required files: " + ", ".join(missing))
    if embedded_manifest_present:
        expected_manifest = make_manifest(snapshot_files(files))
        validate_embedded_manifest(embedded_manifest, expected_manifest)
    return files


def release_bytes(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    data = path.read_bytes()
    if relative in BINARY_PATHS:
        return data
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"Release text file is not UTF-8: {relative}") from exc
    return text.replace("\r\n", "\n").replace("\r", "\n").encode("utf-8")


def snapshot_files(files: list[Path]) -> list[tuple[Path, bytes]]:
    snapshots: list[tuple[Path, bytes]] = []
    for path in files:
        data = release_bytes(path)
        relative = path.relative_to(ROOT).as_posix()
        if relative not in BINARY_PATHS:
            text = data.decode("utf-8")
            findings = find_secret_like_content(text)
            if findings:
                line, label = findings[0]
                raise RuntimeError(
                    f"Refusing possible {label} in release text: {relative}:{line}"
                )
        snapshots.append((path, data))
    return snapshots


def make_manifest(snapshots: list[tuple[Path, bytes]]) -> bytes:
    entries = []
    for path, data in snapshots:
        entries.append(
            {
                "path": path.relative_to(ROOT).as_posix(),
                "bytes": len(data),
                "sha256": digest(data),
            }
        )
    manifest = {
        "format": 1,
        "name": "Claude Code Smart Orchestrator Kit",
        "version": VERSION,
        "note": "MANIFEST.json intentionally does not hash itself.",
        "files": entries,
    }
    return (json.dumps(manifest, indent=2, sort_keys=True) + "\n").encode("utf-8")


def zip_info(archive_path: str, executable: bool = False) -> zipfile.ZipInfo:
    info = zipfile.ZipInfo(archive_path, date_time=(1980, 1, 1, 0, 0, 0))
    info.create_system = 3
    mode = stat.S_IFREG | (0o755 if executable else 0o644)
    info.external_attr = mode << 16
    info.compress_type = zipfile.ZIP_STORED
    return info


def make_archive(snapshots: list[tuple[Path, bytes]], manifest: bytes) -> bytes:
    """Return the one canonical byte representation of this release ZIP."""
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as bundle:
        bundle.comment = b""
        prefix = f"{PACKAGE_NAME}/"
        for path, data in snapshots:
            relative = path.relative_to(ROOT).as_posix()
            executable = path.suffix.casefold() in {".py", ".ps1", ".sh"}
            bundle.writestr(zip_info(prefix + relative, executable), data)
        bundle.writestr(zip_info(prefix + "MANIFEST.json"), manifest)
    return output.getvalue()


def make_checksum(archive: bytes) -> bytes:
    return f"{digest(archive)}  {ARCHIVE.name}\n".encode("ascii")


def make_commit_marker(
    archive: bytes, manifest: bytes, checksum: bytes
) -> bytes:
    """Describe the complete output set; this marker is published last."""
    payloads = (
        (ARCHIVE.name, archive),
        (MANIFEST_PATH.name, manifest),
        (CHECKSUM_PATH.name, checksum),
    )
    marker = {
        "format": 1,
        "package": PACKAGE_NAME,
        "version": VERSION,
        "outputs": [
            {"path": name, "bytes": len(data), "sha256": digest(data)}
            for name, data in payloads
        ],
    }
    return (json.dumps(marker, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _write_staged(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_directory(directory: Path) -> None:
    """Persist directory-entry changes where the platform exposes that API."""
    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


@contextmanager
def _release_lock(directory: Path):
    """Prevent two builders from interleaving a multi-file publication."""
    directory.mkdir(parents=True, exist_ok=True)
    lock = directory / LOCK_PATH.name
    try:
        descriptor = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o600)
    except FileExistsError as exc:
        raise RuntimeError(
            f"Release build lock already exists: {lock}. "
            "Remove it only after confirming no release build is running."
        ) from exc
    try:
        with os.fdopen(descriptor, "w", encoding="ascii", newline="\n") as handle:
            handle.write(f"pid={os.getpid()}\n")
            handle.flush()
            os.fsync(handle.fileno())
        yield
    finally:
        lock.unlink(missing_ok=True)


def publish_release_payloads(
    payloads: list[tuple[Path, bytes]],
    *,
    replace=os.replace,
) -> None:
    """Publish a coordinated output set while retaining the last good set.

    The commit marker must be the final payload. All bytes are staged and
    flushed before any final path changes. Ordinary publication failures are
    rolled back to the prior byte-for-byte state; a process crash is detected
    by the marker because it is replaced only after all other outputs.
    """
    if not payloads:
        raise ValueError("release payload list must not be empty")
    directories = {path.parent.resolve() for path, _ in payloads}
    if len(directories) != 1:
        raise ValueError("release payloads must share one output directory")
    if payloads[-1][0].name != COMMIT_PATH.name:
        raise ValueError("release commit marker must be the final payload")
    paths = [path for path, _ in payloads]
    if len(paths) != len(set(paths)):
        raise ValueError("release payload paths must be unique")

    directory = next(iter(directories))
    nonce = f"{os.getpid()}-{secrets.token_hex(8)}"
    staged = {
        target: target.with_name(f".{target.name}.{nonce}.tmp")
        for target, _ in payloads
    }
    rollback_temps: list[Path] = []

    with _release_lock(directory):
        previous: dict[Path, bytes | None] = {
            target: target.read_bytes() if target.is_file() else None
            for target, _ in payloads
        }
        try:
            for target, data in payloads:
                _write_staged(staged[target], data)
            _fsync_directory(directory)

            # The marker is last, so readers never accept a partially
            # published set as the newly committed release.
            for target, _ in payloads[:-1]:
                replace(staged[target], target)
            _fsync_directory(directory)
            marker_target, _ = payloads[-1]
            replace(staged[marker_target], marker_target)
            _fsync_directory(directory)
        except Exception as publish_error:
            rollback_errors: list[str] = []
            # Restore data outputs first and the old marker last.
            for target, _ in payloads:
                old_data = previous[target]
                try:
                    if old_data is None:
                        target.unlink(missing_ok=True)
                    else:
                        rollback = target.with_name(
                            f".{target.name}.{nonce}.rollback"
                        )
                        rollback_temps.append(rollback)
                        _write_staged(rollback, old_data)
                        os.replace(rollback, target)
                except Exception as rollback_error:  # pragma: no cover - catastrophic I/O
                    rollback_errors.append(f"{target.name}: {rollback_error}")
            try:
                _fsync_directory(directory)
            except Exception as rollback_error:  # pragma: no cover - catastrophic I/O
                rollback_errors.append(f"directory sync: {rollback_error}")
            if rollback_errors:
                raise RuntimeError(
                    "Release publication failed and rollback was incomplete: "
                    + "; ".join(rollback_errors)
                ) from publish_error
            raise
        finally:
            for temporary in (*staged.values(), *rollback_temps):
                temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.parse_args(argv)
    files = collect_files()
    snapshots = snapshot_files(files)
    manifest = make_manifest(snapshots)
    archive = make_archive(snapshots, manifest)
    checksum = make_checksum(archive)
    commit_marker = make_commit_marker(archive, manifest, checksum)
    publish_release_payloads(
        [
            (ARCHIVE, archive),
            (MANIFEST_PATH, manifest),
            (CHECKSUM_PATH, checksum),
            (COMMIT_PATH, commit_marker),
        ]
    )

    print(f"Built: {ARCHIVE}")
    print(f"SHA256: {digest(archive)}")
    print(f"Files: {len(snapshots) + 1} (including MANIFEST.json)")
    print(f"Commit marker: {COMMIT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
