"""Check the published Word output rather than exporter implementation details."""

from __future__ import annotations

import importlib.util
import hashlib
import json
import re
import subprocess
import sys
import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from zipfile import ZipFile
from xml.etree import ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
EXPORTER = ROOT / "mm-write-short-drama/scripts/export_screenplay_docx.py"
ASSETS = ROOT / "mm-write-short-drama/assets"
HAS_DOCX = importlib.util.find_spec("docx") is not None
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"


def paragraph_property(paragraph, tag: str, attr: str = "val") -> str | None:
    """Resolve direct and inherited paragraph properties as a Word reader does."""
    layers = [paragraph._p.pPr]
    style = paragraph.style
    while style is not None:
        layers.append(style.element.find(W + "pPr"))
        style = style.base_style
    for layer in layers:
        child = None if layer is None else layer.find(W + tag)
        if child is not None:
            value = child.get(W + attr)
            if value is not None:
                return value
            if attr == "val":
                return "1"
    return None


def run_property(paragraph, run, tag: str, attr: str = "val") -> str | None:
    """Resolve run properties without requiring direct formatting in the output."""
    layers = [run._r.rPr]
    for first_style in (run.style, paragraph.style):
        style = first_style
        while style is not None:
            layers.append(style.element.find(W + "rPr"))
            style = style.base_style
    defaults = paragraph.part.document.styles.element.find(W + "docDefaults")
    if defaults is not None:
        layers.append(defaults.find(W + "rPrDefault/" + W + "rPr"))
    for layer in layers:
        child = None if layer is None else layer.find(W + tag)
        if child is not None:
            value = child.get(W + attr)
            if value is not None:
                return value
            if attr == "val":
                return "1"
    return None


def character_properties(paragraph):
    return [
        (character, run_property(paragraph, run, "b"), run_property(paragraph, run, "color"))
        for run in paragraph.runs
        for character in run.text
    ]


@unittest.skipUnless(HAS_DOCX, "Word export checks require python-docx")
class WordExportTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.work = Path(self.temp.name)
        self.ep1 = self.work / "EP001.md"
        self.ep2 = self.work / "EP002.md"
        self.ep1.write_text(
            "# 第1集《标签》\n\n"
            "## 本集控制信息\n这行控制信息不应泄漏。\n\n"
            "## 1-1 日 内 档案室\n"
            "人物：甲、乙\n"
            "▲甲把文件袋放到桌面。\n"
            "甲（轻声）：先看标签，再签字。\n"
            "乙：这件事（看向门口）还没说完。\n"
            "VO：电梯即将到达。\n"
            "## 1-2 夜 外 门口\n"
            "人物：乙\n▲乙关上门。\n"
            "## 本集连续性更新\n这行连续性信息不应泄漏。\n"
            "## 改编记录\n这行改编信息不应泄漏。\n",
            encoding="utf-8",
        )
        self.ep2.write_text(
            "# 第2集《回执》\n\n"
            "## 2-1 日 内 收发室\n"
            "人物：甲\n▲甲拿起回执。\n甲：现在可以签了。\n",
            encoding="utf-8",
        )

    def export(self, *extra: str):
        from docx import Document

        output = self.work / ("word-" + str(len(list(self.work.glob("word-*.docx")))) + ".docx")
        result = subprocess.run(
            [
                sys.executable, str(EXPORTER), str(self.ep2), str(self.ep1),
                "--output", str(output), "--project-title", "格式回归样例", *extra,
            ],
            text=True,
            capture_output=True,
        )
        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        return output, Document(output)

    def test_batch_content_is_sorted_complete_and_contains_no_maintenance(self) -> None:
        _, document = self.export()
        texts = [paragraph.text for paragraph in document.paragraphs]
        joined = "\n".join(texts)
        self.assertEqual(texts[0], "格式回归样例")
        episode_positions = [
            (index, int(match.group(1)))
            for index, text in enumerate(texts)
            if (match := re.fullmatch(r"第\s*(\d+)\s*集", text.strip()))
        ]
        self.assertEqual([number for _, number in episode_positions], [1, 2])
        for line in (
            "1-1 日 内 档案室", "1-2 夜 外 门口", "2-1 日 内 收发室",
            "人物：甲、乙", "▲甲把文件袋放到桌面。",
            "甲（轻声）：先看标签，再签字。", "VO：电梯即将到达。",
            "乙：这件事（看向门口）还没说完。", "甲：现在可以签了。",
        ):
            self.assertIn(line, texts)
        for unwanted in ("不应泄漏", "本集控制信息", "本集连续性更新", "改编记录", "［填写］", "[填写]", "故事梗概"):
            self.assertNotIn(unwanted, joined)
        for paragraph in document.paragraphs:
            self.assertNotIn(paragraph_property(paragraph, "pageBreakBefore"), ("1", "true", "on"))
        self.assertFalse(document.element.findall(".//" + W + "br[@" + W + "type='page']"))

    def test_geometry_type_sizes_and_paragraph_rhythm(self) -> None:
        _, document = self.export()
        self.assertEqual(len(document.sections), 1)
        section = document.sections[0]
        self.assertEqual((section.page_width.twips, section.page_height.twips), (11906, 16838))
        self.assertEqual(
            (section.top_margin.twips, section.bottom_margin.twips, section.left_margin.twips, section.right_margin.twips),
            (935, 879, 1134, 1134),
        )
        self.assertEqual((section.header_distance.twips, section.footer_distance.twips), (425, 482))
        title = document.paragraphs[0]
        self.assertEqual(paragraph_property(title, "jc"), "center")
        for run in title.runs:
            if run.text:
                self.assertEqual(run_property(title, run, "sz"), "26")
                self.assertEqual(run_property(title, run, "rFonts", "eastAsia"), "宋体")
        action = next(p for p in document.paragraphs if p.text == "▲甲把文件袋放到桌面。")
        self.assertEqual(paragraph_property(action, "spacing", "line"), "336")
        self.assertEqual(paragraph_property(action, "spacing", "lineRule"), "auto")
        self.assertEqual(paragraph_property(action, "spacing", "after"), "60")
        self.assertEqual(paragraph_property(action, "ind", "firstLine"), "374")
        for run in action.runs:
            if run.text:
                self.assertEqual(run_property(action, run, "sz"), "21")
                self.assertEqual(run_property(action, run, "rFonts", "eastAsia"), "宋体")

    def test_highlights_and_dialogue_colors_are_semantic(self) -> None:
        _, document = self.export()
        highlighted = [p for p in document.paragraphs if re.fullmatch(r"第\s*\d+\s*集", p.text.strip())]
        highlighted.extend(p for p in document.paragraphs if p.text in ("1-1 日 内 档案室", "人物：甲、乙"))
        self.assertEqual(len(highlighted), 4)
        for paragraph in highlighted:
            self.assertEqual(paragraph_property(paragraph, "ind", "firstLine"), "0")
            self.assertIn(paragraph_property(paragraph, "keepNext"), ("1", "true", "on"))
            for run in paragraph.runs:
                if run.text.strip():
                    self.assertIn(run_property(paragraph, run, "b"), ("1", "true", "on"))
                    self.assertEqual(run_property(paragraph, run, "highlight"), "yellow")
                    self.assertEqual(run_property(paragraph, run, "sz"), "21")
        dialogue = next(p for p in document.paragraphs if p.text == "甲（轻声）：先看标签，再签字。")
        properties = character_properties(dialogue)
        for index, (char, bold, color) in enumerate(properties):
            if index in (0, 5):
                self.assertIn(bold, ("1", "true", "on"), char)
                self.assertIn(color, (None, "000000", "auto"), char)
            elif 1 <= index <= 4:
                self.assertNotIn(bold, ("1", "true", "on"), char)
                self.assertIn(color, (None, "000000", "auto"), char)
            else:
                self.assertEqual(color, "0085C9", char)
        inline = next(p for p in document.paragraphs if p.text.startswith("乙：这件事"))
        characters = character_properties(inline)
        start, end = inline.text.index("（"), inline.text.index("）")
        for index in range(start, end + 1):
            self.assertIn(characters[index][2], (None, "000000", "auto"))
        sound = next(p for p in document.paragraphs if p.text.startswith("VO："))
        for index, (char, bold, color) in enumerate(character_properties(sound)):
            if index < 3:
                self.assertIn(bold, ("1", "true", "on"), char)
            else:
                self.assertEqual(color, "0085C9", char)

    def test_footer_uses_live_fields_and_optional_front_matter_is_explicit(self) -> None:
        output, _ = self.export()
        with ZipFile(output) as package:
            footer_files = [name for name in package.namelist() if re.fullmatch(r"word/footer\d+\.xml", name)]
            self.assertTrue(footer_files)
            footers = [ET.fromstring(package.read(name)) for name in footer_files]
            instructions = ["".join(node.itertext()).strip() for footer in footers for node in footer.iter(W + "instrText")]
            self.assertIn("PAGE", instructions)
            self.assertIn("NUMPAGES", instructions)
            self.assertFalse(any(name.startswith("customXml/") for name in package.namelist()))
        front = self.work / "front.md"
        front.write_text("## 项目信息\n制作形式：真人短剧\n## 故事梗概\n这里是当前项目已确认的简介。\n", encoding="utf-8")
        _, with_front = self.export("--front-matter", str(front))
        texts = [p.text for p in with_front.paragraphs]
        self.assertIn("制作形式：真人短剧", texts)
        self.assertIn("这里是当前项目已确认的简介。", texts)
        first_episode = next(i for i, text in enumerate(texts) if re.fullmatch(r"第\s*1\s*集", text.strip()))
        self.assertLess(texts.index("这里是当前项目已确认的简介。"), first_episode)

    def test_existing_delivery_is_not_silently_replaced(self) -> None:
        output, _ = self.export()
        before = output.read_bytes()
        result = subprocess.run(
            [sys.executable, str(EXPORTER), str(self.ep1), "--output", str(output)],
            text=True, capture_output=True,
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertEqual(output.read_bytes(), before)

    def test_base_template_contains_only_neutral_slots_and_matches_manifest(self) -> None:
        template = ASSETS / "screenplay-base-template.docx"
        manifest = json.loads((ASSETS / "screenplay-base-template.json").read_text(encoding="utf-8"))
        self.assertEqual(manifest["template"], template.name)
        self.assertEqual(manifest["templateSha256"], hashlib.sha256(template.read_bytes()).hexdigest())
        self.assertNotIn("referencePath", manifest)
        self.assertEqual(Path(manifest["referenceFile"]).name, manifest["referenceFile"])
        neutral_text = {
            "项目名称", "项目信息：［填写当前项目信息，可选］", "前置信息标题［可选］",
            "［填写已确认的当前项目简介或人物设定，可选］", "第 1 集",
            "1-1 日 内 ［场景名称］", "人物：［角色甲］、［角色乙］",
            "▲［可拍摄动作］", "角色甲：", "（表演提示）", "［对白内容］",
            "VO：", "［画外音内容］", "PAGE", "NUMPAGES", "1", "/",
            "短剧剧本基础模板", "Short Drama Screenwriter",
        }
        with ZipFile(template) as package:
            self.assertFalse(any(name.startswith(("customXml/", "word/comments", "word/media/")) for name in package.namelist()))
            for name in package.namelist():
                if not name.endswith(".xml"):
                    continue
                for node in ET.fromstring(package.read(name)).iter():
                    text = (node.text or "").strip()
                    if not text:
                        continue
                    if node.tag in {
                        "{http://purl.org/dc/terms/}created",
                        "{http://purl.org/dc/terms/}modified",
                    }:
                        self.assertRegex(text, r"^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\dZ$")
                    else:
                        self.assertIn(text, neutral_text, f"Unexpected retained text in {name}")

    def test_existing_cast_wrapper_can_wrap_and_resave_export(self) -> None:
        """Exercise the legacy caller's rPr clone/clear/reinsert sequence."""
        from docx import Document

        name = "_word_export_cast_compat"
        spec = importlib.util.spec_from_file_location(name, EXPORTER)
        self.assertIsNotNone(spec)
        self.assertIsNotNone(spec.loader)
        exporter = importlib.util.module_from_spec(spec)
        sys.modules[name] = exporter
        self.addCleanup(sys.modules.pop, name, None)
        spec.loader.exec_module(exporter)
        cast = "人物：" + "、".join(f"角色{number:02d}" for number in range(1, 13))
        source = self.work / "EP003.md"
        source.write_text(f"# 第3集\n## 3-1 日 内 排练室\n{cast}\n▲众人就位。\n", encoding="utf-8")
        output = self.work / "cast-compat.docx"
        exporter.build_docx([exporter.parse_episode(source)], output, "接口兼容样例", False)
        document = Document(output)
        paragraph = next(p for p in document.paragraphs if p.text == cast)
        segments = []
        current = ""
        for person in paragraph.text.split("、"):
            candidate = current + "、" + person if current else person
            if current and len(candidate) > 34:
                segments.append(current + "、")
                current = person
            else:
                current = candidate
        if current:
            segments.append(current)
        properties = deepcopy(paragraph.runs[0]._element.rPr)
        paragraph.clear()
        run = paragraph.add_run("\n".join(segments))
        run._element.insert(0, properties)
        document.save(output)
        wrapped = next(p for p in Document(output).paragraphs if p.text.replace("\n", "") == cast)
        self.assertGreater(len(wrapped.text.splitlines()), 1)
        self.assertEqual(wrapped.text.replace("\n", ""), cast)
        for run in wrapped.runs:
            self.assertIn(run_property(wrapped, run, "b"), ("1", "true", "on"))
            self.assertEqual(run_property(wrapped, run, "highlight"), "yellow")
            self.assertEqual(run_property(wrapped, run, "sz"), "21")
            self.assertEqual(run_property(wrapped, run, "rFonts", "eastAsia"), "宋体")


if __name__ == "__main__":
    unittest.main()
