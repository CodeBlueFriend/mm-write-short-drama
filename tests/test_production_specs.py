"""Observable production-intake gates using isolated software fixtures only.

Selections, readings and confirmations below are synthetic software inputs.
They do not represent a creator's choices or literary/visual approval.
"""
from __future__ import annotations

import importlib.util
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[1] / "mm-write-short-drama/scripts"
sys.path.insert(0, str(SCRIPTS))
import workflow_lib as wf
sys.path.insert(0, str(SCRIPTS.parent / "evals/fixtures"))
from workflow_fixture import confirm, finish_review, run, seed

TAG = "software-fixture"
QUOTE = "software-fixture: synthetic production choices; no real creator approval"
SELECTION_FIELDS = ("productionMode", "sourceMode", "duration", "episodeCountPreference")


class ProductionSpecsTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.base = Path(self.temp.name)
        self.root = self.new_project("project")

    def new_project(self, name, mode="original", review_mode="strict", *legacy):
        root = self.base / name
        result = run("init_project.py", root, "--mode", mode,
                     "--review-mode", review_mode, *legacy)
        self.assertEqual(result.returncode, 0, result.stderr)
        source = wf.read_json(root / wf.SOURCE)
        source["originalIdea"] = "software-fixture 林初修好旧伞并承担错过订单的损失。"
        if mode != "original":
            source["records"] = [{"title": TAG, "contentType": "authorized_excerpt",
                                  "accessStatus": "unavailable", "coverage": "software-fixture",
                                  "limitations": "software-fixture: no source text supplied"}]
        wf.save_json(root / wf.SOURCE, source)
        for name in (wf.TREATMENT, "04-story-bible.md", wf.OUTLINE):
            (root / name).write_text("# software-fixture\n\n林初修好旧伞并承担损失。\n", encoding="utf-8")
        return root

    def command(self, command, *args, root=None, succeeds=True):
        result = run("workflow.py", root or self.root, command, *args)
        if succeeds:
            self.assertEqual(result.returncode, 0, result.stderr + result.stdout)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result

    def select(self, *args, root=None, succeeds=True):
        return self.command("set-specs", *args, "--user-quote", QUOTE,
                            "--message-ref", TAG, root=root, succeeds=succeeds)

    def complete(self, root=None, mode="live_action", source_mode="original", duration="90", count="2"):
        duration_flag = "--duration-range" if "-" in duration else "--duration-seconds"
        return self.select("--production-mode", mode, "--source-mode", source_mode, duration_flag, duration,
                           "--episode-count", count, root=root)

    def plan(self, total, root=None, reason="software-fixture: deterministic plan for gate testing"):
        return self.command("set-plan", "--total-episodes", total, "--reason", reason, root=root)

    def pack(self, stage="treatment", *, root=None, succeeds=False):
        return self.command("review-pack", "--stage", stage, root=root, succeeds=succeeds)

    def specs(self, root=None):
        return wf.read_json((root or self.root) / ".drama/production-specs.json")

    def status(self, root=None):
        return json.loads(self.command("status", root=root).stdout)

    def test_legacy_init_options_do_not_supply_actual_user_selections(self):
        root = self.new_project("legacy", "original", "strict", "--production-mode",
                                "live_action", "--total-episodes", "60")
        for field in SELECTION_FIELDS:
            self.assertIsNone(self.specs(root)[field])
        self.pack(root=root)
        self.command("check-writing", root=root, succeeds=False)
        self.command("set-plan", "--total-episodes", "58", "--reason", TAG,
                     root=root, succeeds=False)

    def test_init_records_receipted_choices_and_still_awaits_actual_plan(self):
        root = self.new_project("receipted-init", "original", "strict",
                                "--production-mode", "ai_drama", "--source-mode", "original", "--duration-range", "50-60",
                                "--episode-count", "40-60", "--total-episodes", "60",
                                "--specs-user-quote", QUOTE, "--specs-message-ref", TAG)
        selected = self.specs(root)
        self.assertEqual(selected["productionMode"], "ai_drama")
        self.assertEqual(selected["sourceMode"], "original")
        self.assertNotIn("genre", selected)
        self.assertEqual((selected["duration"]["minSeconds"], selected["duration"]["maxSeconds"]), (50, 60))
        self.assertEqual(selected["episodeCountPreference"]["raw"], "40-60")
        for field in SELECTION_FIELDS:
            self.assertEqual(selected["selections"][field]["userQuote"], QUOTE)
            self.assertEqual(selected["selections"][field]["messageRef"], TAG)
        resumed = self.status(root)["productionSpecs"]
        self.assertEqual(resumed["status"], "ready")
        self.assertEqual(resumed["nextRequired"], "episodePlan")
        self.assertIsNone(resumed["plannedTotalEpisodes"])
        self.assertIsNone(wf.read_json(root / ".drama/project-state.json")["totalEpisodes"])
        self.pack(root=root, succeeds=True)

    def test_init_choices_without_selection_receipt_fail_before_creating_directory(self):
        for index, args in enumerate((("--source-mode", "original"), ("--duration-seconds", "90"),
                                      ("--duration-range", "50-60"))):
            with self.subTest(args=args):
                root = self.base / f"unreceipted-init-{index}"
                result = run("init_project.py", root, "--production-mode", "live_action", *args)
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(root.exists())

    def test_state_validator_rejects_conflicting_mirrors_or_unplanned_total(self):
        # Genuine pending input is a warning; contradictory mirrors are errors.
        pending = run("validate_state.py", self.root, "--json")
        self.assertEqual(pending.returncode, 0, pending.stderr + pending.stdout)
        pending_report = json.loads(pending.stdout)
        self.assertEqual(pending_report["errors"], [])
        self.assertTrue(pending_report["warnings"])
        self.complete()
        state_path = self.root / ".drama/project-state.json"
        baseline = wf.read_json(state_path)
        valid = run("validate_state.py", self.root, "--json")
        self.assertEqual(valid.returncode, 0, valid.stderr + valid.stdout)
        self.assertTrue(json.loads(valid.stdout)["warnings"])
        for field, value in (("productionMode", "ai_drama"), ("sourceMode", "adaptation"), ("totalEpisodes", 58)):
            with self.subTest(field=field):
                wf.save_json(state_path, {**baseline, field: value})
                result = run("validate_state.py", self.root, "--json")
                self.assertNotEqual(result.returncode, 0)
                report = json.loads(result.stdout)
                self.assertFalse(report["valid"])
                self.assertTrue(report["errors"])
        wf.save_json(state_path, baseline)
        self.assertEqual(run("validate_state.py", self.root, "--json").returncode, 0)
        source_path = self.root / wf.SOURCE
        source = wf.read_json(source_path)
        wf.save_json(source_path, {**source, "sourceMode": "adaptation"})
        result = run("validate_state.py", self.root, "--json")
        self.assertNotEqual(result.returncode, 0)
        self.assertTrue(json.loads(result.stdout)["errors"])

    def test_stepwise_selection_is_required_before_treatment_and_plan_before_outline(self):
        self.assertEqual(self.status()["productionSpecs"]["nextRequired"], "productionMode")
        self.pack()
        self.select("--production-mode", "live_action")
        # Each status command starts a new process and must restore the pending choice.
        self.assertEqual(self.status()["productionSpecs"]["nextRequired"], "sourceMode")
        self.pack()
        self.select("--source-mode", "original")
        self.assertEqual(self.status()["productionSpecs"]["nextRequired"], "duration")
        self.pack()
        self.select("--duration-seconds", "90")
        self.assertEqual(self.status()["productionSpecs"]["nextRequired"], "episodeCount")
        self.pack()
        self.select("--episode-count", "60")
        ready = self.status()["productionSpecs"]
        self.assertEqual(ready["status"], "ready")
        self.assertEqual(ready["nextRequired"], "episodePlan")
        self.pack(succeeds=True)
        finish_review(self.root, "treatment")
        self.pack("outline")
        self.plan(58)
        self.assertIsNone(self.status()["productionSpecs"]["nextRequired"])
        self.pack("outline", succeeds=True)

    def test_selections_cannot_be_supplied_out_of_order(self):
        self.select("--source-mode", "original", succeeds=False)
        self.select("--duration-seconds", "90", succeeds=False)
        self.select("--episode-count", "60", succeeds=False)
        self.select("--production-mode", "live_action")
        self.select("--duration-seconds", "90", succeeds=False)
        self.select("--episode-count", "60", succeeds=False)
        self.assertEqual(self.status()["productionSpecs"]["nextRequired"], "sourceMode")
        self.select("--source-mode", "original")
        self.select("--episode-count", "60", succeeds=False)
        self.assertEqual(self.status()["productionSpecs"]["nextRequired"], "duration")
        self.pack()

    def test_invalid_source_is_rejected_and_does_not_advance_the_gate(self):
        self.select("--production-mode", "live_action")
        for source_mode in ("", "   ", "\t\n", "not-a-source-mode"):
            with self.subTest(source_mode=source_mode):
                self.select("--source-mode", source_mode, succeeds=False)
                self.assertIsNone(self.specs()["sourceMode"])
                self.assertEqual(self.status()["productionSpecs"]["nextRequired"], "sourceMode")
                self.pack()

    def test_legacy_missing_source_can_be_completed_without_reselecting_receipted_choices(self):
        for variant in ("missing", "null", "unreceipted", "missing-quote"):
            with self.subTest(variant=variant):
                root = self.new_project("legacy-source-" + variant)
                self.complete(root=root)
                legacy = self.specs(root)
                if variant == "missing-quote":
                    legacy["selections"]["sourceMode"]["userQuote"] = ""
                else:
                    legacy["selections"].pop("sourceMode")
                if variant == "missing":
                    legacy.pop("sourceMode")
                elif variant == "null":
                    legacy["sourceMode"] = None
                wf.save_json(root / ".drama/production-specs.json", legacy)
                pending = self.status(root)["productionSpecs"]
                self.assertEqual(pending["status"], "pending")
                self.assertEqual(pending["nextRequired"], "sourceMode")
                self.pack(root=root)
                self.select("--source-mode", "original", root=root)
                saved = self.specs(root)
                self.assertEqual(saved["sourceMode"], "original")
                self.assertEqual(saved["selections"]["sourceMode"]["userQuote"], QUOTE)
                self.assertEqual(saved["selections"]["sourceMode"]["messageRef"], TAG)
                for field in ("productionMode", "duration", "episodeCountPreference"):
                    self.assertEqual(saved[field], legacy[field])
                    self.assertEqual(saved["selections"][field], legacy["selections"][field])
                resumed = self.status(root)["productionSpecs"]
                self.assertEqual(resumed["status"], "ready")
                self.assertEqual(resumed["nextRequired"], "episodePlan")
                self.pack(root=root, succeeds=True)

    def test_quote_and_reference_are_required_and_failed_command_leaves_gate_closed(self):
        for evidence in ([], ["--message-ref", TAG], ["--user-quote", QUOTE],
                         ["--user-quote", "", "--message-ref", TAG],
                         ["--user-quote", QUOTE, "--message-ref", ""]):
            self.command("set-specs", "--production-mode", "live_action",
                         "--source-mode", "original", "--duration-seconds", "90", "--episode-count", "60",
                         *evidence, succeeds=False)
            self.pack()
        self.select("--production-mode", "live_action", "--source-mode", "original", "--duration-seconds", "90",
                    "--episode-count", "60")
        self.pack(succeeds=True)

    def test_persisted_selections_without_quote_never_become_ready(self):
        self.complete()
        original = self.specs()
        for field in SELECTION_FIELDS:
            with self.subTest(field=field):
                altered = json.loads(json.dumps(original))
                altered["selections"][field]["userQuote"] = ""
                wf.save_json(self.root / ".drama/production-specs.json", altered)
                self.assertEqual(self.status()["productionSpecs"]["status"], "pending")
                self.pack()
        wf.save_json(self.root / ".drama/production-specs.json", original)
        self.pack(succeeds=True)

    def test_live_action_duration_hard_limit_is_180_seconds(self):
        self.select("--production-mode", "live_action", "--source-mode", "original", "--duration-seconds", "181",
                    "--episode-count", "60", succeeds=False)
        self.pack()
        self.complete(duration="180", count="60")
        self.pack(succeeds=True)

    def test_ai_regular_optional_and_unconventional_durations_are_selectable(self):
        for duration in ("50-60", "90", "120", "121"):
            with self.subTest(duration=duration):
                root = self.new_project("ai-" + duration)
                self.complete(root=root, mode="ai_drama", duration=duration)
                self.pack(root=root, succeeds=True)
                saved = self.specs(root)["duration"]
                if duration == "121":
                    self.assertEqual(saved["classification"], "unconventional")
                    self.assertTrue(self.status(root)["productionSpecs"]["advisories"])
                if duration == "50-60":
                    self.assertEqual((saved["minSeconds"], saved["maxSeconds"]), (50, 60))
                    self.assertEqual(saved["classification"], "standard")
                if duration == "120":
                    self.assertNotEqual(saved["classification"], "unconventional")

    def test_invalid_duration_values_are_rejected(self):
        for flag, value in (("--duration-seconds", "0"), ("--duration-seconds", "-1"),
                            ("--duration-range", "60-50"), ("--duration-range", "0-60")):
            with self.subTest(value=value):
                self.select("--production-mode", "ai_drama", "--source-mode", "original", flag, value,
                            "--episode-count", "60", succeeds=False)
                self.pack()

    def test_specific_range_and_approximate_episode_preferences_are_accepted(self):
        for preference, kind in (("60", "target"), ("40-60", "range"), ("约60集", "target")):
            with self.subTest(preference=preference):
                root = self.new_project("preference-" + preference)
                self.complete(root=root, count=preference)
                selected = self.specs(root)
                request = selected["episodeCountPreference"]
                self.assertEqual(request["raw"], preference)
                self.assertEqual(request["kind"], kind)
                self.assertTrue(request["flexible"])
                if kind == "range":
                    self.assertEqual((request["min"], request["max"]), (40, 60))
                else:
                    self.assertEqual(request["target"], 60)
                self.plan(58, root=root)
                self.assertEqual(self.specs(root), selected)
                self.pack(root=root, succeeds=True)
                self.assertEqual(wf.read_json(root / ".drama/project-state.json")["totalEpisodes"], 58)
                plan = wf.read_json(root / ".drama/episode-plan.json")
                self.assertEqual(plan["plannedTotalEpisodes"], 58)
                self.assertTrue(plan["planReason"])

    def test_invalid_episode_preferences_are_rejected(self):
        for preference in ("0", "-1", "60-40", "0-60"):
            with self.subTest(preference=preference):
                self.select("--production-mode", "live_action", "--source-mode", "original", "--duration-seconds", "90",
                            "--episode-count", preference, succeeds=False)
                self.pack()

    def test_actual_plan_requires_specs_and_a_recorded_reason(self):
        self.command("set-plan", "--total-episodes", "58", "--reason", TAG, succeeds=False)
        self.complete(count="60")
        self.assertIsNone(wf.read_json(self.root / ".drama/episode-plan.json")["plannedTotalEpisodes"])
        self.command("set-plan", "--total-episodes", "58", succeeds=False)
        self.command("set-plan", "--total-episodes", "58", "--reason", "", succeeds=False)
        for invalid in ("0", "-1"):
            self.command("set-plan", "--total-episodes", invalid, "--reason", TAG, succeeds=False)
        self.plan(58)
        self.assertEqual(wf.read_json(self.root / ".drama/project-state.json")["totalEpisodes"], 58)

    def test_mode_change_discards_previous_duration_and_requires_reselection(self):
        self.complete()
        self.plan(2)
        prior = self.specs()
        canon = self.root / "continuity/canon.yaml"
        self.assertIn('  productionMode: "live_action"\n', canon.read_text(encoding="utf-8"))
        preserved = "immutable_facts:\n  - productionMode: software-fixture-immutable\n"
        canon.write_text(canon.read_text(encoding="utf-8").replace("immutable_facts: []\n", preserved), encoding="utf-8")
        self.select("--production-mode", "ai_drama")
        updated_canon = canon.read_text(encoding="utf-8")
        self.assertIn('  productionMode: "ai_drama"\n', updated_canon)
        self.assertNotIn('  productionMode: "live_action"\n', updated_canon)
        self.assertIn(preserved, updated_canon)
        self.assertEqual(wf.read_json(self.root / ".drama/project-state.json")["productionMode"], "ai_drama")
        self.assertEqual(self.specs()["sourceMode"], prior["sourceMode"])
        self.assertEqual(self.specs()["selections"]["sourceMode"], prior["selections"]["sourceMode"])
        self.assertIsNone(self.specs()["duration"])
        self.assertEqual(self.status()["productionSpecs"]["nextRequired"], "duration")
        self.pack()
        self.select("--duration-range", "50-60")
        self.pack(succeeds=True)

    def test_actual_plan_can_deviate_from_user_range_with_reason(self):
        self.complete(count="40-60")
        before = self.specs()
        reason = "software-fixture: actual outline needs 38 numbered items after combining two checks"
        self.plan(38, reason=reason)
        self.assertEqual(self.specs(), before)
        saved = wf.read_json(self.root / ".drama/episode-plan.json")
        self.assertEqual(saved["plannedTotalEpisodes"], 38)
        self.assertEqual(saved["planReason"], reason)

    def test_source_change_updates_mirrors_and_adds_route_skeleton_without_overwriting(self):
        routes = {"market_research": ["02-market-research.md"],
                  "adaptation": ["01-source-index.md", "02-source-truth.md", "03-adaptation-map.md"]}
        for source_mode, files in routes.items():
            with self.subTest(source_mode=source_mode):
                root = self.new_project("switch-to-" + source_mode)
                self.complete(root=root)
                self.plan(2, root=root)
                before = self.specs(root)
                original_path = root / "03-original-discovery.md"
                original_text = original_path.read_text(encoding="utf-8")
                preserved = "# software-fixture\n\nPreserve this existing route document exactly.\n"
                (root / files[0]).write_text(preserved, encoding="utf-8")
                previous = wf.read_json(root / wf.SOURCE)
                previous["creatorLocks"] = ["software-fixture: preserve creator constraints across source routes"]
                wf.save_json(root / wf.SOURCE, previous)
                source_before = (root / wf.SOURCE).read_bytes()
                self.select("--source-mode", source_mode, root=root)
                selected = self.specs(root)
                self.assertEqual(selected["sourceMode"], source_mode)
                self.assertEqual(selected["selections"]["sourceMode"]["userQuote"], QUOTE)
                self.assertEqual(wf.read_json(root / ".drama/project-state.json")["sourceMode"], source_mode)
                source_after = wf.read_json(root / wf.SOURCE)
                self.assertEqual(source_after["sourceMode"], source_mode)
                self.assertEqual(source_after["originalIdea"], "")
                self.assertEqual(source_after["creatorLocks"], previous["creatorLocks"])
                self.assertEqual(source_after["records"], [])
                history = list((root / ".drama/source-route-history").glob("*.json"))
                self.assertTrue(any(path.read_bytes() == source_before for path in history))
                for filename in files:
                    self.assertTrue((root / filename).is_file(), filename)
                self.assertEqual((root / files[0]).read_text(encoding="utf-8"), preserved)
                self.assertEqual(original_path.read_text(encoding="utf-8"), original_text)
                for field in ("duration", "episodeCountPreference"):
                    self.assertEqual(selected[field], before[field])
                self.assertIsNone(wf.read_json(root / ".drama/episode-plan.json")["plannedTotalEpisodes"])

    def test_all_source_and_review_modes_still_require_selections(self):
        for source_mode in ("original", "adaptation", "market-research", "source-remix"):
            for review_mode in ("strict", "assisted", "automatic"):
                with self.subTest(source_mode=source_mode, review_mode=review_mode):
                    root = self.new_project(f"{source_mode}-{review_mode}", source_mode, review_mode)
                    self.assertEqual(self.status(root)["productionSpecs"]["nextRequired"], "productionMode")
                    result = self.pack(root=root)
                    self.assertFalse((root / ".drama/readings").exists(), result.stdout)
                    self.select("--production-mode", "live_action", root=root)
                    self.assertEqual(self.status(root)["productionSpecs"]["nextRequired"], "sourceMode")
                    self.pack(root=root)
                    self.command("check-writing", root=root, succeeds=False)

    def test_production_choice_or_actual_plan_change_invalidates_old_confirmation(self):
        changes = (("type", ("--production-mode", "ai_drama")),
                   ("source", ("--source-mode", "market_research")),
                   ("duration", ("--duration-seconds", "100")),
                   ("preference", ("--episode-count", "3")))
        for name, args in changes:
            with self.subTest(change=name):
                root = self.base / ("confirmed-" + name)
                seed(root)
                confirm(root)
                self.assertFalse(wf.writing_errors(root))
                self.select(*args, root=root)
                self.status(root)
                self.assertTrue(wf.writing_errors(root))
                self.assertIsNone(wf.load_workflow(root)["outlineConfirmation"])
        root = self.base / "confirmed-plan"
        seed(root)
        confirm(root)
        self.plan(3, root=root)
        self.status(root)
        self.assertTrue(wf.writing_errors(root))
        self.assertIsNone(wf.load_workflow(root)["outlineConfirmation"])

    @unittest.skipUnless(importlib.util.find_spec("docx"), "Word export checks require python-docx")
    def test_word_integrity_uses_actual_58_episode_plan(self):
        import export_screenplay_docx as exporter
        from docx import Document

        self.complete(count="60")
        self.plan(58)
        total = exporter.project_total(self.root)
        self.assertEqual(total, 58)
        body = {
            "剧本名": "软件夹具", "来源": "software-fixture 合成测试，不代表创作批准。",
            "类型": "software-fixture", "集数": "全剧共58集，本稿为第1—58集正式剧本。",
            "剧名寓意": "software-fixture 编号检查。", "热门元素": "software-fixture 无热度主张。",
            "创作理由": "software-fixture 确认实际交付范围。", "故事梗概": "software-fixture 编号从一到五十八。",
            "主要角色": "林初，software-fixture 检查编号。",
        }
        front = self.root / "front-matter.md"
        front.write_text("\n\n".join(f"## {key}\n{value}" for key, value in body.items()) + "\n", encoding="utf-8")
        self.assertEqual(exporter.validate_front_matter(front, "软件夹具", list(range(1, 59)), total), [])
        episodes = []
        for number in range(1, 59):
            path = self.root / f"episodes/EP{number:03d}.md"
            path.write_text(f"# 第{number}集\n\n## {number}-1 日 内 软件夹具室\n人物：林初\n"
                            f"▲林初检查第{number}号夹具。\n林初：software-fixture 已收到。\n", encoding="utf-8")
            episodes.append(exporter.parse_episode(path))
        output = self.root / "deliverables/software-fixture-preview.docx"
        exporter.build_docx(episodes, output, "软件夹具", False, front_matter=front, preview=True)
        visible = [paragraph.text for paragraph in Document(output).paragraphs]
        labels = [int(match[1]) for text in visible if (match := re.fullmatch(r"第\s*(\d+)\s*集", text))]
        self.assertEqual(labels, list(range(1, 59)))
        self.assertIn("集数：全剧共58集，本稿为第1—58集正式剧本。", visible)
        self.assertEqual(Document(output).core_properties.category, "PREVIEW")
        self.assertTrue(exporter.validate_front_matter(front, "软件夹具", list(range(1, 61)), total))
        body["集数"] = "全剧共60集，本稿为第1—58集正式剧本。"
        front.write_text("\n\n".join(f"## {key}\n{value}" for key, value in body.items()) + "\n", encoding="utf-8")
        self.assertTrue(exporter.validate_front_matter(front, "软件夹具", list(range(1, 59)), total))


if __name__ == "__main__":
    unittest.main()
