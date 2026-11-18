"""Five-book import/migration and fresh-install retrieval regression tests."""
import hashlib
import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "mm-write-short-drama" / "scripts"
sys.path.insert(0, str(SCRIPTS))
from import_book_capabilities import COMMIT, INPUTS, import_library
from knowledge_lib import iter_cards, render_card, rebuild_index


def snapshot(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


class BookCapabilitiesTests(unittest.TestCase):
    def test_draft_provenance_and_upstream_revision_are_distinct(self):
        with tempfile.TemporaryDirectory() as temp:
            kb = Path(temp) / "knowledge-base"
            result = import_library(kb, INPUTS)
            cards = list(iter_cards(kb))
            self.assertEqual(len(result["created"]), 24)
            story = [c for c in cards if c.get("story_number")]
            self.assertEqual(len(story), 19)
            self.assertEqual({c["capability_revision"] for c in story if c["story_number"] <= 6}, {2})
            self.assertEqual({c["capability_revision"] for c in story if c["story_number"] > 6}, {1})
            self.assertEqual({c["version"] for c in cards}, {1})
            self.assertEqual({c["status"] for c in cards}, {"draft"})
            self.assertEqual({c["source_commit"] for c in story}, {COMMIT})
            for card in story:
                self.assertEqual(len(card["original_source_sha256"]), 64)
                self.assertEqual(card["source"]["sha256"], card["import_sha256"])
                self.assertIn("index_split_", card["source_locator"])

    def test_activation_requires_review_then_reimport_is_byte_identical(self):
        with tempfile.TemporaryDirectory() as temp:
            kb = Path(temp) / "knowledge-base"
            with self.assertRaisesRegex(ValueError, "review-note"):
                import_library(kb, INPUTS, True)
            import_library(kb, INPUTS)
            result = import_library(kb, INPUTS, True, "Review source scope, exceptions, execution fields")
            self.assertEqual(len(result["upgraded"]), 24)
            self.assertEqual({c["status"] for c in iter_cards(kb)}, {"active"})
            before = snapshot(kb)
            again = import_library(kb, INPUTS, True, "Second invocation")
            self.assertEqual(len(again["reused"]), 24)
            self.assertEqual(snapshot(kb), before)

    def test_legacy_six_migrate_same_ids_and_archive_old_rules(self):
        with tempfile.TemporaryDirectory() as temp:
            kb = Path(temp) / "knowledge-base"
            import_library(kb, INPUTS)
            legacy_ids = set()
            for card in list(iter_cards(kb)):
                path = Path(card.pop("_path"))
                if card.get("story_number", 99) > 6:
                    path.unlink()
                    continue
                legacy_ids.add(card["id"])
                card.update(capability_revision=1, source_commit="legacy-six",
                            rule=card["rule"] + "（模拟旧六卡）", status="active")
                card.pop("import_sha256", None)
                path.write_text(render_card(card), encoding="utf-8")
            rebuild_index(kb)
            result = import_library(kb, INPUTS, True, "Reviewed Chinese revision-2 summaries", True)
            self.assertFalse(result["conflicts"])
            self.assertEqual(len(result["created"]), 18)
            self.assertEqual({item["card_id"] for item in result["upgraded"]}, legacy_ids)
            self.assertEqual(len(list((kb / "archive").glob("*.md"))), 6)
            self.assertEqual(len(list(iter_cards(kb))), 24)
            for archive in (kb / "archive").glob("*.md"):
                self.assertIn("模拟旧六卡", archive.read_text())

    def test_changed_same_revision_is_retained_as_conflict(self):
        with tempfile.TemporaryDirectory() as temp:
            kb = Path(temp) / "knowledge-base"
            import_library(kb, INPUTS, True, "Source reviewed")
            target = next(c for c in iter_cards(kb) if c.get("story_number") == 10)
            path = Path(target.pop("_path"))
            target["rule"] = "个人项目已裁决的另一种人物处理，必须保持。"
            path.write_text(render_card(target), encoding="utf-8")
            before = path.read_bytes()
            result = import_library(kb, INPUTS, True, "Do not override user differences")
            self.assertEqual(len(result["conflicts"]), 1)
            self.assertEqual(before, path.read_bytes())

    def test_tampered_pinned_summary_is_rejected_before_card_creation(self):
        import shutil
        with tempfile.TemporaryDirectory() as temp:
            folder = Path(temp) / "inputs"
            shutil.copytree(INPUTS, folder)
            with (folder / "story-01-expectation-gap.md").open("a") as handle:
                handle.write("\ntampered\n")
            kb = Path(temp) / "knowledge-base"
            with self.assertRaisesRegex(ValueError, "hash mismatch"):
                import_library(kb, folder)
            self.assertFalse(kb.exists())

    def test_empty_workspace_uses_builtin_and_full_execution_fields(self):
        with tempfile.TemporaryDirectory() as temp:
            result = subprocess.run([sys.executable, str(SCRIPTS / "search_knowledge.py"),
                "--capability", "cap.mckee-story-short-drama.scene-analysis", "--stage", "scene"],
                cwd=temp, text=True, capture_output=True, check=True)
            for expected in ("动作", "自检", "例外", "上游能力修订", COMMIT):
                self.assertIn(expected, result.stdout)

    def test_personal_capability_wins_without_mutating_library(self):
        with tempfile.TemporaryDirectory() as temp:
            kb = Path(temp) / "knowledge-base"
            import_library(kb, INPUTS, True, "Source reviewed")
            target = next(c for c in iter_cards(kb) if c.get("story_number") == 4)
            path = Path(target.pop("_path"))
            target["action"] = "PERSONAL-DECISION: use this project's approved scene analysis."
            path.write_text(render_card(target), encoding="utf-8")
            before = snapshot(kb)
            result = subprocess.run([sys.executable, str(SCRIPTS / "search_knowledge.py"),
                "--kb", str(kb), "--capability", target["capability_id"], "--format", "json"],
                text=True, capture_output=True, check=True)
            found = json.loads(result.stdout)
            self.assertEqual(len(found), 1)
            self.assertTrue(found[0]["action"].startswith("PERSONAL-DECISION"))
            self.assertEqual(snapshot(kb), before)

    def test_every_story_card_is_retrievable_at_its_declared_stages(self):
        with tempfile.TemporaryDirectory() as temp:
            for card in iter_cards(ROOT / "mm-write-short-drama" / "knowledge-base"):
                if not card.get("story_number"):
                    continue
                for stage in card["stage"]:
                    result = subprocess.run([sys.executable, str(SCRIPTS / "search_knowledge.py"),
                        "--capability", card["capability_id"], "--stage", stage, "--format", "json"],
                        cwd=temp, text=True, capture_output=True, check=True)
                    found = json.loads(result.stdout)
                    self.assertEqual([c["id"] for c in found], [card["id"]])

    def test_newer_upstream_revision_is_never_downgraded(self):
        with tempfile.TemporaryDirectory() as temp:
            kb = Path(temp) / "knowledge-base"
            import_library(kb, INPUTS, True, "Reviewed")
            target = next(c for c in iter_cards(kb) if c.get("story_number") == 4)
            path = Path(target.pop("_path"))
            target["capability_revision"] = 3
            path.write_text(render_card(target), encoding="utf-8")
            before = path.read_bytes()
            result = import_library(kb, INPUTS, True, "Reviewed")
            self.assertEqual(len(result["conflicts"]), 1)
            self.assertEqual(path.read_bytes(), before)


if __name__ == "__main__":
    unittest.main()
