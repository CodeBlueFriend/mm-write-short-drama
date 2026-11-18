#!/usr/bin/env python3
"""Build a compact context pack for an episode batch from project files."""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path


def parse_range(value: str) -> tuple[int, int]:
    match = re.fullmatch(r"(?:EP)?(\d+)\s*[-:]\s*(?:EP)?(\d+)", value, re.I)
    if not match:
        raise argparse.ArgumentTypeError("use START-END, for example 6-10")
    start, end = map(int, match.groups())
    if start < 1 or end < start:
        raise argparse.ArgumentTypeError("episode range must be positive and ascending")
    return start, end


def text_section(title: str, path: Path, max_chars: int) -> str:
    if not path.exists():
        return f"## {title}\n\n> 缺失：`{path.name}`\n"
    content = path.read_text(encoding="utf-8-sig").strip()
    if len(content) > max_chars:
        content = content[:max_chars].rstrip() + "\n\n> 已截断；创作前须按需读取源文件。"
    return f"## {title}\n\n来源：`{path}`\n\n{content}\n"


def matrix_rows(path: Path, start: int, end: int) -> str:
    if not path.exists():
        return "> 缺失分集矩阵。"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        rows = []
        for row in reader:
            match = re.search(r"\d+", row.get("episode", ""))
            if match and start <= int(match.group()) <= end:
                rows.append(row)
    if not rows:
        return "> 指定范围没有分集记录。"
    headers = list(rows[0])
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in rows:
        values = [str(row.get(key, "")).replace("|", "\\|").replace("\n", " ") for key in headers]
        lines.append("| " + " | ".join(values) + " |")
    return "\n".join(lines)


def ledger_excerpt(path: Path, start: int, previous: int) -> str:
    if not path.exists():
        return f"> 缺失 `{path.name}`。"
    with path.open(encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        return "> 暂无记录。"
    kept = []
    for row in rows:
        joined = " ".join(row.values())
        numbers = [int(n) for n in re.findall(r"EP\s*0*(\d+)", joined, re.I)]
        unresolved = row.get("status", "").lower() not in {"closed", "resolved", "recovered", "已回收", "废弃"}
        if unresolved or any(number >= max(1, start - previous) for number in numbers):
            kept.append(row)
    kept = kept[-80:]
    headers = list(rows[0])
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in kept:
        lines.append("| " + " | ".join(str(row.get(key, "")).replace("|", "\\|") for key in headers) + " |")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--episodes", type=parse_range, required=True)
    parser.add_argument("-o", "--output", type=Path)
    parser.add_argument("--previous", type=int, default=2, help="Previous episodes to retain in ledgers")
    parser.add_argument("--max-file-chars", type=int, default=16000)
    args = parser.parse_args()

    root = args.project_dir.expanduser().resolve()
    if not root.is_dir():
        parser.error(f"project directory does not exist: {root}")
    start, end = args.episodes
    output = args.output or root / "context-packs" / f"EP{start:03d}-EP{end:03d}-context.md"

    parts = [f"# EP{start:03d}—EP{end:03d} 上下文包", "", "> 这是源文件的便利快照，不是新的事实源。", ""]
    for title, relative in (
        ("项目状态", ".drama/project-state.json"),
        ("当前工作流与大纲确认", ".drama/workflow.json"),
        ("产物依赖索引", ".drama/artifact-index.json"),
        ("项目启动单", "00-project-brief.md"),
        ("锁定决策", "locked-decisions.md"),
        ("来源证据", "source-evidence.json"),
        ("已审故事底稿", "03-story-treatment.md"),
        ("故事圣经", "04-story-bible.md"),
        ("整季结构", "05-season-architecture.md"),
        ("最近变更", "change-log.md"),
        ("Canon", "continuity/canon.yaml"),
    ):
        parts.append(text_section(title, root / relative, args.max_file_chars))
    parts.extend(["## 当前批次分集卡", "", matrix_rows(root / "06-episode-matrix.csv", start, end), ""])
    for name in (
        "timeline.csv", "character-state.csv", "knowledge-state.csv",
        "relationships.csv", "props-ledger.csv", "evidence.csv",
        "hooks-ledger.csv", "foreshadowing.csv",
    ):
        parts.extend([f"## {name}", "", ledger_excerpt(root / "continuity" / name, start, args.previous), ""])

    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(parts).rstrip() + "\n", encoding="utf-8")
    print(f"Wrote context pack: {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
