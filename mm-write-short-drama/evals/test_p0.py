#!/usr/bin/env python3
"""Regression smoke test for P0 project state and dependency behavior."""

from __future__ import annotations

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPTS = ROOT / "scripts"


def run(*args: str, expect: int = 0) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([sys.executable, *args], text=True, capture_output=True)
    if result.returncode != expect:
        raise AssertionError(
            f"command returned {result.returncode}, expected {expect}: {' '.join(args)}\n"
            f"stdout:\n{result.stdout}\nstderr:\n{result.stderr}"
        )
    return result


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="mm-drama-p0-") as temp:
        project = Path(temp) / "original-project"
        run(str(SCRIPTS / "init_project.py"), str(project), "--mode", "original", "--production-mode", "ai_drama", "--orientation", "vertical", "--total-episodes", "6")
        for relative in (
            ".drama/project-state.json", ".drama/artifact-index.json",
            "continuity/relationships.csv", "continuity/evidence.csv",
            "continuity/foreshadowing.csv",
        ):
            assert (project / relative).exists(), relative
        run(str(SCRIPTS / "validate_state.py"), str(project))
        run(str(SCRIPTS / "validate_project.py"), str(project), "--stage", "full")

        transitions = [
            ("planned", ["--story-bible-revision", "1", "--matrix-revision", "1"]),
            ("draft", []),
            ("in_review", ["--blocking-issues", "1"]),
        ]
        for target, extra in transitions:
            run(str(SCRIPTS / "update_episode_state.py"), str(project), "--episode", "1", "--to", target, *extra)
        run(str(SCRIPTS / "update_episode_state.py"), str(project), "--episode", "1", "--to", "approved", expect=2)
        run(str(SCRIPTS / "update_episode_state.py"), str(project), "--episode", "1", "--to", "revision")
        run(str(SCRIPTS / "update_episode_state.py"), str(project), "--episode", "1", "--to", "in_review", "--blocking-issues", "0")
        run(str(SCRIPTS / "update_episode_state.py"), str(project), "--episode", "1", "--to", "approved")
        run(str(SCRIPTS / "validate_state.py"), str(project))

        report = run(str(SCRIPTS / "impact_analysis.py"), str(project), "--changed", "04-story-bible.md", "--json")
        impact = json.loads(report.stdout)
        assert "05-season-architecture.md" in impact["direct"]
        before = json.loads((project / ".drama/artifact-index.json").read_text(encoding="utf-8"))
        assert before["artifacts"]["seasonArchitecture"]["status"] == "draft"
        run(str(SCRIPTS / "impact_analysis.py"), str(project), "--changed", "04-story-bible.md", "--apply", "--approved-by", "eval", "--reason", "regression test")
        after = json.loads((project / ".drama/artifact-index.json").read_text(encoding="utf-8"))
        assert after["artifacts"]["seasonArchitecture"]["status"] == "stale"
        after_state = json.loads((project / ".drama/project-state.json").read_text(encoding="utf-8"))
        assert after_state["episodes"]["001"]["status"] == "stale"
        assert (project / ".drama/invalidation-log.jsonl").read_text(encoding="utf-8").strip()
        run(str(SCRIPTS / "validate_state.py"), str(project))

        adaptation = Path(temp) / "adaptation-project"
        run(str(SCRIPTS / "init_project.py"), str(adaptation), "--mode", "adaptation", "--through", "story-bible")
        state = json.loads((adaptation / ".drama/project-state.json").read_text(encoding="utf-8"))
        assert state["sourceMode"] == "adaptation"
        assert (adaptation / "01-source-index.md").exists()
        run(str(SCRIPTS / "validate_project.py"), str(adaptation), "--stage", "gate-a")

    print("P0 regression test: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
