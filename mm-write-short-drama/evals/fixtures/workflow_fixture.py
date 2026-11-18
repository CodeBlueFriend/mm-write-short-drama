"""Synthetic receipt fixtures for software regression; no literary evaluation claimed."""
from pathlib import Path
import subprocess
import sys
SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
sys.path.insert(0, str(SCRIPTS))
import workflow_lib as wf

def run(name, *args):
    return subprocess.run([sys.executable, str(SCRIPTS / name), *map(str, args)], capture_output=True, text=True)


def seed(root, mode="original", review_mode="strict"):
    result = run("init_project.py", root, "--mode", mode, "--review-mode", review_mode, "--total-episodes", 2)
    assert result.returncode == 0, result.stderr
    choose_specs(root, 2, source_mode=mode.replace("-", "_"))
    source = wf.read_json(root / wf.SOURCE)
    source["originalIdea"] = "修伞人要退还借走的旧伞，修复遗物的代价是错过有酬订单。"
    wf.save_json(root / wf.SOURCE, source)
    for name in (wf.TREATMENT, "04-story-bible.md", wf.OUTLINE):
        (root / name).write_text("# 合成测试夹具\n\n林初为还旧伞放弃订单，先找伞主说明破损，最终与父亲一起修好。\n", encoding="utf-8")
    for number in ("001", "002"):
        (root / f"episodes/EP{number}.md").write_text(f"# 第{int(number)}集\n\n## 本集控制信息\n测试\n\n## {int(number)}-1 日 内 修伞铺\n人物：林初、父亲\n△林初将订单移开，摆上旧伞。\n林初：先把借的还上。\n\n## 本集连续性更新\n归还旧伞。\n", encoding="utf-8")
    (root / "front-matter.md").write_text("# 合成验收夹具\n\n已写内容和范围，供程序测试，不代表用户确认。\n", encoding="utf-8")


def choose_specs(root, total=2, *, episode_count=None, source_mode="original"):
    """Declare software inputs without representing them as creator approval."""
    result = run("workflow.py", root, "set-specs", "--production-mode", "live_action",
                 "--source-mode", source_mode, "--duration-seconds", 90,
                 "--episode-count", episode_count or str(total),
                 "--user-quote", "software-fixture: synthetic selection for software regression; not real user approval",
                 "--message-ref", "software-fixture")
    assert result.returncode == 0, result.stderr
    result = run("workflow.py", root, "set-plan", "--total-episodes", total,
                 "--reason", "software-fixture: deterministic episode count for software regression")
    assert result.returncode == 0, result.stderr


def finish_review(root, stage, ids=None, issues=None):
    """Submit synthetic evidence solely to exercise deterministic gate behavior."""
    session = wf.review_pack(root, stage, ids or [], "front-matter.md" if stage == "final" else None)
    evidence = [{"path": session["coverage"][0]["path"], "quote": "林初"}]
    first = {"reviewer": "software-test-fixture", "knowledgeOfExpectations": "informed",
             "readChunks": [c["id"] for c in session["chunks"]],
             "causalRetelling": "Fixture data; this does not claim a model read the story.",
             "observations": [{"chunkId": c["id"], "protagonistIntent": "还伞", "concern": "订单",
                               "forcedChange": "旧伞破损", "understanding": "测试夹具",
                               "evidence": [{"path": c["source"], "quote": "林初"}]} for c in session["chunks"]]}
    first_path = root / "fixture-first.json"
    wf.save_json(first_path, first)
    wf.submit_first_read(root, session["sessionId"], first_path)
    wf.reveal_context(root, session["sessionId"])
    report = {"sessionId": session["sessionId"], "stage": stage, "reviewer": "software-test-fixture",
              "complete": True, "coverage": session["coverage"],
              "checks": [{"domain": d, "result": "pass", "reason": "synthetic software fixture", "evidence": evidence, "issueIds": []} for d in sorted(wf.DOMAINS[stage])],
              "issues": issues or [], "methods": [{"status": "skipped", "reason": "Software fixture tests receipts, not creative quality."}], "promiseAudit": []}
    report_path = root / "fixture-review.json"
    wf.save_json(report_path, report)
    wf.record_review(root, session["sessionId"], report_path)
    return session, report


def confirm(root):
    finish_review(root, "treatment")
    finish_review(root, "outline")
    wf.confirm_outline(root, "confirm", "软件夹具模拟同意，并非真实用户确认", "test-fixture", "合成2集")


def fixture_polish(root, ids=("001", "002")):
    from polish_guard import record_review
    for number in ids:
        script = root / f"episodes/EP{number}.md"
        review = {"reviewer": "software-test-fixture", "evidence": "Synthetic gate fixture, not a literary evaluation.",
                  "semanticVerified": True, "beforeHash": wf.digest(script), "afterHash": wf.digest(script),
                  "checked": ["characters", "subject_object", "negation", "conditions", "time", "amounts", "promises", "voice", "continuity"],
                  "mode": "off", "changes": [], "callChain": []}
        path = root / f"fixture-polish-{number}.json"
        wf.save_json(path, review)
        record_review(script, script, path, root / f".drama/polish/EP{number}.json")
