"""Behavioral regressions for versioned reviews, confirmation, and release gates.

The tiny review reports here are explicitly software fixtures, not literary evaluations.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "mm-write-short-drama/scripts"
sys.path.insert(0, str(SCRIPTS))
import workflow_lib as wf
sys.path.insert(0, str(SCRIPTS.parent / "evals/fixtures"))


from workflow_fixture import run, seed, finish_review, confirm, fixture_polish


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name) / "project"
        seed(self.root)

    def tearDown(self):
        self.temp.cleanup()

    def test_no_mode_can_bypass_confirmation_or_restart(self):
        for mode in ("strict", "assisted", "automatic"):
            state = wf.read_json(self.root / ".drama/project-state.json")
            state["reviewMode"] = mode
            wf.save_json(self.root / ".drama/project-state.json", state)
            result = run("update_episode_state.py", self.root, "--episode", 1, "--to", "planned")
            self.assertNotEqual(result.returncode, 0)
            self.assertIn("confirmation", result.stderr)
            self.assertTrue(wf.synchronize(self.root)["writingErrors"])
        finish_review(self.root, "treatment")
        finish_review(self.root, "outline")
        wf.confirm_outline(self.root, "revise", "测试退回修改", "fixture", "2集")
        self.assertTrue(wf.writing_errors(self.root))
        wf.confirm_outline(self.root, "confirm", "测试改后确认", "fixture", "2集")
        self.assertFalse(wf.writing_errors(self.root))

    def test_first_pass_cannot_reveal_context_and_missing_chunk_is_incomplete(self):
        session = wf.review_pack(self.root, "treatment", [])
        with self.assertRaisesRegex(ValueError, "first read"):
            wf.reveal_context(self.root, session["sessionId"])
        path = self.root / "first.json"
        wf.save_json(path, {"readChunks": [], "observations": []})
        with self.assertRaisesRegex(ValueError, "reading incomplete"):
            wf.submit_first_read(self.root, session["sessionId"], path)

    def test_first_read_pack_excludes_control_and_ledger_answers(self):
        confirm(self.root)
        session = wf.review_pack(self.root, "batch", ["001"])
        pack = (self.root / session["chunks"][0]["path"]).read_text()
        self.assertIn("先把借的还上", pack)
        self.assertNotIn("控制信息", pack)
        self.assertNotIn("连续性更新", pack)
        self.assertNotIn("归还旧伞", pack)

    def test_wrong_episode_title_cannot_be_reviewed_as_another_episode(self):
        confirm(self.root)
        path = self.root / "episodes/EP001.md"
        path.write_text(path.read_text().replace("# 第1集", "# 第2集"), encoding="utf-8")
        with self.assertRaisesRegex(ValueError, "does not match"):
            wf.review_pack(self.root, "batch", ["001"])

    def test_duplicate_scenes_cannot_hide_missing_scene_coverage(self):
        confirm(self.root)
        path = self.root / "episodes/EP001.md"
        with path.open("a") as handle:
            handle.write("\n## 1-1 夜 内 修伞铺\n林初：再次相同场号。\n")
        with self.assertRaisesRegex(ValueError, "duplicate scene"):
            wf.review_pack(self.root, "batch", ["001"])

    def test_fixed_issue_must_pass_new_review_before_approval(self):
        confirm(self.root)
        for target in ("planned", "draft", "in_review"):
            result = run("update_episode_state.py", self.root, "--episode", 1, "--to", target,
                         "--story-bible-revision", 1, "--matrix-revision", 1)
            self.assertEqual(result.returncode, 0, result.stderr)
        # Zero alone and an unreviewed script remain blocked.
        result = run("update_episode_state.py", self.root, "--episode", 1, "--to", "approved", "--blocking-issues", 0)
        self.assertNotEqual(result.returncode, 0)
        finish_review(self.root, "batch", ["001", "002"])
        fixture_polish(self.root)
        result = run("update_episode_state.py", self.root, "--episode", 1, "--to", "approved", "--blocking-issues", 0)
        self.assertEqual(result.returncode, 0, result.stderr)
        result = run("validate_state.py", self.root)
        self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        with (self.root / "episodes/EP001.md").open("a") as handle:
            handle.write("\n林初：稿件后来变了。\n")
        resumed = wf.synchronize(self.root)
        self.assertEqual(resumed["episodes"]["001"], "stale")
        events = [json.loads(line) for line in (self.root / ".drama/invalidation-log.jsonl").read_text().splitlines()]
        self.assertIn("EP001", events[-1]["episodes"])
        self.assertIn("episodes/EP001.md", events[-1]["changed"])

    def test_changed_outline_invalidates_confirmation_and_planning(self):
        confirm(self.root)
        self.assertFalse(wf.writing_errors(self.root))
        with (self.root / wf.OUTLINE).open("a") as handle:
            handle.write("\n结局改为出售旧伞。\n")
        self.assertTrue(wf.writing_errors(self.root))
        result = wf.synchronize(self.root)
        self.assertEqual(result["phase"], "outline_revision")
        self.assertIsNone(wf.load_workflow(self.root)["outlineConfirmation"])

    def test_locked_decision_change_invalidates_outline_even_when_outline_text_is_unchanged(self):
        confirm(self.root)
        (self.root / "locked-decisions.md").write_text("# L0锁定决定\n\n旧伞必须销毁，父女决裂。\n", encoding="utf-8")
        self.assertTrue(wf.writing_errors(self.root))
        state = wf.synchronize(self.root)
        self.assertEqual(state["phase"], "outline_revision")
        self.assertIsNone(wf.load_workflow(self.root)["outlineConfirmation"])

    def test_new_partial_rejection_cannot_be_hidden_by_an_old_full_review(self):
        confirm(self.root)
        finish_review(self.root, "final", ["001", "002"])
        self.assertFalse(wf.current_review(self.root, "final", ["001", "002"])[1])
        issue = {"issueId": "NEW-EP002", "severity": "P1", "category": "causality", "location": "2-1",
                 "evidence": [{"path": "episodes/EP002.md", "quote": "先把借的还上"}],
                 "reason": "later partial review found a previously missed problem", "returnTo": "scene", "impactScope": ["EP002"],
                 "regressionCheck": ["reread EP002"], "status": "open"}
        finish_review(self.root, "final", ["002"], [issue])
        self.assertTrue(wf.current_review(self.root, "final", ["002"])[1])
        self.assertTrue(wf.current_review(self.root, "final", ["001", "002"])[1])
        self.assertFalse(wf.current_review(self.root, "final", ["001"])[1])

    def test_hand_filled_zero_does_not_approve_blocking_review(self):
        confirm(self.root)
        for target in ("planned", "draft", "in_review"):
            result = run("update_episode_state.py", self.root, "--episode", 1, "--to", target,
                         "--story-bible-revision", 1, "--matrix-revision", 1)
            self.assertEqual(result.returncode, 0, result.stderr)
        issue = {"issueId": "TEST-CAUSALITY", "severity": "P1", "category": "causality", "location": "1-1",
                 "evidence": [{"path": "episodes/EP001.md", "quote": "先把借的还上"}],
                 "reason": "deliberately injected fixture", "returnTo": "outline", "impactScope": ["EP001"],
                 "regressionCheck": ["reread setup and consequence"], "status": "open"}
        finish_review(self.root, "batch", ["001"], [issue])
        result = run("update_episode_state.py", self.root, "--episode", 1, "--to", "approved", "--blocking-issues", 0)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("blocking issues", result.stderr)
        with self.assertRaisesRegex(ValueError, "unresolved issues cannot disappear"):
            finish_review(self.root, "batch", ["001"], [])

    def test_current_text_required_missing_coverage_and_changed_receipt_fail(self):
        confirm(self.root)
        session, _ = finish_review(self.root, "batch", ["001"])
        self.assertFalse(wf.validate_episode_review(self.root, "001"))
        self.assertTrue(wf.validate_episode_review(self.root, "002"))
        with (self.root / "episodes/EP001.md").open("a") as handle:
            handle.write("\n林初：订单不等了。\n")
        self.assertTrue(wf.validate_episode_review(self.root, "001"))
        saved = wf.session_path(self.root, session["sessionId"]).parent / "report.json"
        report = wf.read_json(saved)
        report["issues"] = []
        report["reviewer"] = "tampered"
        wf.save_json(saved, report)
        self.assertIn("report changed", ";".join(wf.validate_episode_review(self.root, "001")))

    def test_one_episode_issue_does_not_roll_back_an_unaffected_episode(self):
        confirm(self.root)
        for target in ("planned", "draft", "in_review"):
            result = run("update_episode_state.py", self.root, "--episode", 1, "--to", target,
                         "--story-bible-revision", 1, "--matrix-revision", 1)
            self.assertEqual(result.returncode, 0, result.stderr)
        issue = {"issueId": "TEST-ONLY-EP002", "severity": "P1", "category": "character", "location": "2-1",
                 "evidence": [{"path": "episodes/EP002.md", "quote": "先把借的还上"}],
                 "reason": "synthetic episode-two-only fixture", "returnTo": "scene", "impactScope": ["EP002"],
                 "regressionCheck": ["reread EP002"], "status": "open"}
        finish_review(self.root, "batch", ["001", "002"], [issue])
        fixture_polish(self.root, ["001"])
        self.assertFalse(wf.validate_episode_review(self.root, "001"))
        self.assertTrue(wf.validate_episode_review(self.root, "002"))
        result = run("update_episode_state.py", self.root, "--episode", 1, "--to", "approved")
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_release_requires_final_semantics_and_exact_delivery_range(self):
        confirm(self.root)
        finish_review(self.root, "batch", ["001", "002"])
        errors = wf.validate_release(self.root, ["001", "002"], self.root / "front-matter.md")
        self.assertTrue(any("final review" in e for e in errors))
        self.assertTrue(any("semantic" in e for e in errors))
        self.assertTrue(any("not approved" in e for e in errors))
        self.assertTrue(any("contiguous" in e for e in wf.validate_release(self.root, ["002", "001"], None)))

    def test_future_promise_valid_in_partial_delivery_but_not_season_end(self):
        result = run("workflow.py", self.root, "set-plan", "--total-episodes", 50,
                     "--reason", "software-fixture: exercise future promise and season-end boundaries")
        self.assertEqual(result.returncode, 0, result.stderr)
        path = self.root / "continuity/foreshadowing.csv"
        path.write_text("foreshadow_id,setup,setup_episode,payoff_by,status\nF-1,旧伞,1,35,planned\n", encoding="utf-8")
        report = {"promiseAudit": [{"id": "F-1", "status": "future", "owner": "编剧", "plannedRange": "35"}]}
        session = {"stage": "final", "episodes": ["001", "030"], "inputs": {}}
        self.assertFalse(wf.promise_errors(self.root, session, report))
        session["episodes"] = ["001", "050"]
        self.assertTrue(wf.promise_errors(self.root, session, report))

    def test_source_routes_record_scope_and_failures(self):
        with tempfile.TemporaryDirectory() as temp:
            adaptation = Path(temp) / "adaptation"
            seed(adaptation, "adaptation")
            self.assertTrue(wf.source_errors(adaptation))
            source = wf.read_json(adaptation / wf.SOURCE)
            source["records"] = [{"title": "节选", "contentType": "authorized_excerpt", "accessStatus": "unavailable", "coverage": "前一章", "limitations": "未提供原文"}]
            wf.save_json(adaptation / wf.SOURCE, source)
            self.assertFalse(wf.source_errors(adaptation))
            market = Path(temp) / "market"
            seed(market, "market-research")
            self.assertTrue(wf.source_errors(market))
            self.assertTrue((market / "02-market-research.md").exists())
            self.assertEqual(wf.read_json(market / ".drama/project-state.json")["sourceMode"], "market_research")

    def test_p0_cannot_be_waived_with_an_acceptance_quote(self):
        issue = {"issueId": "P0-FIXTURE", "severity": "P0", "category": "character", "status": "accepted_by_user",
                 "userAcceptance": {"quote": "synthetic acceptance", "messageRef": "fixture"}}
        self.assertEqual(wf.blocking_issues({"issues": [issue]}), [issue])


if __name__ == "__main__":
    unittest.main()
