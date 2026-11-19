"""Exercise delivery from a single installed skill directory."""

import importlib.util
import json
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from zipfile import ZipFile


SKILL = Path(__file__).resolve().parents[1] / "mm-write-short-drama"


@unittest.skipUnless(importlib.util.find_spec("docx"), "Word export requires python-docx")
class BundledDeliveryTests(unittest.TestCase):
    def test_install_can_check_and_preview_without_sibling_skills(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            installed = root / "skills" / SKILL.name
            shutil.copytree(SKILL, installed, ignore=shutil.ignore_patterns("__pycache__"))
            project = root / "project"
            project.mkdir()

            def run(script, *args, expected=0):
                result = subprocess.run(
                    [sys.executable, str(installed / "scripts" / script), *map(str, args)],
                    cwd=project,
                    text=True,
                    capture_output=True,
                    check=False,
                )
                self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
                return result.stdout

            rules = installed / "references" / "vendor"
            self.assertIn("version: \"3.0.0\"", (rules / "humanizer.md").read_text(encoding="utf-8"))
            self.assertIn("Siqi Chen", (rules / "humanizer-LICENSE").read_text(encoding="utf-8"))
            self.assertEqual(list(installed.parent.iterdir()), [installed])
            draft = project / "draft.md"
            final = project / "EP001.md"
            log = project / ".humanizer" / "runs.jsonl"
            output = project / "示例_第01集.docx"
            header = "# 第01集《试验》\n\n## 1-1 夜 内 值班室\n\n人物：小周\n\n"
            draft.write_text(header + "小周：这一事实非常重要，我得让别人知道。\n", encoding="utf-8")
            final.write_text(header + "小周：这事得让她知道。\n", encoding="utf-8")
            check_args = ["check", "--final", final, "--log", log]
            run("humanizer_gate.py", *check_args, expected=3)
            run("humanizer_gate.py", "verify", "--draft", draft, "--final", final)
            run(
                "humanizer_gate.py", "record", "--draft", draft, "--final", final,
                "--adapter", "short-drama", "--attestation", "model-edit-complete", "--log", log,
            )
            self.assertTrue(json.loads(run("humanizer_gate.py", *check_args))["processed"])
            run("export_screenplay_docx.py", final, "--output", output, "--project-title", "示例", expected=2)
            self.assertFalse(output.exists())
            run("export_screenplay_docx.py", final, "--output", output, "--project-title", "示例", "--preview")
            with ZipFile(output) as package:
                body = package.read("word/document.xml").decode("utf-8")
            self.assertIn("这事得让她知道。", body)
            self.assertNotIn("这一事实非常重要", body)
            self.assertIn("版式预览", body)
            final.write_text(final.read_text(encoding="utf-8") + "▲ 小周推开门。\n", encoding="utf-8")
            run("humanizer_gate.py", *check_args, expected=3)
