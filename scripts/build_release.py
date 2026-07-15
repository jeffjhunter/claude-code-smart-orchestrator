#!/usr/bin/env python3
"""Build the deterministic public Smart Orchestrator giveaway archive."""

from __future__ import annotations

import argparse
from contextlib import contextmanager
from dataclasses import dataclass
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

GIVEAWAY_PACKAGE_NAME = f"Claude-Code-Smart-Orchestrator-Giveaway-v{VERSION}"
DIST = ROOT / "dist"
GIVEAWAY_ARCHIVE = DIST / f"{GIVEAWAY_PACKAGE_NAME}.zip"
GIVEAWAY_MANIFEST_PATH = DIST / "MANIFEST.json"
CHECKSUM_PATH = DIST / "SHA256SUMS.txt"
COMMIT_PATH = DIST / "RELEASE-COMMIT.json"
LOCK_PATH = DIST / ".build-release.lock"

sys.path.insert(0, str(ROOT / "starter" / "scripts"))
from validate_kit import find_secret_like_content  # noqa: E402  # pyright: ignore[reportMissingImports]

EXCLUDED_PARTS = {
    ".git",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "__pycache__",
    "dist",
    "output",
    "tmp",
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
BINARY_SOURCE_PATHS = {
    "Claude-Code-Smart-Orchestrator-Kit.pdf",
}

GIVEAWAY_SOURCE_MAP = {
    "START-HERE.md": "README-FIRST.md",
    "Claude-Code-Smart-Orchestrator-Kit.pdf": "Claude-Code-Smart-Orchestrator-Kit.pdf",
    "CREDITS.md": "CREDITS.md",
    "LICENSE": "LICENSE",
    "LIVE-TEST-RESULTS.md": "LIVE-TEST-RESULTS.md",
    "SECURITY.md": "SECURITY.md",
    "requirements-dev.txt": "requirements-dev.txt",
    "starter/CLAUDE.md": "starter/CLAUDE.md",
    "starter/MODEL-POLICY.md": "starter/MODEL-POLICY.md",
    "starter/ROUTING-MATRIX.md": "starter/ROUTING-MATRIX.md",
    "starter/SETUP.md": "starter/SETUP.md",
    "starter/TEST-PROMPTS.md": "starter/TEST-PROMPTS.md",
    "starter/.claude/agents/architect.md": "starter/.claude/agents/architect.md",
    "starter/.claude/agents/deep-reasoner.md": "starter/.claude/agents/deep-reasoner.md",
    "starter/.claude/agents/fable-planner.md": "starter/.claude/agents/fable-planner.md",
    "starter/.claude/agents/fast-worker.md": "starter/.claude/agents/fast-worker.md",
    "starter/.claude/agents/qa-reviewer.md": "starter/.claude/agents/qa-reviewer.md",
    "starter/scripts/validate_kit.py": "starter/scripts/validate_kit.py",
    "starter/scripts/verify_direct_model_trace.py": "starter/scripts/verify_direct_model_trace.py",
    "starter/scripts/verify_runtime_trace.py": "starter/scripts/verify_runtime_trace.py",
    "starter/tests/test_validate_kit.py": "starter/tests/test_validate_kit.py",
    "starter/tests/test_verify_direct_model_trace.py": "starter/tests/test_verify_direct_model_trace.py",
    "starter/tests/test_verify_runtime_trace.py": "starter/tests/test_verify_runtime_trace.py",
}
MAINTAINER_PATHS = {
    ".gitattributes",
    ".gitignore",
    ".github/ISSUE_TEMPLATE/bug_report.yml",
    ".github/ISSUE_TEMPLATE/config.yml",
    ".github/ISSUE_TEMPLATE/feature_request.yml",
    ".github/PULL_REQUEST_TEMPLATE.md",
    ".github/dependabot.yml",
    ".github/workflows/ci.yml",
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
    "RELEASING.md",
    "VERSION",
    "scripts/build_release.py",
    "scripts/build_visual_assets.ps1",
    "scripts/verify_release.py",
    "source/guide.html",
    "source/infographic.svg",
    "Claude-Code-Smart-Orchestrator-Infographic.png",
    "tests/test_release_tools.py",
    "tests/test_public_release.py",
}
REPOSITORY_ALLOWED_PATHS = (
    set(GIVEAWAY_SOURCE_MAP.values())
    | MAINTAINER_PATHS
)


@dataclass(frozen=True)
class Snapshot:
    path: str
    data: bytes


@dataclass(frozen=True)
class BundleArtifacts:
    key: str
    package_name: str
    display_name: str
    archive_path: Path
    manifest_path: Path
    snapshots: tuple[Snapshot, ...]
    manifest: bytes
    archive: bytes


@dataclass(frozen=True)
class ReleaseArtifacts:
    bundles: dict[str, BundleArtifacts]
    checksum: bytes
    commit: bytes
    outputs: tuple[tuple[Path, bytes], ...]


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _safe_source_bytes(path: Path) -> bytes:
    relative = path.relative_to(ROOT).as_posix()
    data = path.read_bytes()
    if relative in BINARY_SOURCE_PATHS:
        return data
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise RuntimeError(f"Release text file is not UTF-8: {relative}") from exc
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    findings = find_secret_like_content(text)
    if findings:
        line, label = findings[0]
        raise RuntimeError(
            f"Refusing possible {label} in release text: {relative}:{line}"
        )
    return text.encode("utf-8")


def validate_repository_inventory() -> None:
    present: set[str] = set()
    for path in ROOT.rglob("*"):
        relative = path.relative_to(ROOT)
        if any(part in EXCLUDED_PARTS for part in relative.parts):
            continue
        if path.suffix == ".pyc":
            continue
        if path.is_symlink():
            raise RuntimeError(f"Refusing symbolic link: {relative.as_posix()}")
        if not path.is_file():
            continue
        name = relative.as_posix()
        lowered = path.name.casefold()
        if (
            lowered == ".env"
            or lowered.startswith(".env.")
            or path.suffix.casefold() in SENSITIVE_SUFFIXES
            or lowered.endswith("~")
        ):
            raise RuntimeError(f"Refusing sensitive or backup source: {name}")
        if name not in REPOSITORY_ALLOWED_PATHS:
            raise RuntimeError(f"Unallowlisted repository file: {name}")
        present.add(name)
    missing = sorted(REPOSITORY_ALLOWED_PATHS - present)
    if missing:
        raise RuntimeError("Repository is missing required files: " + ", ".join(missing))


def _snapshot_map(mapping: dict[str, str]) -> tuple[Snapshot, ...]:
    return tuple(
        Snapshot(output_path, _safe_source_bytes(ROOT / source_path))
        for output_path, source_path in sorted(mapping.items())
    )


def make_manifest(display_name: str, snapshots: tuple[Snapshot, ...]) -> bytes:
    entries = [
        {"path": item.path, "bytes": len(item.data), "sha256": digest(item.data)}
        for item in snapshots
    ]
    manifest = {
        "format": 1,
        "name": display_name,
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


def make_archive(
    package_name: str, snapshots: tuple[Snapshot, ...], manifest: bytes
) -> bytes:
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as bundle:
        prefix = f"{package_name}/"
        for item in snapshots:
            executable = Path(item.path).suffix.casefold() in {".py", ".ps1", ".sh"}
            bundle.writestr(zip_info(prefix + item.path, executable), item.data)
        bundle.writestr(zip_info(prefix + "MANIFEST.json"), manifest)
    return output.getvalue()


def make_checksum(archives: tuple[tuple[Path, bytes], ...]) -> bytes:
    lines = [f"{digest(data)}  {path.name}\n" for path, data in archives]
    return "".join(lines).encode("ascii")


def make_commit_marker(outputs: tuple[tuple[Path, bytes], ...]) -> bytes:
    marker = {
        "format": 1,
        "package": "Claude Code Smart Orchestrator public giveaway",
        "version": VERSION,
        "outputs": [
            {"path": path.name, "bytes": len(data), "sha256": digest(data)}
            for path, data in outputs
        ],
    }
    return (json.dumps(marker, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _build_bundle(
    *,
    key: str,
    package_name: str,
    display_name: str,
    archive_path: Path,
    manifest_path: Path,
    snapshots: tuple[Snapshot, ...],
) -> BundleArtifacts:
    manifest = make_manifest(display_name, snapshots)
    archive = make_archive(package_name, snapshots, manifest)
    return BundleArtifacts(
        key=key,
        package_name=package_name,
        display_name=display_name,
        archive_path=archive_path,
        manifest_path=manifest_path,
        snapshots=snapshots,
        manifest=manifest,
        archive=archive,
    )


def build_release_artifacts() -> ReleaseArtifacts:
    validate_repository_inventory()
    giveaway = _build_bundle(
        key="giveaway",
        package_name=GIVEAWAY_PACKAGE_NAME,
        display_name="Claude Code Smart Orchestrator Giveaway",
        archive_path=GIVEAWAY_ARCHIVE,
        manifest_path=GIVEAWAY_MANIFEST_PATH,
        snapshots=_snapshot_map(GIVEAWAY_SOURCE_MAP),
    )
    archive_outputs = ((giveaway.archive_path, giveaway.archive),)
    checksum = make_checksum(archive_outputs)
    committed_outputs = (
        *archive_outputs,
        (giveaway.manifest_path, giveaway.manifest),
        (CHECKSUM_PATH, checksum),
    )
    commit = make_commit_marker(committed_outputs)
    outputs = (*committed_outputs, (COMMIT_PATH, commit))
    return ReleaseArtifacts(
        bundles={"giveaway": giveaway},
        checksum=checksum,
        commit=commit,
        outputs=outputs,
    )


def validate_embedded_manifest(path: Path, expected_manifest: bytes) -> None:
    if path.read_bytes() != expected_manifest:
        raise RuntimeError("Embedded manifest does not match canonical bytes")


def _write_staged(path: Path, data: bytes) -> None:
    with path.open("xb") as handle:
        handle.write(data)
        handle.flush()
        os.fsync(handle.fileno())


def _fsync_directory(directory: Path) -> None:
    if os.name == "nt":
        return
    descriptor = os.open(directory, os.O_RDONLY)
    try:
        os.fsync(descriptor)
    finally:
        os.close(descriptor)


def _reject_unexpected_outputs(directory: Path, allowed_names: set[str]) -> None:
    unexpected = sorted(
        item.name for item in directory.iterdir() if item.name not in allowed_names
    )
    if unexpected:
        raise RuntimeError(
            "unexpected release output in destination; remove stale files before "
            "building: " + ", ".join(unexpected)
        )


@contextmanager
def _release_lock(directory: Path):
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
    payloads: list[tuple[Path, bytes]] | tuple[tuple[Path, bytes], ...],
    *,
    replace=os.replace,
) -> None:
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
        _reject_unexpected_outputs(
            directory,
            {path.name for path, _ in payloads} | {LOCK_PATH.name},
        )
        previous = {
            target: target.read_bytes() if target.is_file() else None
            for target, _ in payloads
        }
        try:
            for target, data in payloads:
                _write_staged(staged[target], data)
            _fsync_directory(directory)
            for target, _ in payloads[:-1]:
                replace(staged[target], target)
            _fsync_directory(directory)
            marker_target, _ = payloads[-1]
            replace(staged[marker_target], marker_target)
            _fsync_directory(directory)
        except Exception as publish_error:
            rollback_errors: list[str] = []
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
                except Exception as rollback_error:  # pragma: no cover
                    rollback_errors.append(f"{target.name}: {rollback_error}")
            try:
                _fsync_directory(directory)
            except Exception as rollback_error:  # pragma: no cover
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
    release = build_release_artifacts()
    publish_release_payloads(release.outputs)
    bundle = release.bundles["giveaway"]
    print(f"Built public giveaway: {bundle.archive_path}")
    print(f"SHA256: {digest(bundle.archive)}")
    print(f"Files: {len(bundle.snapshots) + 1} (including MANIFEST.json)")
    print(f"Commit marker: {COMMIT_PATH}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
