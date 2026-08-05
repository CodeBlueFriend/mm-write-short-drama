#!/usr/bin/env python3
"""Index Markdown or text source material into stable, line-addressable sections."""

from __future__ import annotations

import argparse
import hashlib
import re
from dataclasses import dataclass
from pathlib import Path


HEADING = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
CHAPTER = re.compile(r"^\s*(第[一二三四五六七八九十百千万零〇0-9]+[章节回卷部].*?)\s*$")


@dataclass
class Section:
    source: Path
    title: str
    start: int
    end: int
    chars: int
    digest: str


def source_files(inputs: list[Path]) -> list[Path]:
    result: list[Path] = []
    for item in inputs:
        item = item.expanduser().resolve()
        if item.is_dir():
            result.extend(p for p in item.rglob("*") if p.suffix.lower() in {".md", ".txt"})
        elif item.suffix.lower() in {".md", ".txt"}:
            result.append(item)
        else:
            raise ValueError(f"Unsupported source: {item}")
    return sorted(set(result))


def split_file(path: Path, chunk_lines: int) -> list[Section]:
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    starts: list[tuple[int, str]] = []
    for index, line in enumerate(lines, 1):
        heading = HEADING.match(line)
        chapter = CHAPTER.match(line)
        if heading:
            starts.append((index, heading.group(2)))
        elif chapter:
            starts.append((index, chapter.group(1)))
    if not starts:
        starts = [(line, f"文本块 {number}") for number, line in enumerate(range(1, max(len(lines), 1) + 1, chunk_lines), 1)]
    elif starts[0][0] != 1:
        starts.insert(0, (1, "开篇/标题前内容"))

    sections: list[Section] = []
    for idx, (start, title) in enumerate(starts):
        end = (starts[idx + 1][0] - 1) if idx + 1 < len(starts) else max(len(lines), 1)
        text = "\n".join(lines[start - 1 : end])
        digest = hashlib.sha256(text.encode("utf-8")).hexdigest()[:12]
        sections.append(Section(path, title, start, end, len(text), digest))
    return sections


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--chunk-lines", type=int, default=200, help="Fallback size when no headings exist")
    args = parser.parse_args()
    if args.chunk_lines < 20:
        parser.error("--chunk-lines must be at least 20")

    try:
        files = source_files(args.inputs)
    except ValueError as exc:
        parser.error(str(exc))
    if not files:
        parser.error("no .md or .txt sources found")

    base = Path.cwd().resolve()
    rows = ["# 原著索引", "", "| Source ID | 文件 | 标题/章节 | 行号 | 字符数 | SHA-256 |", "|---|---|---|---:|---:|---|" ]
    counter = 1
    for path in files:
        try:
            display = path.relative_to(base)
        except ValueError:
            display = path
        for section in split_file(path, args.chunk_lines):
            title = section.title.replace("|", "\\|")
            rows.append(f"| SRC-{counter:04d} | `{display}` | {title} | {section.start}-{section.end} | {section.chars} | `{section.digest}` |")
            counter += 1

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text("\n".join(rows) + "\n", encoding="utf-8")
    print(f"Indexed {len(files)} file(s), {counter - 1} section(s): {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
