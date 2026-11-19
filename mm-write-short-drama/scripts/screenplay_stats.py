#!/usr/bin/env python3
"""Report deterministic scene, character, dialogue, and duration estimates."""

from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path


SCENE = re.compile(
    r"^##\s+\d+-\d+\s+(?:(?:日|夜|晨|早|午|晚|黄昏|清晨|傍晚)\s+(?:内|外|内/外|外/内)|(?:内景|外景|内/外景|外/内景))",
    re.M,
)
DIALOGUE = re.compile(r"^([^#|\s][^：:\n]{0,24})[：:]\s*(.+)$")
CHARACTERS = re.compile(r"^人物[：:]\s*(.+)$")


def stats(path: Path, chars_per_second: float) -> dict[str, object]:
    content = path.read_text(encoding="utf-8-sig")
    body = content.split("## 本集连续性更新", 1)[0]
    dialogue_chars = 0
    dialogue_lines = 0
    speakers: Counter[str] = Counter()
    listed: Counter[str] = Counter()
    action_chars = 0
    for raw in body.splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or line.startswith("-"):
            continue
        cast = CHARACTERS.match(line)
        if cast:
            for name in re.split(r"[、,，/ ]+", cast.group(1)):
                if name:
                    listed[name] += 1
            continue
        match = DIALOGUE.match(line)
        if match:
            speaker, speech = match.groups()
            speakers[speaker.strip()] += 1
            dialogue_lines += 1
            dialogue_chars += len(re.sub(r"\s", "", speech))
        else:
            action_chars += len(re.sub(r"\s", "", line))
    estimated_seconds = round(dialogue_chars / chars_per_second + action_chars / 7.0, 1)
    return {
        "episode": path.stem,
        "scenes": len(SCENE.findall(body)),
        "dialogue_lines": dialogue_lines,
        "dialogue_chars": dialogue_chars,
        "action_chars": action_chars,
        "estimated_seconds": estimated_seconds,
        "speakers": dict(speakers.most_common()),
        "cast_mentions": dict(listed.most_common()),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path, help="Episode files or directories")
    parser.add_argument("--chars-per-second", type=float, default=4.2, help="Mandarin dialogue estimate")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    if args.chars_per_second <= 0:
        parser.error("--chars-per-second must be positive")

    files: list[Path] = []
    for item in args.inputs:
        item = item.expanduser().resolve()
        if item.is_dir():
            files.extend(p for p in item.glob("EP*.md") if re.fullmatch(r"EP\d+\.md", p.name, re.I))
        elif item.suffix.lower() == ".md":
            files.append(item)
    files = sorted(set(files))
    if not files:
        parser.error("no episode Markdown files found")
    report = [stats(path, args.chars_per_second) for path in files]

    if args.as_json:
        print(json.dumps(report, ensure_ascii=False, indent=2))
    else:
        print("| 集数 | 场次 | 台词行 | 台词字 | 动作字 | 估算时长(秒) | 说话角色 |")
        print("|---|---:|---:|---:|---:|---:|---:|")
        for row in report:
            print(f"| {row['episode']} | {row['scenes']} | {row['dialogue_lines']} | {row['dialogue_chars']} | {row['action_chars']} | {row['estimated_seconds']} | {len(row['speakers'])} |")
        print("\n> 时长为粗略统计信号，不替代朗读、表演节奏和剪辑判断。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
