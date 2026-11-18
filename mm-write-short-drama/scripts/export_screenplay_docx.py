#!/usr/bin/env python3
"""Merge episode Markdown files into one production-facing screenplay DOCX."""

from __future__ import annotations

import argparse
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

try:
    from docx import Document
    from docx.oxml.ns import qn
except ImportError as exc:  # pragma: no cover - environment-dependent message
    raise SystemExit(
        "python-docx is required. Run this script with the Codex workspace Python runtime."
    ) from exc


EPISODE_TITLE_RE = re.compile(
    r"^#\s+第\s*(?P<number>\d+)\s*集\s*(?:《(?P<title>[^》]+)》)?\s*$",
    re.M,
)
SCENE_NUMBER_RE = re.compile(r"^(?P<number>\d+)-(?P<scene>\d+)\s+(?P<rest>.+)$")
OLD_SCENE_RE = re.compile(
    r"^(?P<number>\d+-\d+)\s+"
    r"(?P<interior>内景|外景|内/外景|外/内景)[·・]\s*"
    r"(?P<location>.+?)[·・]\s*"
    r"(?P<time>日|夜|晨|早|午|晚|黄昏|清晨|傍晚|上午|中午|下午|午后|深夜|凌晨)$"
)
NEW_SCENE_RE = re.compile(
    r"^(?P<number>\d+-\d+)\s+"
    r"(?P<time>日|夜|晨|早|午|晚|黄昏|清晨|傍晚|上午|中午|下午|午后|深夜|凌晨)\s+"
    r"(?P<interior>内|外|内/外|外/内|内景|外景|内/外景|外/内景)\s+"
    r"(?P<location>.+)$"
)
DIALOGUE_RE = re.compile(r"^[^#\s][^：:\n]{0,40}[：:].+")
COLON_RE = re.compile(r"^(?P<speaker>[^：:\n]{1,40})[：:].+")
GENERIC_SPEAKER_RE = re.compile(r"^(?:HR|人事|同学|毕业生)[甲乙丙丁一二三四五六七八九十\d]*$")
HIDDEN_SECTIONS = {"本集控制信息", "本集连续性更新", "改编记录"}
WORD_NAMESPACE = "http://schemas.openxmlformats.org/wordprocessingml/2006/main"


@dataclass(frozen=True)
class Episode:
    number: int
    blocks: tuple[tuple[str, str], ...]
    source: Path


def natural_key(path: Path) -> tuple[int, str]:
    match = re.search(r"(\d+)", path.stem)
    return (int(match.group(1)) if match else sys.maxsize, path.name)


def collect_inputs(items: list[Path]) -> list[Path]:
    files: list[Path] = []
    for item in items:
        path = item.expanduser().resolve()
        if path.is_dir():
            files.extend(sorted(path.glob("EP*.md"), key=natural_key))
        elif path.is_file() and path.suffix.lower() == ".md":
            files.append(path)
        else:
            raise ValueError(f"not an episode Markdown file or directory: {path}")
    unique = list(dict.fromkeys(files))
    if not unique:
        raise ValueError("no episode Markdown files found")
    return unique


def clean_markdown(text: str) -> str:
    text = re.sub(r"^[-*+]\s+", "", text.strip())
    text = text.replace("**", "").replace("__", "").replace("`", "")
    return text.strip()


def normalize_scene_heading(text: str) -> str | None:
    def delivery_time(value: str) -> str:
        return "夜" if value in {"夜", "晚", "深夜", "凌晨"} else "日"

    text = clean_markdown(text)
    match = NEW_SCENE_RE.match(text)
    if match:
        interior = match.group("interior").replace("景", "")
        return f"{match.group('number')} {delivery_time(match.group('time'))} {interior} {match.group('location')}"
    match = OLD_SCENE_RE.match(text)
    if match:
        interior = match.group("interior").replace("景", "")
        return f"{match.group('number')} {delivery_time(match.group('time'))} {interior} {match.group('location')}"
    return None


def extract_cast_speakers(line: str) -> set[str]:
    body = line.split("：", 1)[1] if "：" in line else line.split(":", 1)[1]
    speakers: set[str] = set()
    for item in re.split(r"[、，,]", body):
        name = item.strip()
        if not name or name in {"同上", "众人"}:
            continue
        speakers.add(name)
        base = re.sub(r"（[^）]*）|\([^)]*\)", "", name).strip()
        if base:
            speakers.add(base)
    return speakers


def is_dialogue(line: str, speakers: set[str]) -> bool:
    match = COLON_RE.match(line)
    if not match:
        return False
    speaker = match.group("speaker").strip()
    base = re.sub(r"（[^）]*）|\([^)]*\)", "", speaker).strip()
    if speaker in speakers or base in speakers:
        return True
    if speaker in {"VO", "OS", "旁白"} or speaker.endswith(("OS", "VO")):
        return True
    if re.search(r"（(?:画外音|电话声|声音)）|\((?:画外音|电话声|声音)\)", speaker):
        return True
    return bool(GENERIC_SPEAKER_RE.fullmatch(base))


def parse_episode(path: Path) -> Episode:
    content = path.read_text(encoding="utf-8-sig")
    title_match = EPISODE_TITLE_RE.search(content)
    if not title_match:
        raise ValueError(f"{path}: missing '# 第NN集' title")
    number = int(title_match.group("number"))
    blocks: list[tuple[str, str]] = []
    hidden = False
    speakers: set[str] = set()

    for raw in content.splitlines():
        stripped = raw.strip()
        if not stripped or EPISODE_TITLE_RE.match(stripped):
            continue
        if stripped.startswith("## "):
            heading = clean_markdown(stripped[3:])
            if heading in HIDDEN_SECTIONS:
                hidden = True
                continue
            scene = normalize_scene_heading(heading)
            if scene:
                hidden = False
                blocks.append(("scene", scene))
            continue
        if hidden or stripped.startswith("#"):
            continue

        line = clean_markdown(stripped)
        if not line:
            continue
        if line.startswith("人物：") or line.startswith("人物:"):
            line = line.replace("人物:", "人物：", 1)
            cast_speakers = extract_cast_speakers(line)
            if "同上" in line:
                speakers.update(cast_speakers)
            else:
                speakers = cast_speakers
            blocks.append(("cast", line))
        elif line.startswith("【") and line.endswith("】"):
            blocks.append(("transition", line))
        elif re.match(r"^(?:音效|声音|环境音|音乐|SFX|BGM)[：:]", line, re.I):
            blocks.append(("sound", line))
        elif is_dialogue(line, speakers):
            blocks.append(("dialogue", line))
        else:
            blocks.append(("action", line if line.startswith("▲") else f"▲{line}"))

    scenes = [text for kind, text in blocks if kind == "scene"]
    if not scenes:
        raise ValueError(f"{path}: no standard scene heading found")
    for scene in scenes:
        scene_episode = int(SCENE_NUMBER_RE.match(scene).group("number"))
        if scene_episode != number:
            raise ValueError(
                f"{path}: scene heading {scene!r} does not match episode {number}"
            )
    return Episode(number=number, blocks=tuple(blocks), source=path)


def infer_project_title(output: Path) -> str:
    """Infer the visible document title from the delivery filename."""
    title = output.stem.strip()
    title = re.sub(r"[_-]?第\d+(?:-\d+)?集$", "", title).strip(" _-")
    title = re.sub(r"[（(]\d+(?:-\d+)?集[）)]$", "", title).strip(" _-")
    return title or output.stem


BASE_TEMPLATE = Path(__file__).resolve().parents[1] / "assets" / "screenplay-base-template.docx"
REQUIRED_STYLES = {
    "剧本标题", "剧集标题", "场次标题", "人物行", "剧本文本", "对白文本",
    "声音文本", "前置信息", "前置标题", "转场标记", "对白角色", "对白提示", "对白台词",
}
SOUND_LABEL_RE = re.compile(r"^(?:音效|声音|环境音|音乐|SFX|BGM|OS|VO)$", re.I)
PARENTHETICAL_RE = re.compile(r"（[^）]*）|\([^)]*\)")


def load_base_template() -> Document:
    """Load the distilled reference design; original screenplay prose is absent."""
    if not BASE_TEMPLATE.is_file():
        raise ValueError(f"base template is missing: {BASE_TEMPLATE}")
    document = Document(BASE_TEMPLATE)
    missing = sorted(REQUIRED_STYLES - {style.name for style in document.styles})
    if missing:
        raise ValueError(f"base template lacks required styles: {', '.join(missing)}")
    body = document._element.body
    for child in list(body):
        if child.tag != qn("w:sectPr"):
            body.remove(child)
    return document


def add_dialogue_runs(paragraph, text: str, *, sound: bool = False) -> None:
    """Preserve every input character while applying speaker/note/speech colors."""
    match = re.match(r"^(?P<label>[^：:]+)(?P<colon>[：:])(?P<body>.*)$", text)
    if not match:
        paragraph.add_run(text)
        return

    def add_segment(segment: str, *, label: bool = False) -> None:
        position = 0
        for note in PARENTHETICAL_RE.finditer(segment):
            if position < note.start():
                paragraph.add_run(segment[position:note.start()], style="对白角色" if label else "对白台词")
            paragraph.add_run(note.group(), style="对白提示" if label or not sound else "对白台词")
            position = note.end()
        if position < len(segment):
            paragraph.add_run(segment[position:], style="对白角色" if label else "对白台词")

    add_segment(match.group("label"), label=True)
    paragraph.add_run(match.group("colon"), style="对白角色")
    add_segment(match.group("body"))


def add_body_paragraph(document: Document, kind: str, text: str) -> None:
    label = re.split(r"[：:]", text, maxsplit=1)[0]
    sound = kind == "sound" or (kind == "dialogue" and bool(SOUND_LABEL_RE.fullmatch(label)))
    style_name = {
        "scene": "场次标题", "cast": "人物行", "transition": "转场标记",
        "dialogue": "声音文本" if sound else "对白文本", "sound": "声音文本",
        "action": "剧本文本",
    }[kind]
    paragraph = document.add_paragraph(style=style_name)
    if kind in {"dialogue", "sound"}:
        add_dialogue_runs(paragraph, text, sound=sound)
    else:
        run = paragraph.add_run(text)
        # Project wrappers may clone rPr when wrapping long cast lines.
        # Keep that OOXML node available; the base style still owns its values.
        run._r.get_or_add_rPr()


def add_front_matter(document: Document, path: Path | None) -> None:
    """Render only explicitly supplied current-project preface Markdown."""
    if path is None:
        return
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        stripped = raw.strip()
        if not stripped:
            add_blank_paragraph(document, style="前置信息")
            continue
        heading = re.match(r"^#{1,6}\s+(.+)$", stripped)
        if heading:
            document.add_paragraph(clean_markdown(heading.group(1)), style="前置标题")
        elif not re.fullmatch(r"[-*_]{3,}", stripped):
            document.add_paragraph(clean_markdown(stripped), style="前置信息")


def add_font_fallbacks(path: Path) -> None:
    """Keep source 宋体 in Word/WPS and register the macOS rendering fallback."""
    rewritten = path.with_name(f".{path.name}.fonts.docx")
    with zipfile.ZipFile(path, "r") as source, zipfile.ZipFile(
        rewritten, "w", compression=zipfile.ZIP_DEFLATED
    ) as target:
        for item in source.infolist():
            data = source.read(item.filename)
            if item.filename == "word/fontTable.xml":
                root = ElementTree.fromstring(data)
                font = next((node for node in root.findall(f"{{{WORD_NAMESPACE}}}font")
                             if node.get(f"{{{WORD_NAMESPACE}}}name") == "宋体"), None)
                if font is None:
                    font = ElementTree.SubElement(root, f"{{{WORD_NAMESPACE}}}font",
                                                  {f"{{{WORD_NAMESPACE}}}name": "宋体"})
                alternate = font.find(f"{{{WORD_NAMESPACE}}}altName")
                if alternate is None:
                    alternate = ElementTree.SubElement(font, f"{{{WORD_NAMESPACE}}}altName")
                alternate.set(f"{{{WORD_NAMESPACE}}}val", "Songti SC")
                data = ElementTree.tostring(root, encoding="utf-8", xml_declaration=True)
            target.writestr(item, data)
    rewritten.replace(path)


def add_blank_paragraph(document: Document, style: str = "剧本文本") -> None:
    document.add_paragraph(style=style)


def build_docx(
    episodes: list[Episode], output: Path, project_title: str, force: bool,
    front_matter: Path | None = None,
) -> None:
    if output.resolve() == BASE_TEMPLATE.resolve():
        raise ValueError("output must not overwrite the base template")
    if output.exists() and not force:
        raise FileExistsError(f"output exists; pass --force to replace it: {output}")
    document = load_base_template()
    document.core_properties.title = project_title
    document.add_paragraph(project_title, style="剧本标题")
    add_front_matter(document, front_matter)
    for episode in episodes:
        add_blank_paragraph(document)
        document.add_paragraph(f"第 {episode.number} 集", style="剧集标题")
        scene_count = 0
        for kind, text in episode.blocks:
            if kind == "scene":
                if scene_count:
                    add_blank_paragraph(document)
                scene_count += 1
            add_body_paragraph(document, kind, text)

    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(f".{output.name}.tmp.docx")
    try:
        document.save(temporary)
        add_font_fallbacks(temporary)
        temporary.replace(output)
    finally:
        temporary.unlink(missing_ok=True)
        temporary.with_name(f".{temporary.name}.fonts.docx").unlink(missing_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="Episode Markdown files or an episodes directory")
    parser.add_argument("--output", required=True, type=Path, help="Combined .docx output path")
    parser.add_argument(
        "--project-title",
        help="Visible title at the start of the Word document (defaults to the output filename without its episode range)",
    )
    parser.add_argument("--front-matter", type=Path, help="Optional approved current-project preface Markdown; never copied from the reference")
    parser.add_argument("--force", action="store_true", help="Replace an existing output file")
    args = parser.parse_args()

    output = args.output.expanduser().resolve()
    if output.suffix.lower() != ".docx":
        parser.error("--output must end in .docx")
    try:
        files = collect_inputs(args.inputs)
        episodes = sorted((parse_episode(path) for path in files), key=lambda item: item.number)
        numbers = [episode.number for episode in episodes]
        if len(numbers) != len(set(numbers)):
            raise ValueError("duplicate episode numbers in inputs")
        project_title = (args.project_title or infer_project_title(output)).strip()
        if not project_title:
            raise ValueError("--project-title must not be blank")
        build_docx(episodes, output, project_title, args.force, front_matter=args.front_matter)
    except (FileExistsError, OSError, ValueError) as exc:
        parser.error(str(exc))

    episode_range = f"第{numbers[0]}集" if len(numbers) == 1 else f"第{numbers[0]}-{numbers[-1]}集"
    print(f"Merged {len(episodes)} episode(s) ({episode_range}) into: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
