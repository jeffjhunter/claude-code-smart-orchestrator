from __future__ import annotations

import io
import json
from pathlib import Path
import sys
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from build_release import (  # noqa: E402  # pyright: ignore[reportMissingImports]
    GIVEAWAY_ARCHIVE,
    GIVEAWAY_PACKAGE_NAME,
    build_release_artifacts,
)


class PublicReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.release = build_release_artifacts()
        cls.giveaway = cls.release.bundles["giveaway"]

    @staticmethod
    def members(archive: bytes, prefix: str) -> dict[str, bytes]:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            return {
                info.filename.removeprefix(prefix + "/"): bundle.read(info)
                for info in bundle.infolist()
            }

    def test_release_builds_only_the_public_giveaway(self) -> None:
        self.assertEqual(set(self.release.bundles), {"giveaway"})
        self.assertEqual(self.giveaway.archive_path, GIVEAWAY_ARCHIVE)
        self.assertEqual(self.giveaway.package_name, GIVEAWAY_PACKAGE_NAME)

    def test_public_archive_contains_resources_without_internal_assets(self) -> None:
        members = self.members(self.giveaway.archive, GIVEAWAY_PACKAGE_NAME)
        for required in (
            "START-HERE.md",
            "Claude-Code-Smart-Orchestrator-Kit.pdf",
            "starter/CLAUDE.md",
            "starter/.claude/agents/fable-planner.md",
            "starter/scripts/validate_kit.py",
            "starter/tests/test_validate_kit.py",
            "MANIFEST.json",
        ):
            self.assertIn(required, members)
        for forbidden in (
            "SOCIAL-POST.md",
            "COMMENT-REPLIES.md",
            "DELIVERY-COPY.md",
            "LAUNCH-CHECKLIST.md",
            "ASSET-LINKS.md",
            "Claude-Code-Smart-Orchestrator-Infographic.png",
            "scripts/build_release.py",
            "scripts/verify_release.py",
            "source/guide.html",
            ".github/workflows/ci.yml",
            "tests/test_release_tools.py",
        ):
            self.assertNotIn(forbidden, members)
        text = b"\n".join(
            data for name, data in members.items() if name.endswith(".md")
        ).decode("utf-8")
        self.assertNotIn("{{", text)
        self.assertNotIn("AI Money Group team", text)

    def test_manifest_checksum_and_commit_cover_only_public_outputs(self) -> None:
        manifest = json.loads(self.giveaway.manifest)
        self.assertEqual(manifest["name"], "Claude Code Smart Orchestrator Giveaway")
        self.assertNotIn("MANIFEST.json", {item["path"] for item in manifest["files"]})

        checksum = self.release.checksum.decode("ascii").splitlines()
        self.assertEqual(len(checksum), 1)
        self.assertTrue(checksum[0].endswith(f"  {GIVEAWAY_ARCHIVE.name}"))

        commit = json.loads(self.release.commit)
        self.assertEqual(
            [entry["path"] for entry in commit["outputs"]],
            [path.name for path, _ in self.release.outputs[:-1]],
        )
        self.assertEqual(len(commit["outputs"]), 3)
        self.assertEqual(self.release.outputs[-1][0].name, "RELEASE-COMMIT.json")

    def test_public_release_is_byte_for_byte_repeatable(self) -> None:
        second = build_release_artifacts()
        self.assertEqual(self.giveaway.archive, second.bundles["giveaway"].archive)
        self.assertEqual(self.release.checksum, second.checksum)
        self.assertEqual(self.release.commit, second.commit)


if __name__ == "__main__":
    unittest.main()
