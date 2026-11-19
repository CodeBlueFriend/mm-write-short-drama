#!/usr/bin/env python3
"""Merge episode Markdown files into one production-facing screenplay DOCX."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from datetime import datetime, timezone
import re
import sys
import zipfile
from dataclasses import dataclass
from pathlib import Path
from xml.etree import ElementTree

from render_screenplay import verify_render_manifest

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
            files.extend(sorted((p for p in path.glob("EP*.md") if re.fullmatch(r"EP\d+\.md", p.name, re.I)), key=natural_key))
        elif path.is_file() and path.suffix.lower() == ".md":
            files.append(path)
        else:
            raise ValueError(f"not an episode Markdown file or directory: {path}")
    unique = list(dict.fromkeys(files))
    if len(unique) != len(files):
        raise ValueError("duplicate episode input paths")
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
    scene_numbers = [int(SCENE_NUMBER_RE.match(scene).group("scene")) for scene in scenes]
    if scene_numbers != list(range(1, len(scene_numbers)+1)):
        raise ValueError(f"{path}: scene numbers must be unique, ordered and contiguous from 1")
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
    for kind, text in front_matter_blocks(path):
        if text:
            document.add_paragraph(text, style="前置标题" if kind=="heading" else "前置信息")
        else:
            add_blank_paragraph(document, style="前置信息")


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
    preview: bool = True,
    project_dir: Path | None = None,
) -> None:
    if output.resolve() == BASE_TEMPLATE.resolve():
        raise ValueError("output must not overwrite the base template")
    if output.with_suffix(".delivery.json").exists():
        raise FileExistsError("published delivery is immutable, including preview retries; choose a new filename")
    if output.exists() and not force:
        raise FileExistsError(f"output exists; pass --force to replace it: {output}")
    if output.exists() and force:
        if not preview:
            raise FileExistsError("formal files cannot be replaced with force")
        try:
            existing_preview = Document(output).core_properties.category == "PREVIEW"
        except Exception:
            existing_preview = False
        if not existing_preview:
            raise FileExistsError("force can replace only a labeled preview; choose a new filename")
    if not preview:
        if project_dir is None or front_matter is None:
            raise ValueError("formal build requires project_dir and approved front_matter")
        project_dir = project_dir.resolve()
        if output.resolve().parent != project_dir / ".drama" / "staging":
            raise ValueError("formal builds must be staged before visual QA and publish")
        errors = validate_front_matter(front_matter, project_title, [e.number for e in episodes], project_total(project_dir))
        errors.extend(release_errors(project_dir, episodes, front_matter))
        if errors:
            raise ValueError("; ".join(errors))
    document = load_base_template()
    document.core_properties.title = project_title
    document.add_paragraph(project_title, style="剧本标题")
    if preview:
        document.core_properties.category = "PREVIEW"
        document.add_paragraph("版式预览 尚未通过正式交付验收", style="前置信息")
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


FRONT_MODULES = ["剧本名", "来源", "类型", "集数", "剧名寓意", "热门元素", "创作理由", "故事梗概", "主要角色"]
PLACEHOLDER_RE = re.compile(r"\[.?填写|［.?填写|待填写|待补充|TODO|TBD|占位|示例人物|角色甲|角色乙")


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_front_modules(path: Path) -> list[tuple[str, str]]:
    modules: list[tuple[str,str]]=[]
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line=clean_markdown(re.sub(r"^#{1,6}\s+", "", raw.strip()))
        if not line: continue
        match=re.fullmatch(r"(剧本名|来源|类型|短剧类型|剧名寓意|热门元素|创作理由|故事梗概|主要角色|集数)(?:\s*[：:]\s*(.*)|\s*)",line)
        if match:
            name="类型" if match.group(1)=="短剧类型" else match.group(1)
            modules.append((name,match.group(2) or ""))
        elif modules:
            name,body=modules[-1]
            modules[-1]=(name,(body+"\n"+line).strip())
    return modules


def front_matter_blocks(path: Path) -> list[tuple[str,str]]:
    modules=read_front_modules(path)
    if [name for name,_ in modules]==FRONT_MODULES:
        blocks=[]
        for index,(name,body) in enumerate(modules):
            if index<6:
                blocks.append(("body",name+"："+body.replace("\n"," ")))
            else:
                blocks.append(("heading",name+"："))
                blocks.extend(("body",line) for line in body.splitlines())
        return blocks
    blocks=[]
    for raw in path.read_text(encoding="utf-8-sig").splitlines():
        line=raw.strip()
        if not line:
            blocks.append(("body",""));continue
        heading=re.match(r"^#{1,6}\s+(.+)$",line)
        if heading: blocks.append(("heading",clean_markdown(heading.group(1))))
        elif not re.fullmatch(r"[-*_]{3,}",line): blocks.append(("body",clean_markdown(line)))
    return blocks


def validate_front_matter(path: Path, title: str, numbers: list[int], total: int | None = None) -> list[str]:
    """Validate required current-project modules, independently of content review."""
    text = path.read_text(encoding="utf-8-sig")
    modules = read_front_modules(path)
    errors: list[str] = []
    if [name for name, _ in modules] != FRONT_MODULES:
        errors.append("front matter must contain the nine modules in order: " + "、".join(FRONT_MODULES))
    data = dict(modules)
    for name in FRONT_MODULES:
        if not data.get(name, "").strip():
            errors.append(f"empty front-matter module: {name}")
    if data.get("剧本名", "").strip("《》 ") != title.strip("《》 "):
        errors.append("front-matter 剧本名 must equal the visible project title")
    if PLACEHOLDER_RE.search(text):
        errors.append("front matter contains placeholder or reference-screenplay content")
    count = data.get("集数", "")
    total_match = re.search(r"(?:全剧)?\s*共\s*(\d+)\s*集", count)
    range_match = re.search(r"本稿(?:为|范围为|交付)?\s*第?\s*(\d+)\s*(?:[—–－至到-]\s*(\d+)\s*)?集", count)
    if not total_match or not range_match:
        errors.append("集数 must state 全剧共N集，本稿为第X—Y集正式剧本")
    else:
        stated_total = int(total_match.group(1))
        start, end = int(range_match.group(1)), int(range_match.group(2) or range_match.group(1))
        if (start, end) != (numbers[0], numbers[-1]) or stated_total < end or (total and stated_total != total):
            errors.append("front-matter total/range does not match the selected episodes and project")
    # Content truth, author attribution, role completeness and spoiler intent are
    # validated by the final reading, bound to this exact file hash.
    return errors


def expected_paragraphs(episodes: list[Episode], title: str, front_matter: Path | None) -> list[str]:
    result = [title]
    if front_matter:
        result.extend(text for _,text in front_matter_blocks(front_matter) if text)
    for episode in episodes:
        result.append(f"第 {episode.number} 集")
        result.extend(text for _, text in episode.blocks)
    return result


def verify_visible_text(path: Path, episodes: list[Episode], title: str, front_matter: Path) -> str:
    actual = [p.text.strip() for p in Document(path).paragraphs if p.text.strip()]
    expected = expected_paragraphs(episodes, title, front_matter)
    if actual != expected:
        mismatch = next((i for i, (a,b) in enumerate(zip(actual, expected)) if a != b), min(len(actual),len(expected)))
        raise ValueError(f"Word visible text differs from reviewed source at paragraph {mismatch+1}")
    return hashlib.sha256("\n".join(actual).encode("utf-8")).hexdigest()


def release_errors(project: Path, episodes: list[Episode], front: Path) -> list[str]:
    try:
        from workflow_lib import validate_release
    except ImportError as exc:
        raise ValueError("workflow release gate is unavailable; use --preview only for a labeled layout preview") from exc
    # Never allow exporting an unreviewed file with the same episode number.
    errors = []
    for episode in episodes:
        canonical = project / "episodes" / f"EP{episode.number:03d}.md"
        if not canonical.is_file() or file_hash(canonical) != file_hash(episode.source):
            errors.append(f"EP{episode.number:03d}: selected file differs from the project's reviewed episode")
    errors.extend(validate_release(project, [f"{e.number:03d}" for e in episodes], front_matter=front))
    return errors


def project_total(project: Path) -> int | None:
    state = json.loads((project / ".drama/project-state.json").read_text(encoding="utf-8"))
    value = state.get("totalEpisodes") or state.get("specifications",{}).get("totalEpisodes")
    return int(value) if value else None


def stage_release(project: Path, episodes: list[Episode], output: Path, title: str, front: Path) -> Path:
    errors = validate_front_matter(front, title, [e.number for e in episodes], project_total(project))
    errors.extend(release_errors(project, episodes, front))
    if errors:
        raise ValueError("; ".join(errors))
    if output.exists():
        raise FileExistsError("existing formal delivery is immutable; choose a new output filename")
    staging = project / ".drama" / "staging"
    staging.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    staged = staging / f"{output.stem}-{stamp}.docx"
    build_docx(episodes, staged, title, False, front_matter=front, preview=False, project_dir=project)
    visible_hash = verify_visible_text(staged, episodes, title, front)
    manifest = {
        "schemaVersion":"1.0.0", "status":"awaiting_visual_qa", "project":str(project),
        "target":str(output), "title":title, "frontMatter":str(front), "frontHash":file_hash(front),
        "episodes":[{"number":e.number,"source":str(e.source),"hash":file_hash(e.source)} for e in episodes],
        "stagedHash":file_hash(staged), "visibleTextHash":visible_hash,
        "createdAt":datetime.now(timezone.utc).isoformat(),
    }
    staged.with_suffix(".manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return staged


def publish_release(staged: Path, qa_path: Path) -> Path:
    manifest = json.loads(staged.with_suffix(".manifest.json").read_text(encoding="utf-8"))
    if manifest.get("status") != "awaiting_visual_qa":
        raise ValueError("staged release has already been published or is invalid")
    project, front = Path(manifest["project"]), Path(manifest["frontMatter"])
    output = Path(manifest["target"])
    if output.exists():
        raise FileExistsError("existing formal delivery is immutable; stage a new version")
    if file_hash(staged) != manifest["stagedHash"] or file_hash(front) != manifest["frontHash"]:
        raise ValueError("staged Word or front matter changed after content verification")
    episodes=[]
    for item in manifest["episodes"]:
        source=Path(item["source"])
        if file_hash(source) != item["hash"]:
            raise ValueError(f"EP{item['number']:03d} changed after staging")
        episodes.append(parse_episode(source))
    errors=validate_front_matter(front,manifest["title"],[e.number for e in episodes],project_total(project))
    errors.extend(release_errors(project,episodes,front))
    if errors:
        raise ValueError("; ".join(errors))
    if verify_visible_text(staged,episodes,manifest["title"],front) != manifest["visibleTextHash"]:
        raise ValueError("visible text fingerprint changed")
    qa=json.loads(qa_path.read_text(encoding="utf-8"))
    if qa.get("docxHash") != file_hash(staged) or qa.get("passed") is not True or not qa.get("reviewer") or not qa.get("notes"):
        raise ValueError("visual QA must identify this exact DOCX, reviewer, result and observations")
    if not qa.get("renderManifest"):
        raise ValueError("visual QA requires the manifest from an actual fresh render")
    render_manifest_path=Path(qa["renderManifest"]).expanduser()
    if not render_manifest_path.is_absolute():
        render_manifest_path=qa_path.parent/render_manifest_path
    pages=qa.get("pages",[])
    render_dir=Path(qa.get("renderDirectory", "")).expanduser()
    if not render_dir.is_absolute():
        render_dir=qa_path.parent/render_dir
    render_errors=verify_render_manifest(staged,render_manifest_path,render_dir)
    if render_errors:
        raise ValueError("; ".join(render_errors))
    if not render_dir.is_dir():
        raise ValueError("visual QA renderDirectory is missing")
    rendered=sorted(render_dir.glob("page-*.png"),key=natural_key)
    if not rendered or len(pages)!=len(rendered):
        raise ValueError("visual QA must cover every rendered page")
    if [p.name for p in rendered] != [f"page-{i}.png" for i in range(1,len(rendered)+1)]:
        raise ValueError("rendered page numbering is incomplete")
    seen=set()
    for item in pages:
        page=Path(item.get("path",""))
        if page.resolve() not in {p.resolve() for p in rendered} or page.resolve() in seen or item.get("sha256")!=file_hash(page) or item.get("inspected") is not True:
            raise ValueError("page QA is missing, duplicated, changed or uninspected")
        seen.add(page.resolve())
    output.parent.mkdir(parents=True,exist_ok=True)
    # exclusive creation: even concurrent retries cannot overwrite a delivery
    created = False
    try:
        with output.open("xb") as target, staged.open("rb") as source:
            created = True
            shutil.copyfileobj(source,target)
    except Exception:
        # Only remove a partial file created by this invocation.
        if created and output.exists() and file_hash(output)!=manifest["stagedHash"]:
            output.unlink()
        raise
    manifest.update(status="published",publishedAt=datetime.now(timezone.utc).isoformat(),visualQaHash=file_hash(qa_path),renderManifest=str(render_manifest_path.resolve()),renderManifestHash=file_hash(render_manifest_path),outputHash=file_hash(output))
    staged.with_suffix(".manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    output.with_suffix(".delivery.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return output


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs",nargs="*",type=Path,help="Episode Markdown files or an episodes directory")
    parser.add_argument("--output",type=Path,help="Intended combined .docx delivery path")
    parser.add_argument("--project-title",help="Visible current-project title")
    parser.add_argument("--front-matter",type=Path,help="Reviewed current-project preface with all nine modules")
    parser.add_argument("--project-dir",type=Path,help="Project whose current review evidence permits delivery")
    parser.add_argument("--preview",action="store_true",help="Write a visibly labeled layout preview; never a formal delivery")
    parser.add_argument("--publish",type=Path,help="Publish a staged Word after visual inspection")
    parser.add_argument("--visual-qa",type=Path,help="Actual page inspection record for --publish")
    parser.add_argument("--force",action="store_true",help="Replace a preview only; formal deliveries are immutable")
    args=parser.parse_args()
    try:
        if args.publish:
            if not args.visual_qa or args.preview or args.inputs:
                raise ValueError("--publish requires --visual-qa and cannot be combined with preview or inputs")
            output=publish_release(args.publish.expanduser().resolve(),args.visual_qa.expanduser().resolve())
            print(json.dumps({"status":"published","output":str(output)},ensure_ascii=False))
            return 0
        if not args.inputs or not args.output:
            raise ValueError("inputs and --output are required")
        output=args.output.expanduser().resolve()
        if output.suffix.lower()!=".docx":
            raise ValueError("--output must end in .docx")
        episodes=sorted((parse_episode(p) for p in collect_inputs(args.inputs)),key=lambda e:e.number)
        numbers=[e.number for e in episodes]
        if len(numbers)!=len(set(numbers)):
            raise ValueError("duplicate episode numbers in inputs")
        if numbers!=list(range(numbers[0],numbers[-1]+1)):
            raise ValueError("episode range has gaps")
        title=(args.project_title or infer_project_title(output)).strip()
        if not title:
            raise ValueError("--project-title must not be blank")
        front=args.front_matter.expanduser().resolve() if args.front_matter else None
        if args.preview:
            build_docx(episodes,output,title,args.force,front_matter=front,preview=True)
            print(json.dumps({"status":"preview","output":str(output),"episodes":numbers},ensure_ascii=False))
        else:
            if not args.project_dir or not front:
                raise ValueError("formal export requires --project-dir and --front-matter; use --preview for layout-only output")
            if args.force:
                raise ValueError("--force applies to previews only")
            staged=stage_release(args.project_dir.expanduser().resolve(),episodes,output,title,front)
            print(json.dumps({"status":"awaiting_visual_qa","staged":str(staged),"target":str(output)},ensure_ascii=False))
        return 0
    except (FileExistsError,OSError,ValueError,KeyError) as exc:
        parser.error(str(exc))


if __name__=="__main__":
    raise SystemExit(main())
