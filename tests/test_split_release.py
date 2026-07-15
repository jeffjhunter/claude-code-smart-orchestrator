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
    GIVEAWAY_URL,
    TEAM_ARCHIVE,
    TEAM_PACKAGE_NAME,
    build_release_artifacts,
)


class SplitReleaseTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.release = build_release_artifacts()
        cls.giveaway = cls.release.bundles["giveaway"]
        cls.team = cls.release.bundles["team"]

    @staticmethod
    def members(archive: bytes, prefix: str) -> dict[str, bytes]:
        with zipfile.ZipFile(io.BytesIO(archive)) as bundle:
            return {
                info.filename.removeprefix(prefix + "/"): bundle.read(info)
                for info in bundle.infolist()
            }

    def test_release_builds_exactly_two_audience_specific_archives(self) -> None:
        self.assertEqual(set(self.release.bundles), {"giveaway", "team"})
        self.assertEqual(self.giveaway.archive_path, GIVEAWAY_ARCHIVE)
        self.assertEqual(self.team.archive_path, TEAM_ARCHIVE)
        self.assertEqual(self.giveaway.package_name, GIVEAWAY_PACKAGE_NAME)
        self.assertEqual(self.team.package_name, TEAM_PACKAGE_NAME)

    def test_giveaway_contains_resources_without_team_or_maintainer_assets(self) -> None:
        members = self.members(self.giveaway.archive, GIVEAWAY_PACKAGE_NAME)
        self.assertIn("START-HERE.md", members)
        self.assertIn("Claude-Code-Smart-Orchestrator-Kit.pdf", members)
        self.assertIn("starter/CLAUDE.md", members)
        self.assertIn("starter/.claude/agents/fable-planner.md", members)
        self.assertIn("starter/scripts/validate_kit.py", members)
        self.assertIn("starter/tests/test_validate_kit.py", members)
        self.assertIn("MANIFEST.json", members)
        for forbidden in (
            "social-post.md",
            "Claude-Code-Smart-Orchestrator-Infographic.png",
            "scripts/build_release.py",
            "scripts/verify_release.py",
            "source/guide.html",
            ".github/workflows/ci.yml",
            "tests/test_release_tools.py",
        ):
            self.assertNotIn(forbidden, members)

    def test_team_archive_is_copy_paste_ready_and_contains_no_giveaway_payload(self) -> None:
        members = self.members(self.team.archive, TEAM_PACKAGE_NAME)
        expected = {
            "START-HERE.md",
            "SOCIAL-POST.md",
            "COMMENT-REPLIES.md",
            "DELIVERY-COPY.md",
            "LAUNCH-CHECKLIST.md",
            "ASSET-LINKS.md",
            "Claude-Code-Smart-Orchestrator-Infographic.png",
            "MANIFEST.json",
        }
        self.assertEqual(set(members), expected)
        self.assertNotIn("starter/CLAUDE.md", members)
        self.assertNotIn("Claude-Code-Smart-Orchestrator-Kit.pdf", members)
        text = b"\n".join(
            data for name, data in members.items() if name.endswith(".md")
        ).decode("utf-8")
        self.assertNotIn("{{", text)
        self.assertIn(GIVEAWAY_URL, text)
        self.assertIn("ORCHESTRATE", text)

    def test_manifests_are_audience_specific(self) -> None:
        giveaway_manifest = json.loads(self.giveaway.manifest)
        team_manifest = json.loads(self.team.manifest)
        self.assertEqual(
            giveaway_manifest["name"],
            "Claude Code Smart Orchestrator Giveaway",
        )
        self.assertEqual(
            team_manifest["name"],
            "Claude Code Smart Orchestrator Team Assets",
        )
        giveaway_paths = {item["path"] for item in giveaway_manifest["files"]}
        team_paths = {item["path"] for item in team_manifest["files"]}
        self.assertNotIn("MANIFEST.json", giveaway_paths)
        self.assertNotIn("MANIFEST.json", team_paths)
        self.assertFalse(giveaway_paths & team_paths - {"START-HERE.md"})

    def test_checksum_lists_both_archives_and_commit_binds_all_outputs(self) -> None:
        checksum = self.release.checksum.decode("ascii").splitlines()
        self.assertEqual(len(checksum), 2)
        self.assertTrue(checksum[0].endswith(f"  {GIVEAWAY_ARCHIVE.name}"))
        self.assertTrue(checksum[1].endswith(f"  {TEAM_ARCHIVE.name}"))
        commit = json.loads(self.release.commit)
        self.assertEqual(
            [entry["path"] for entry in commit["outputs"]],
            [path.name for path, _ in self.release.outputs[:-1]],
        )
        self.assertEqual(self.release.outputs[-1][0].name, "RELEASE-COMMIT.json")

    def test_split_release_is_byte_for_byte_repeatable(self) -> None:
        second = build_release_artifacts()
        self.assertEqual(self.giveaway.archive, second.bundles["giveaway"].archive)
        self.assertEqual(self.team.archive, second.bundles["team"].archive)
        self.assertEqual(self.release.checksum, second.checksum)
        self.assertEqual(self.release.commit, second.commit)


if __name__ == "__main__":
    unittest.main()
