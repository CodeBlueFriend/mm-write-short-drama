#!/usr/bin/env python3
"""Import the pinned five-book summaries, preserving upstream and library revisions.

First import into an isolated draft library. Activation requires an explicit review
note; it is never inferred from a second --status active generic ingestion.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

from ingest_knowledge import make_card, parse_structured
from knowledge_lib import (append_jsonl, archive_and_update, ensure_layout, iter_cards,
                           normalize_text, now_iso, rebuild_index, source_record, write_new_card)
from validate_knowledge import validate_card

COMMIT = "6e99009572a64f99d60134405fbf1cf200b0dfe4"
PREFIX = "cap.mckee-story-short-drama."
INPUTS = Path(__file__).resolve().parents[1] / "assets" / "book-capability-inputs"


def read_inputs(folder: Path) -> list[tuple[Path, dict]]:
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    if manifest.get("commit") != COMMIT:
        raise ValueError("unexpected source commit; this importer is pinned to " + COMMIT)
    paths = sorted(folder.glob("first-four-*.md")) + sorted(folder.glob("story-*.md"))
    if len(paths) != 24:
        raise ValueError("expected exactly 5 first-four and 19 Story input summaries")
    for name, expected in manifest["files"].items():
        if hashlib.sha256((folder / name).read_bytes()).hexdigest() != expected:
            raise ValueError("pinned input hash mismatch: " + name)
    source_manifest = json.loads((folder / "story-source-manifest.json").read_text())
    result = []
    seen = set()
    for path in paths:
        candidate = parse_structured(path.read_text(encoding="utf-8"))
        if not candidate or not candidate.get("capability_id"):
            raise ValueError("missing structured capability: " + path.name)
        cap = candidate["capability_id"]
        if cap in seen:
            raise ValueError("duplicate upstream capability: " + cap)
        seen.add(cap)
        candidate["capability_revision"] = int(candidate.get("capability_revision", 1))
        candidate["source_commit"] = COMMIT
        candidate["import_sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
        candidate["upstream_path"] = "knowledge-inbox/" + path.name
        candidate["source_locator"] = candidate["source_note"]
        candidate["provenance_layers"] = {
            "book_principle": "source_note and source_verification identify available evidence",
            "short_drama_operations": "action, output_contract, self_check, adaptation are project adaptation",
            "examples": "positive_example and negative_example are upstream original exercises",
        }
        if cap.startswith(PREFIX):
            number = int(path.name.split("-")[1])
            expected_revision = 2 if number <= 6 else 1
            if candidate["capability_revision"] != expected_revision:
                raise ValueError("unexpected Story capability revision: " + cap)
            if candidate.get("original_source_sha256") != source_manifest["sha256"]:
                raise ValueError("Story original source hash differs from source manifest")
            candidate["original_edition"] = {key: source_manifest[key] for key in (
                "title", "author", "translator", "publisher", "edition", "isbn", "version_id")}
            candidate["original_source_commit"] = source_manifest["source_repo_commit"]
            candidate["story_number"] = number
        result.append((path, candidate))
    return result


def import_library(root: Path, inputs: Path, activate: bool = False,
                   review_note: str = "", upgrade_legacy_six: bool = False) -> dict:
    if activate and not review_note.strip():
        raise ValueError("--activate-reviewed requires --review-note describing the source/scope review")
    materials = read_inputs(inputs)
    root = ensure_layout(root)
    existing = list(iter_cards(root))
    result = {"source_commit": COMMIT, "knowledge_base": str(root), "created": [],
              "upgraded": [], "reused": [], "conflicts": [], "mapping": []}
    for path, candidate in materials:
        cap = candidate["capability_id"]
        matches = [card for card in existing if card.get("capability_id") == cap
                   and card.get("status") not in {"deprecated", "archived", "rejected", "duplicate"}]
        if len(matches) > 1:
            result["conflicts"].append({"capability_id": cap, "reason": "multiple current cards; resolve before migration"})
            continue
        old = matches[0] if matches else None
        equal = (old and old.get("import_sha256") == candidate["import_sha256"]
                 and old.get("source_commit") == COMMIT
                 and old.get("rule") == candidate["rule"]
                 and old.get("capability_revision") == candidate["capability_revision"]
                 and all(old.get(key) == candidate.get(key) for key in (
                     "action", "source_locator", "self_check", "source_note", "source_verification")))
        if equal and (not activate or old["status"] == "active"):
            result["reused"].append(old["id"])
            result["mapping"].append({"capability_id": cap, "card_id": old["id"],
                                      "capability_revision": old["capability_revision"], "action": "reused"})
            continue
        old_revision = int(old.get("capability_revision", 1)) if old else 0
        if old and old_revision > candidate["capability_revision"]:
            result["conflicts"].append({"capability_id": cap, "reason": "refusing to downgrade a newer upstream revision"})
            continue
        if old and old["status"] == "active" and not equal and not activate:
            result["conflicts"].append({"capability_id": cap,
                                        "reason": "active-card upgrade requires explicit source/scope review; existing card retained"})
            continue
        legacy = (old and candidate.get("story_number", 99) <= 6 and upgrade_legacy_six
                  and old_revision < candidate["capability_revision"])
        same_rule = old and normalize_text(old["rule"]) == normalize_text(candidate["rule"])
        if old and not (equal or legacy or same_rule):
            result["conflicts"].append({"capability_id": cap, "existing_id": old["id"],
                                        "reason": "changed rule without a recognized legacy-six upgrade; existing card retained"})
            continue
        if old and old["status"] == "pending-conflict":
            result["conflicts"].append({"capability_id": cap, "reason": "pending conflict cannot be activated by import"})
            continue
        source = source_record(root, path.name, path.read_bytes(), ".md")
        args = SimpleNamespace(**{key: None for key in (
            "category", "stage", "genre", "production_mode", "priority", "title", "rationale",
            "exceptions", "positive_example", "negative_example")}, status="active" if activate else "draft")
        card = make_card(candidate, source, args)
        for key in ("capability_revision", "source_commit", "import_sha256", "upstream_path", "source_locator",
                    "provenance_layers", "original_edition", "original_source_sha256", "original_source_commit", "story_number"):
            if key in candidate:
                card[key] = candidate[key]
        if old:
            card["id"] = old["id"]  # Card identity survives changed wording and source metadata.
            card["created_at"] = old.get("created_at", card["created_at"])
        if activate:
            card["activation_review"] = {"review_note": review_note.strip(), "reviewed_at": now_iso(),
                                         "input_sha256": candidate["import_sha256"]}
        errors, warnings = [], []
        validate_card(root, {**card, "_path": str(root / "cards" / (card["id"] + ".md"))}, errors, warnings)
        if errors:
            raise ValueError("; ".join(errors))
        action = "upgraded" if old else "created"
        if old:
            archive = archive_and_update(root, old, card)
            entry = {"card_id": card["id"], "archive": str(archive.relative_to(root))}
            result["upgraded"].append(entry)
            existing.remove(old)
        else:
            write_new_card(root, card)
            result["created"].append(card["id"])
        existing.append({**card, "_path": str(root / "cards" / (card["id"] + ".md"))})
        result["mapping"].append({"capability_id": cap, "card_id": card["id"],
                                  "capability_revision": card["capability_revision"], "action": action,
                                  "input_sha256": candidate["import_sha256"]})
    rebuild_index(root)
    result["activation_requested"] = activate
    result["valid"] = not result["conflicts"]
    if result["created"] or result["upgraded"] or result["conflicts"]:
        append_jsonl(root / "index" / "ingest-log.jsonl", {"imported_at": now_iso(), "importer": "five-books", **result})
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--kb", type=Path, required=True)
    parser.add_argument("--inputs", type=Path, default=INPUTS)
    parser.add_argument("--activate-reviewed", action="store_true")
    parser.add_argument("--review-note", default="")
    parser.add_argument("--upgrade-legacy-six", action="store_true",
                        help="Explicitly migrate the first six Story capability revision-1 cards to revision 2")
    parser.add_argument("--report", type=Path)
    args = parser.parse_args()
    try:
        result = import_library(args.kb, args.inputs, args.activate_reviewed,
                                args.review_note, args.upgrade_legacy_six)
    except (OSError, ValueError, KeyError) as exc:
        parser.error(str(exc))
    output = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(output, encoding="utf-8")
    print(output, end="")
    return 0 if result["valid"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
