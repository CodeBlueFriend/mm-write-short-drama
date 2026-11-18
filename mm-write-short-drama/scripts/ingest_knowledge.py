#!/usr/bin/env python3
"""Ingest conversation text or Markdown/TXT files into the personal knowledge base."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path
from typing import Any

from knowledge_lib import (
    PRIORITIES,
    STATUSES,
    append_jsonl,
    archive_and_update,
    classify,
    is_conflict,
    iter_cards,
    list_value,
    load_jsonl,
    make_id,
    normalize_text,
    now_iso,
    rebuild_index,
    relative_or_absolute,
    resolve_kb,
    similarity,
    source_record,
    write_new_card,
)


FIELD_MAP = {
    "来源": "source_note",
    "来源链接": "source_url",
    "仓颉能力 ID": "capability_id",
    "触发": "triggers",
    "诊断": "diagnosis",
    "动作": "action",
    "输出": "output_contract",
    "自检": "self_check",
    "短剧适配": "adaptation",
    "来源核验": "source_verification",
    "技巧名称": "title",
    "标题": "title",
    "title": "title",
    "规则": "rule",
    "rule": "rule",
    "理由": "rationale",
    "原理": "rationale",
    "rationale": "rationale",
    "分类": "category",
    "category": "category",
    "阶段": "stage",
    "stage": "stage",
    "题材": "genre",
    "genre": "genre",
    "制作形式": "production_mode",
    "production_mode": "production_mode",
    "优先级": "priority",
    "priority": "priority",
    "例外": "exceptions",
    "exceptions": "exceptions",
    "正例": "positive_example",
    "positive_example": "positive_example",
    "反例": "negative_example",
    "negative_example": "negative_example",
}


def parse_structured(block: str) -> dict[str, Any] | None:
    result: dict[str, Any] = {}
    for line in block.splitlines():
        match = re.match(r"^\s*([^：:]{1,24})[：:]\s*(.*?)\s*$", line)
        if not match:
            continue
        key = FIELD_MAP.get(match.group(1).strip().lower()) or FIELD_MAP.get(match.group(1).strip())
        if key:
            result[key] = match.group(2).strip()
    return result if result.get("rule") else None


def extract_candidates(text: str) -> list[dict[str, Any]]:
    text = text.replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        return []
    blocks = [part.strip() for part in re.split(r"\n\s*---+\s*\n", text) if part.strip()]
    structured = [parse_structured(block) for block in blocks]
    parsed = [item for item in structured if item]
    if parsed and len(parsed) == len(blocks):
        return parsed

    bullets = []
    for line in text.splitlines():
        match = re.match(r"^\s*(?:[-*+]\s+|\d+[.)、]\s*)(.+?)\s*$", line)
        if match and len(match.group(1).strip()) >= 8:
            bullets.append({"rule": match.group(1).strip()})
    if bullets:
        return bullets

    paragraphs = [
        re.sub(r"^#{1,6}\s*", "", part.strip())
        for part in re.split(r"\n\s*\n+", text)
        if part.strip() and not part.strip().startswith("# ")
    ]
    prescriptive = ("必须", "应该", "应当", "需要", "不能", "不得", "不要", "避免", "优先", "建议", "最好", "可以")
    selected = [part for part in paragraphs if len(part) >= 8 and any(word in part for word in prescriptive)]
    if selected:
        return [{"rule": part} for part in selected]
    return [{"rule": text}]


def collect_files(inputs: list[Path], inbox: Path | None) -> list[Path]:
    found: list[Path] = []
    items = list(inputs)
    if inbox:
        items.append(inbox)
    for item in items:
        item = item.expanduser().resolve()
        if item.is_dir():
            found.extend(
                path
                for path in item.rglob("*")
                if path.is_file()
                and path.suffix.lower() in {".md", ".txt"}
                and path.name.lower() not in {"readme.md", "card-template.md"}
                and not path.name.startswith(".")
            )
        elif item.is_file() and item.suffix.lower() in {".md", ".txt"}:
            found.append(item)
        else:
            raise ValueError(f"unsupported or missing input: {item}")
    return sorted(set(found))


def title_from_rule(rule: str) -> str:
    compact = re.sub(r"\s+", " ", rule).strip("。；;，, ")
    return compact if len(compact) <= 28 else compact[:27] + "…"


def make_card(candidate: dict[str, Any], source: dict[str, str], args: argparse.Namespace) -> dict[str, Any]:
    rule = str(candidate["rule"]).strip()
    if not rule:
        raise ValueError("atomic rule cannot be empty")
    auto_category, auto_stage, auto_production = classify(rule)
    category = str(args.category or candidate.get("category") or auto_category)
    stage = list_value(args.stage or candidate.get("stage") or auto_stage)
    genre = list_value(args.genre or candidate.get("genre"))
    production = list_value(args.production_mode or candidate.get("production_mode") or auto_production)
    priority = str(args.priority or candidate.get("priority") or "experimental")
    status = str(args.status)
    card_id = make_id(category, rule)
    return {
        "id": card_id,
        "title": str(args.title or candidate.get("title") or title_from_rule(rule)),
        "rule": rule,
        "rationale": str(args.rationale or candidate.get("rationale") or "待补充：请在激活前说明该规则为何有效。"),
        "category": category,
        "stage": stage,
        "genre": genre,
        "production_mode": production,
        "priority": priority,
        "exceptions": list_value(args.exceptions or candidate.get("exceptions"), default="") if (args.exceptions or candidate.get("exceptions")) else [],
        "positive_example": str(args.positive_example or candidate.get("positive_example") or ""),
        "negative_example": str(args.negative_example or candidate.get("negative_example") or ""),
        "source": source,
        **{key: candidate[key] for key in (
            "source_note", "source_url", "capability_id", "triggers", "diagnosis",
            "action", "output_contract", "self_check", "adaptation", "source_verification"
        ) if candidate.get(key)},
        "status": status,
        "version": 1,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def resolve_conflict(root: Path, conflict_id: str, decision: str, note: str) -> int:
    conflicts = load_jsonl(root / "conflicts" / "open.jsonl")
    resolutions = load_jsonl(root / "conflicts" / "resolutions.jsonl")
    if any(item.get("conflict_id") == conflict_id for item in resolutions):
        raise ValueError(f"conflict already resolved: {conflict_id}")
    conflict = next((item for item in conflicts if item.get("conflict_id") == conflict_id), None)
    if not conflict:
        raise ValueError(f"conflict not found: {conflict_id}")
    cards = {card["id"]: card for card in iter_cards(root)}
    new_card = cards.get(conflict["new_rule_id"])
    if not new_card:
        raise ValueError(f"new card missing: {conflict['new_rule_id']}")
    existing = [cards[item] for item in conflict.get("existing_rule_ids", []) if item in cards]
    archives = []
    if decision == "keep-existing":
        archives.append(str(archive_and_update(root, new_card, {"status": "rejected"})))
    elif decision == "activate-new":
        for card in existing:
            if card.get("status") not in {"deprecated", "archived", "rejected"}:
                archives.append(str(archive_and_update(root, card, {"status": "deprecated"})))
        archives.append(str(archive_and_update(root, new_card, {"status": "active"})))
    elif decision == "keep-both":
        if not note.strip():
            raise ValueError("--note is required for keep-both and must explain separated scopes")
        archives.append(str(archive_and_update(root, new_card, {"status": "active"})))
    else:
        raise ValueError(f"unsupported decision: {decision}")
    append_jsonl(
        root / "conflicts" / "resolutions.jsonl",
        {
            "conflict_id": conflict_id,
            "decision": decision,
            "note": note,
            "resolved_at": now_iso(),
            "affected_rule_ids": [new_card["id"], *[item["id"] for item in existing]],
            "archives": archives,
        },
    )
    rebuild_index(root)
    print(f"Resolved {conflict_id}: {decision}")
    return 0


def ingest(args: argparse.Namespace) -> int:
    root = resolve_kb(args.kb)
    inputs = collect_files(args.inputs, root / "inbox" if args.all_inbox else None)
    if not inputs and args.text is None:
        raise ValueError("provide --text, input files/directories, or --all-inbox")

    materials: list[tuple[str, bytes, str, bool]] = []
    if args.text is not None:
        materials.append((args.source_name or "codex-conversation.md", args.text.encode("utf-8"), ".md", True))
    for path in inputs:
        materials.append((path.name, path.read_bytes(), path.suffix.lower(), False))

    existing = list(iter_cards(root))
    created: list[str] = []
    duplicate_count = 0
    conflict_count = 0
    source_ids: list[str] = []
    for original_name, content, suffix, is_direct in materials:
        source = source_record(root, original_name, content, suffix)
        source_ids.append(source["source_id"])
        text = content.decode("utf-8-sig")
        candidates = [{"rule": args.rule}] if is_direct and args.rule else extract_candidates(text)
        for candidate in candidates:
            card = make_card(candidate, source, args)
            duplicates = [
                item
                for item in existing
                if normalize_text(str(item.get("rule", ""))) == normalize_text(card["rule"])
                or similarity(str(item.get("rule", "")), card["rule"]) >= args.duplicate_threshold
            ]
            if duplicates:
                duplicate_count += 1
                append_jsonl(
                    root / "conflicts" / "duplicates.jsonl",
                    {
                        "detected_at": now_iso(),
                        "candidate_id": card["id"],
                        "candidate_rule": card["rule"],
                        "existing_rule_ids": [item["id"] for item in duplicates],
                        "source": source,
                        "action": "skipped-without-overwrite",
                    },
                )
                continue

            conflicts = []
            for item in existing:
                if item.get("status") in {"rejected", "deprecated", "archived", "duplicate"}:
                    continue
                detected, score, reason = is_conflict(card, item)
                if detected:
                    conflicts.append({"id": item["id"], "score": round(score, 4), "reason": reason})
            if conflicts:
                card["status"] = "pending-conflict"
            write_new_card(root, card)
            created.append(card["id"])
            existing.append({**card, "_path": str(root / "cards" / f"{card['id']}.md")})
            if conflicts:
                conflict_count += 1
                conflict_id = "KBC-" + hashlib.sha256(
                    (card["id"] + "|" + "|".join(item["id"] for item in conflicts)).encode("utf-8")
                ).hexdigest()[:12].upper()
                append_jsonl(
                    root / "conflicts" / "open.jsonl",
                    {
                        "conflict_id": conflict_id,
                        "detected_at": now_iso(),
                        "new_rule_id": card["id"],
                        "existing_rule_ids": [item["id"] for item in conflicts],
                        "evidence": conflicts,
                        "status": "awaiting-user-decision",
                    },
                )

    card_count, term_count = rebuild_index(root)
    append_jsonl(
        root / "index" / "ingest-log.jsonl",
        {
            "ingested_at": now_iso(),
            "materials_processed": len(materials),
            "source_ids": sorted(set(source_ids)),
            "created_rule_ids": created,
            "duplicates": duplicate_count,
            "conflicts": conflict_count,
            "requested_status": args.status,
        },
    )
    print(
        json.dumps(
            {
                "materials_processed": len(materials),
                "unique_source_contents": len(set(source_ids)),
                "created": created,
                "duplicates": duplicate_count,
                "conflicts": conflict_count,
                "indexed_cards": card_count,
                "index_terms": term_count,
                "knowledge_base": relative_or_absolute(root, Path.cwd()),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("inputs", nargs="*", type=Path, help="Markdown/TXT files or directories")
    parser.add_argument("--kb", type=Path, help="Knowledge-base root; defaults to ./knowledge-base discovered upward")
    parser.add_argument("--text", help="Direct conversation text to preserve and ingest")
    parser.add_argument("--rule", help="Atomic rule extracted from --text while preserving the full original text")
    parser.add_argument("--source-name", help="Original label for --text, for example lesson-12.md")
    parser.add_argument("--all-inbox", action="store_true", help="Batch process knowledge-base/inbox without deleting files")
    parser.add_argument("--title")
    parser.add_argument("--rationale")
    parser.add_argument("--category")
    parser.add_argument("--stage", help="Comma-separated stage scope")
    parser.add_argument("--genre", help="Comma-separated genre scope")
    parser.add_argument("--production-mode", help="Comma-separated production scope")
    parser.add_argument("--priority", choices=sorted(PRIORITIES))
    parser.add_argument("--exceptions", help="Comma-separated exception conditions")
    parser.add_argument("--positive-example")
    parser.add_argument("--negative-example")
    parser.add_argument("--status", choices=sorted(STATUSES), default="draft")
    parser.add_argument("--duplicate-threshold", type=float, default=0.92)
    parser.add_argument("--resolve", metavar="CONFLICT_ID", help="Resolve a logged conflict instead of ingesting")
    parser.add_argument("--decision", choices=("keep-existing", "activate-new", "keep-both"))
    parser.add_argument("--note", default="")
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if not 0.5 <= args.duplicate_threshold <= 1.0:
        parser.error("--duplicate-threshold must be between 0.5 and 1.0")
    try:
        if args.resolve:
            if not args.decision:
                parser.error("--decision is required with --resolve")
            return resolve_conflict(resolve_kb(args.kb), args.resolve, args.decision, args.note)
        if args.rule and (args.text is None or args.inputs or args.all_inbox):
            parser.error("--rule is only valid with one direct --text input")
        return ingest(args)
    except (FileNotFoundError, FileExistsError, UnicodeDecodeError, ValueError, RuntimeError) as exc:
        parser.error(str(exc))
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
