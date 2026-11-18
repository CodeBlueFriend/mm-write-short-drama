#!/usr/bin/env python3
"""Search only task-relevant, approved personal screenwriting knowledge cards."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from knowledge_lib import list_value, load_jsonl, rebuild_index, resolve_kb, tokenize


PRIORITY_SCORE = {"hard": 4.0, "preferred": 3.0, "optional": 2.0, "experimental": 1.0}


def scope_matches(card: dict[str, Any], key: str, requested: str | None) -> bool:
    if not requested:
        return True
    card_values = set(list_value(card.get(key)))
    requested_values = set(list_value(requested))
    return "all" in card_values or bool(card_values.intersection(requested_values))


def score_card(card: dict[str, Any], query: str) -> float:
    score = PRIORITY_SCORE.get(str(card.get("priority")), 0.0)
    if not query.strip():
        return score
    query_lower = query.lower()
    rule = str(card.get("rule", ""))
    title = str(card.get("title", ""))
    category = str(card.get("category", ""))
    if query_lower in rule.lower():
        score += 8
    if query_lower in title.lower():
        score += 6
    if query_lower in category.lower():
        score += 4
    query_terms = tokenize(query)
    card_terms = set(card.get("search_terms") or tokenize(" ".join((rule, title, category))))
    if query_terms:
        score += 10 * len(query_terms & card_terms) / len(query_terms)
    return score


def markdown_table(cards: list[dict[str, Any]]) -> str:
    lines = [
        "| ID | 标题 | 阶段 | 题材 | 制作 | 优先级 | 规则 |",
        "|---|---|---|---|---|---|---|",
    ]
    for card in cards:
        values = (
            card.get("id", ""),
            card.get("title", ""),
            ", ".join(list_value(card.get("stage"))),
            ", ".join(list_value(card.get("genre"))),
            ", ".join(list_value(card.get("production_mode"))),
            card.get("priority", ""),
            card.get("rule", ""),
        )
        lines.append("| " + " | ".join(str(value).replace("|", "\\|").replace("\n", " ") for value in values) + " |")
    return "\n".join(lines)


def context_block(cards: list[dict[str, Any]]) -> str:
    lines = ["## 本任务检索到的个人编剧规则", ""]
    if not cards:
        lines.append("> 没有匹配且可应用的 active 规则。")
        return "\n".join(lines)
    for card in cards:
        exceptions = card.get("exceptions") or []
        rule = str(card.get("rule", "")).rstrip("。；;，, ")
        suffix = f"；例外：{'、'.join(str(item) for item in exceptions)}" if exceptions else ""
        lines.append(f"- **{card['id']}** [{card.get('priority', '')}] {rule}{suffix}。")
        for key, label in (("capability_id", "原能力"), ("source_note", "来源范围"),
                           ("source_url", "来源链接"), ("source_verification", "核验"),
                           ("triggers", "触发"), ("diagnosis", "诊断"), ("action", "动作"),
                           ("output_contract", "输出"), ("self_check", "自检"),
                           ("adaptation", "适配")):
            if card.get(key):
                lines.append(f"  - {label}：{card[key]}")
    lines.extend(
        [
            "",
            "> 应用顺序：当前项目明确要求与锁定事实优先；未列出的规则不要为本任务额外加载。",
            "",
            "实际使用后，在审核报告记录：`使用的知识规则 ID：...`。",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query", nargs="?", default="", help="Keywords or task description")
    parser.add_argument("--kb", type=Path, help="Knowledge-base root")
    parser.add_argument("--stage", help="planning/structure/episode/scene/dialogue/review/adaptation")
    parser.add_argument("--category")
    parser.add_argument("--capability", help="Exact original capability ID; other filters still apply")
    parser.add_argument("--genre")
    parser.add_argument("--production-mode")
    parser.add_argument("--status", default="active", help="Comma-separated statuses; defaults to active only")
    parser.add_argument("--limit", type=int, default=10)
    parser.add_argument("--format", choices=("table", "json", "context", "ids"), default="table")
    parser.add_argument("--rebuild", action="store_true", help="Rebuild deterministic indexes before searching")
    args = parser.parse_args()
    if args.limit < 1:
        parser.error("--limit must be positive")
    try:
        root = resolve_kb(args.kb)
        if args.rebuild or not (root / "index" / "cards.jsonl").exists():
            rebuild_index(root)
        cards = load_jsonl(root / "index" / "cards.jsonl")
    except (FileNotFoundError, ValueError) as exc:
        parser.error(str(exc))

    statuses = set(list_value(args.status, default="active"))
    selected = []
    for card in cards:
        if card.get("status") not in statuses:
            continue
        if args.capability and card.get("capability_id") != args.capability:
            continue
        if args.category and str(card.get("category")) != args.category:
            continue
        if not scope_matches(card, "stage", args.stage):
            continue
        if not scope_matches(card, "genre", args.genre):
            continue
        if not scope_matches(card, "production_mode", args.production_mode):
            continue
        relevance = score_card(card, args.query)
        if args.query and relevance <= PRIORITY_SCORE.get(str(card.get("priority")), 0.0):
            continue
        selected.append({**card, "_score": round(relevance, 4)})
    selected.sort(key=lambda item: (-float(item["_score"]), str(item.get("id"))))
    selected = selected[: args.limit]

    if args.format == "json":
        print(json.dumps(selected, ensure_ascii=False, indent=2))
    elif args.format == "context":
        print(context_block(selected))
    elif args.format == "ids":
        print("\n".join(str(card["id"]) for card in selected))
    else:
        print(markdown_table(selected))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
