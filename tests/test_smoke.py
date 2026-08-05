from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SKILL = ROOT / "mm-write-short-drama"
SCRIPTS = SKILL / "scripts"


def run_script(name: str, *args: object) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(SCRIPTS / name), *(str(arg) for arg in args)],
        check=True,
        text=True,
        capture_output=True,
    )


class SkillSmokeTests(unittest.TestCase):
    def test_skill_metadata_and_links(self) -> None:
        skill_md = (SKILL / "SKILL.md").read_text(encoding="utf-8")
        self.assertTrue(skill_md.startswith("---\nname: mm-write-short-drama\ndescription:"))
        self.assertIn("$mm-write-short-drama", (SKILL / "agents/openai.yaml").read_text(encoding="utf-8"))
        for resource in (
            "workflow.md",
            "original-creation.md",
            "adaptation.md",
            "story-structure.md",
            "scene-and-dialogue.md",
            "continuity.md",
            "anti-ai-style.md",
            "production-modes.md",
            "review-rubrics.md",
            "techniques-catalog.md",
            "techniques-inbox.md",
        ):
            self.assertTrue((SKILL / "references" / resource).is_file(), resource)

    def test_original_project_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "original"
            run_script("init_project.py", project, "--mode", "original")
            (project / "episodes" / "EP001.md").write_text(
                (SKILL / "assets" / "screenplay-template.md").read_text(encoding="utf-8"),
                encoding="utf-8",
            )
            validated = run_script("validate_project.py", project, "--mode", "original")
            self.assertIn("Result: PASS", validated.stdout)
            stats = run_script("screenplay_stats.py", project / "episodes")
            self.assertIn("EP001", stats.stdout)
            run_script("build_context_pack.py", project, "--episodes", "1-3")
            self.assertTrue((project / "context-packs" / "EP001-EP003-context.md").is_file())

    def test_adaptation_index_and_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            source = root / "source.md"
            source.write_text("# 第一章\n许秋接手照相馆。\n\n# 第二章\n她发现十张空椅子照片。\n", encoding="utf-8")
            project = root / "adaptation"
            run_script("init_project.py", project, "--mode", "adaptation")
            run_script("index_source.py", source, "-o", project / "01-source-index.md")
            index = (project / "01-source-index.md").read_text(encoding="utf-8")
            self.assertIn("SRC-0001", index)
            self.assertIn("SRC-0002", index)
            validated = run_script("validate_project.py", project, "--mode", "adaptation", "--json")
            self.assertIn('"valid": true', validated.stdout)

    def test_refuses_to_overwrite_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "project"
            run_script("init_project.py", project)
            second = subprocess.run(
                [sys.executable, str(SCRIPTS / "init_project.py"), str(project)],
                text=True,
                capture_output=True,
            )
            self.assertNotEqual(second.returncode, 0)
            self.assertIn("target is not empty", second.stderr)

    def test_stage_limited_project(self) -> None:
        with tempfile.TemporaryDirectory() as temp:
            project = Path(temp) / "gate-a"
            run_script("init_project.py", project, "--mode", "original", "--through", "story-bible")
            self.assertTrue((project / "03-original-discovery.md").is_file())
            self.assertTrue((project / "04-story-bible.md").is_file())
            self.assertFalse((project / "05-season-architecture.md").exists())
            self.assertFalse((project / "06-episode-matrix.csv").exists())
            validated = run_script("validate_project.py", project, "--mode", "original", "--stage", "gate-a")
            self.assertIn("Result: PASS", validated.stdout)


if __name__ == "__main__":
    unittest.main()
