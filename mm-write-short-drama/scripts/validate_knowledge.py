#!/usr/bin/env python3
"""Validate knowledge-base layout, cards, sources, indexes, and conflict state."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any

from knowledge_lib import (
    PRIORITIES,
    PRODUCTION_MODES,
    REQUIRED_FIELDS,
    STAGES,
    STATUSES,
    iter_cards,
    list_value,
    load_jsonl,
    normalize_text,
    rebuild_index,
    resolve_kb,
)


def source_path(root: Path, value: str) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else root.parent / path


def validate_card(root: Path, card: dict[str, Any], errors: list[str], warnings: list[str]) -> None:
    label = str(card.get("_path", "unknown card"))
    missing = [field for field in REQUIRED_FIELDS if field not in card]
    if missing:
        errors.append(f"{label}: missing fields {', '.join(missing)}")
        return
    if Path(label).stem != str(card["id"]):
        errors.append(f"{label}: filename must equal id {card['id']}.md")
    for field in ("id", "title", "rule", "rationale", "category", "positive_example", "negative_example", "status", "priority"):
        if not isinstance(card[field], str):
            errors.append(f"{label}: {field} must be a string")
    for field in ("id", "title", "rule", "rationale", "category", "status", "priority"):
        if isinstance(card[field], str) and not card[field].strip():
            errors.append(f"{label}: {field} cannot be empty")
    for field in ("stage", "genre", "production_mode", "exceptions"):
        if not isinstance(card[field], list) or not all(isinstance(item, str) for item in card[field]):
            errors.append(f"{label}: {field} must be a list of strings")
    for field in ("stage", "genre", "production_mode"):
        if isinstance(card[field], list) and not card[field]:
            errors.append(f"{label}: {field} cannot be empty")
    if card.get("priority") not in PRIORITIES:
        errors.append(f"{label}: invalid priority {card.get('priority')}")
    if card.get("status") not in STATUSES:
        errors.append(f"{label}: invalid status {card.get('status')}")
    invalid_stages = set(list_value(card.get("stage"))) - STAGES
    if invalid_stages:
        errors.append(f"{label}: invalid stages {', '.join(sorted(invalid_stages))}")
    invalid_modes = set(list_value(card.get("production_mode"))) - PRODUCTION_MODES
    if invalid_modes:
        errors.append(f"{label}: invalid production modes {', '.join(sorted(invalid_modes))}")
    if not isinstance(card.get("version"), int) or int(card.get("version", 0)) < 1:
        errors.append(f"{label}: version must be a positive integer")
    source = card.get("source")
    if not isinstance(source, dict):
        errors.append(f"{label}: source must be an object")
    else:
        required_source = {"source_id", "stored_path", "original_name", "sha256", "captured_at"}
        absent = required_source - set(source)
        if absent:
            errors.append(f"{label}: source missing {', '.join(sorted(absent))}")
        elif source.get("stored_path"):
            path = source_path(root, str(source["stored_path"]))
            if not path.is_file():
                errors.append(f"{label}: immutable source missing: {path}")
            else:
                digest = hashlib.sha256(path.read_bytes()).hexdigest()
                if digest != source.get("sha256"):
                    errors.append(f"{label}: source hash changed: {path}")
    if card.get("status") == "active":
        if card.get("capability_id"):
            for field in ("source_note", "source_url", "source_verification", "triggers",
                          "diagnosis", "action", "output_contract", "self_check", "adaptation"):
                if not isinstance(card.get(field), str) or not card[field].strip():
                    errors.append(f"{label}: active capability card requires {field}")
        if str(card.get("rationale", "")).startswith("待补充"):
            warnings.append(f"{label}: active card still has placeholder rationale")
        if not card.get("positive_example") or not card.get("negative_example"):
            warnings.append(f"{label}: active card should include positive and negative examples")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb", type=Path, help="Knowledge-base root")
    parser.add_argument("--json", action="store_true", dest="as_json")
    parser.add_argument("--fix-index", action="store_true", help="Rebuild index after validation")
    args = parser.parse_args()
    errors: list[str] = []
    warnings: list[str] = []
    try:
        root = resolve_kb(args.kb)
    except FileNotFoundError as exc:
        parser.error(str(exc))

    for name in ("inbox", "sources", "cards", "index", "conflicts", "archive"):
        if not (root / name).is_dir():
            errors.append(f"missing directory: {name}")

    cards: list[dict[str, Any]] = []
    try:
        cards = list(iter_cards(root))
    except (ValueError, json.JSONDecodeError) as exc:
        errors.append(str(exc))
    ids: dict[str, str] = {}
    rules: dict[str, str] = {}
    for card in cards:
        validate_card(root, card, errors, warnings)
        card_id = str(card.get("id", ""))
        if card_id in ids:
            errors.append(f"duplicate card id {card_id}: {ids[card_id]} and {card.get('_path')}")
        ids[card_id] = str(card.get("_path"))
        normalized = normalize_text(str(card.get("rule", "")))
        if normalized and normalized in rules:
            errors.append(f"duplicate normalized rule in {rules[normalized]} and {card_id}")
        rules[normalized] = card_id

    logs: dict[str, list[dict[str, Any]]] = {}
    for relative in (
        "index/cards.jsonl",
        "index/terms.jsonl",
        "index/ingest-log.jsonl",
        "conflicts/open.jsonl",
        "conflicts/duplicates.jsonl",
        "conflicts/resolutions.jsonl",
    ):
        try:
            logs[relative] = load_jsonl(root / relative)
        except ValueError as exc:
            errors.append(str(exc))
            logs[relative] = []

    indexed = {str(item.get("id")): item for item in logs["index/cards.jsonl"]}
    indexed_ids = set(indexed)
    stale_index = indexed_ids != set(ids)
    for card in cards:
        item = indexed.get(str(card.get("id")))
        if not item:
            continue
        for field in ("rule", "category", "stage", "genre", "production_mode", "priority", "status", "version", "updated_at"):
            if item.get(field) != card.get(field):
                stale_index = True
                break
    if stale_index:
        if not args.fix_index:
            errors.append("index/cards.jsonl is stale; rerun with --fix-index")

    resolution_ids = {item.get("conflict_id") for item in logs["conflicts/resolutions.jsonl"]}
    for conflict in logs["conflicts/open.jsonl"]:
        conflict_id = conflict.get("conflict_id")
        new_id = conflict.get("new_rule_id")
        if new_id not in ids:
            errors.append(f"{conflict_id}: new rule missing: {new_id}")
        for existing in conflict.get("existing_rule_ids", []):
            if existing not in ids:
                errors.append(f"{conflict_id}: existing rule missing: {existing}")
        if conflict_id not in resolution_ids:
            card = next((item for item in cards if item.get("id") == new_id), None)
            if card and card.get("status") != "pending-conflict":
                errors.append(f"{conflict_id}: unresolved new card must remain pending-conflict")

    if args.fix_index and not errors:
        count, terms = rebuild_index(root)
    else:
        count = len(logs["index/cards.jsonl"])
        terms = len(logs["index/terms.jsonl"])
    result = {
        "knowledge_base": str(root),
        "valid": not errors,
        "cards": len(cards),
        "active_cards": sum(1 for card in cards if card.get("status") == "active"),
        "unresolved_conflicts": sum(1 for item in logs["conflicts/open.jsonl"] if item.get("conflict_id") not in resolution_ids),
        "index_cards": count,
        "index_terms": terms,
        "errors": errors,
        "warnings": warnings,
    }
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Knowledge base: {root}")
        print(f"Result: {'PASS' if not errors else 'FAIL'}")
        print(f"Cards: {result['cards']} (active: {result['active_cards']})")
        print(f"Unresolved conflicts: {result['unresolved_conflicts']}")
        for item in errors:
            print(f"ERROR: {item}")
        for item in warnings:
            print(f"WARN: {item}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
