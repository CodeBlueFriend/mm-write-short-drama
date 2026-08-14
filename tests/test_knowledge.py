from __future__ import annotations

import json
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "mm-write-short-drama" / "scripts"


def run_script(name: str, *args: object, check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *(str(arg) for arg in args)],
        check=check,
        text=True,
        capture_output=True,
    )


class KnowledgeBaseTests(unittest.TestCase):
    def make_kb(self, root: Path) -> Path:
        kb = root / "knowledge-base"
        run_script("validate_knowledge.py", "--kb", kb, "--fix-index")
        return kb

    def test_direct_text_ingest_search_and_validate(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kb = self.make_kb(Path(temp))
            text = (
                "技巧名称: 首次有效反击\n"
                "规则: 主角第一次有效反击必须改变资源、关系或信息状态，不能只获得口头胜利。\n"
                "理由: 状态变化才能影响后续因果。\n"
                "分类: 分集与卡点\n"
                "阶段: episode\n"
                "题材: 女频复仇\n"
                "制作形式: all\n"
                "优先级: preferred\n"
                "例外: 经确认的前期压抑型结构\n"
                "正例: 女主公开账本后夺回表决权。\n"
                "反例: 女主只把反派骂走。"
            )
            ingested = run_script(
                "ingest_knowledge.py",
                "--kb", kb,
                "--text", text,
                "--source-name", "conversation-tip.md",
                "--status", "active",
            )
            result = json.loads(ingested.stdout)
            self.assertEqual(len(result["created"]), 1)
            self.assertEqual(len(list((kb / "sources").glob("SRC-*"))), 1)
            searched = run_script(
                "search_knowledge.py", "有效反击", "--kb", kb,
                "--stage", "episode", "--genre", "女频复仇", "--format", "context",
            )
            self.assertIn(result["created"][0], searched.stdout)
            self.assertIn("使用的知识规则 ID", searched.stdout)
            validated = run_script("validate_knowledge.py", "--kb", kb)
            self.assertIn("Result: PASS", validated.stdout)

    def test_direct_text_can_preserve_full_source_and_override_atomic_rule(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kb = self.make_kb(Path(temp))
            original = "已确认技巧：主角首次反击必须改变资源状态。只用于女频复仇分集，例外是慢热结构。"
            atomic = "主角首次反击必须改变资源状态。"
            payload = json.loads(
                run_script(
                    "ingest_knowledge.py", "--kb", kb,
                    "--text", original, "--rule", atomic,
                    "--stage", "episode", "--genre", "女频复仇",
                ).stdout
            )
            card = next((kb / "cards").glob(f"{payload['created'][0]}.md")).read_text(encoding="utf-8")
            self.assertIn(atomic, card)
            self.assertNotIn("只用于女频复仇分集", card)
            source = next((kb / "sources").glob("SRC-*"))
            self.assertEqual(source.read_text(encoding="utf-8"), original)

    def test_batch_inbox_preserves_originals(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kb = self.make_kb(Path(temp))
            first = kb / "inbox" / "lesson-01.md"
            second = kb / "inbox" / "lesson-02.txt"
            first.write_text("- 场景必须通过人物行动改变权力关系。\n- 对白不要重复双方都知道的信息。\n", encoding="utf-8")
            second.write_text("反转必须改变人物下一步策略，不能只有惊讶。", encoding="utf-8")
            before = {first: first.read_bytes(), second: second.read_bytes()}
            result = run_script("ingest_knowledge.py", "--kb", kb, "--all-inbox")
            payload = json.loads(result.stdout)
            self.assertEqual(payload["materials_processed"], 2)
            self.assertEqual(payload["unique_source_contents"], 2)
            self.assertEqual(len(payload["created"]), 3)
            self.assertEqual(first.read_bytes(), before[first])
            self.assertEqual(second.read_bytes(), before[second])
            self.assertGreaterEqual(len(list((kb / "sources").glob("SRC-*"))), 2)

    def test_duplicate_is_logged_without_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kb = self.make_kb(Path(temp))
            rule = "人物第一次做出重大选择时，必须付出可见代价。"
            first = json.loads(run_script("ingest_knowledge.py", "--kb", kb, "--text", rule).stdout)
            card_path = kb / "cards" / f"{first['created'][0]}.md"
            original = card_path.read_bytes()
            second = json.loads(run_script("ingest_knowledge.py", "--kb", kb, "--text", rule).stdout)
            self.assertEqual(second["created"], [])
            self.assertEqual(second["duplicates"], 1)
            self.assertEqual(card_path.read_bytes(), original)
            duplicate_lines = (kb / "conflicts" / "duplicates.jsonl").read_text(encoding="utf-8").splitlines()
            self.assertEqual(len(duplicate_lines), 1)

    def test_conflict_waits_for_resolution_and_can_be_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kb = self.make_kb(Path(temp))
            positive = json.loads(
                run_script(
                    "ingest_knowledge.py", "--kb", kb,
                    "--text", "短剧开场必须立即展示主角的核心困境。",
                    "--category", "短剧开场", "--stage", "episode", "--status", "active",
                ).stdout
            )
            negative = json.loads(
                run_script(
                    "ingest_knowledge.py", "--kb", kb,
                    "--text", "短剧开场不得立即展示主角的核心困境。",
                    "--category", "短剧开场", "--stage", "episode", "--status", "active",
                ).stdout
            )
            self.assertEqual(negative["conflicts"], 1)
            new_id = negative["created"][0]
            default_results = run_script("search_knowledge.py", "核心困境", "--kb", kb, "--format", "ids").stdout
            self.assertIn(positive["created"][0], default_results)
            self.assertNotIn(new_id, default_results)
            conflict = json.loads((kb / "conflicts" / "open.jsonl").read_text(encoding="utf-8").splitlines()[0])
            run_script(
                "ingest_knowledge.py", "--kb", kb,
                "--resolve", conflict["conflict_id"], "--decision", "keep-both",
                "--note", "正向规则用于强情节类型，反向规则仅用于经确认的慢热悬疑。",
            )
            all_active = run_script("search_knowledge.py", "核心困境", "--kb", kb, "--format", "ids").stdout
            self.assertIn(new_id, all_active)
            self.assertTrue(any((kb / "archive").glob(f"{new_id}-v1-*.md")))
            self.assertEqual(run_script("validate_knowledge.py", "--kb", kb).returncode, 0)

    def test_scope_filtering_supports_actual_stage_call(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            kb = self.make_kb(Path(temp))
            dialogue = json.loads(
                run_script(
                    "ingest_knowledge.py", "--kb", kb,
                    "--text", "对白必须体现人物此刻的行动目的。",
                    "--category", "对白与潜台词", "--stage", "dialogue",
                    "--genre", "all", "--status", "active",
                ).stdout
            )["created"][0]
            run_script(
                "ingest_knowledge.py", "--kb", kb,
                "--text", "整季结构必须提前规划信息揭示顺序。",
                "--category", "反转悬念伏笔", "--stage", "structure", "--status", "active",
            )
            context = run_script(
                "search_knowledge.py", "人物行动", "--kb", kb,
                "--stage", "dialogue", "--production-mode", "live-action", "--format", "context",
            ).stdout
            self.assertIn(dialogue, context)
            self.assertNotIn("整季结构必须", context)


if __name__ == "__main__":
    unittest.main()
