#!/usr/bin/env python3
"""Validate a short-drama project skeleton, CSV schemas, and episode structure."""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

from validate_state import validate as validate_state_files


BASE_FILES = [
    ".drama/project-state.json",
    ".drama/artifact-index.json",
    ".drama/invalidation-log.jsonl",
    "00-project-brief.md",
    "04-story-bible.md",
    "05-season-architecture.md",
    "06-episode-matrix.csv",
    "continuity/canon.yaml",
    "continuity/timeline.csv",
    "continuity/character-state.csv",
    "continuity/knowledge-state.csv",
    "continuity/relationships.csv",
    "continuity/props-ledger.csv",
    "continuity/evidence.csv",
    "continuity/hooks-ledger.csv",
    "continuity/foreshadowing.csv",
    "locked-decisions.md",
    "change-log.md",
]
ADAPTATION_FILES = ["01-source-index.md", "02-source-truth.md", "03-adaptation-map.md"]
BRIEF_FILES = [
    ".drama/project-state.json", ".drama/artifact-index.json",
    ".drama/invalidation-log.jsonl", "00-project-brief.md",
    "continuity/canon.yaml", "locked-decisions.md", "change-log.md",
]
CSV_REQUIRED = {
    "06-episode-matrix.csv": {"episode", "episode_goal", "start_state", "core_conflict", "turn", "ending_drive", "end_state", "status"},
    "continuity/timeline.csv": {"event_id", "event", "location", "participants", "source_episode", "source_scene", "status"},
    "continuity/character-state.csv": {"episode", "scene", "character", "location", "physical", "emotion", "relationships", "resources", "current_goal", "status"},
    "continuity/knowledge-state.csv": {"fact_id", "character", "knowledge", "learned_episode", "source", "status"},
    "continuity/relationships.csv": {"relationship_id", "episode", "party_a", "party_b", "trust", "power", "change", "status"},
    "continuity/props-ledger.csv": {"prop_id", "prop", "current_holder", "location", "condition", "source_episode", "provenance", "status"},
    "continuity/evidence.csv": {"evidence_id", "evidence", "created_episode", "current_holder", "proves", "chain_of_custody", "status"},
    "continuity/hooks-ledger.csv": {"hook_id", "setup_episode", "type", "audience_question", "promise", "answer_owner", "resolve_by", "status"},
    "continuity/foreshadowing.csv": {"foreshadow_id", "setup", "setup_episode", "payoff_by", "status", "evidence"},
}
EPISODE_HEADERS = ["# 第", "## 本集控制信息", "## 本集连续性更新"]


def read_csv_header(path: Path) -> set[str]:
    with path.open(encoding="utf-8-sig", newline="") as handle:
        return set(next(csv.reader(handle), []))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--mode", choices=("original", "adaptation", "source_remix"), help="Defaults to project-state sourceMode")
    parser.add_argument("--stage", choices=("brief", "gate-a", "full"), default="full")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    root = args.project_dir.expanduser().resolve()
    errors: list[str] = []
    warnings: list[str] = []

    if not root.is_dir():
        parser.error(f"project directory does not exist: {root}")
    state_mode = None
    state_path = root / ".drama" / "project-state.json"
    if state_path.exists():
        try:
            state_mode = json.loads(state_path.read_text(encoding="utf-8")).get("sourceMode")
        except json.JSONDecodeError:
            pass
    mode = args.mode or state_mode or "original"
    if args.mode and state_mode and args.mode != state_mode:
        errors.append(f"--mode {args.mode} conflicts with project state {state_mode}")
    if args.stage == "brief":
        required = BRIEF_FILES
    elif args.stage == "gate-a":
        required = BRIEF_FILES + ["04-story-bible.md"]
        required += ADAPTATION_FILES if mode in {"adaptation", "source_remix"} else ["03-original-discovery.md"]
    else:
        required = BASE_FILES + (ADAPTATION_FILES if mode in {"adaptation", "source_remix"} else ["03-original-discovery.md"])
    for relative in required:
        path = root / relative
        if not path.exists():
            errors.append(f"missing required file: {relative}")
        elif path.is_file() and path.stat().st_size == 0:
            warnings.append(f"empty file: {relative}")

    for relative, expected in (CSV_REQUIRED.items() if args.stage == "full" else []):
        path = root / relative
        if not path.exists():
            continue
        actual = read_csv_header(path)
        missing = expected - actual
        if missing:
            errors.append(f"{relative}: missing columns {', '.join(sorted(missing))}")

    episode_dir = root / "episodes"
    episode_files = sorted(episode_dir.glob("EP*.md")) if episode_dir.exists() else []
    for path in episode_files:
        content = path.read_text(encoding="utf-8-sig")
        for header in EPISODE_HEADERS:
            if header not in content:
                errors.append(f"{path.relative_to(root)}: missing section starting with {header!r}")
        if not re.search(
            r"^##\s+\d+-\d+\s+(?:(?:日|夜|晨|早|午|晚|黄昏|清晨|傍晚)\s+(?:内|外|内/外|外/内)|(?:内景|外景|内/外景|外/内景))",
            content,
            re.M,
        ):
            warnings.append(f"{path.relative_to(root)}: no standard scene heading found")

    matrix = root / "06-episode-matrix.csv"
    if matrix.exists():
        with matrix.open(encoding="utf-8-sig", newline="") as handle:
            matrix_ids = {row.get("episode", "").upper() for row in csv.DictReader(handle) if row.get("episode")}
        file_ids = {path.stem.upper() for path in episode_files}
        for file_id in sorted(file_ids - matrix_ids):
            warnings.append(f"episode file {file_id} has no matrix row")

    if state_path.exists():
        state_errors, state_warnings = validate_state_files(root)
        errors.extend(f"state: {item}" for item in state_errors)
        warnings.extend(f"state: {item}" for item in state_warnings)

    issue_required = {"schemaVersion", "issueId", "severity", "category", "location", "evidence", "reason", "suggestedFix", "status", "regressionCheck"}
    for path in sorted((root / "reviews").rglob("*.json")) if (root / "reviews").exists() else []:
        try:
            issue = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            errors.append(f"{path.relative_to(root)}: invalid review issue JSON: {exc}")
            continue
        missing = issue_required - set(issue) if isinstance(issue, dict) else issue_required
        if missing:
            errors.append(f"{path.relative_to(root)}: missing review issue fields {', '.join(sorted(missing))}")
        elif issue.get("schemaVersion") != "1.0.0" or issue.get("severity") not in {"P0", "P1", "P2", "P3"}:
            errors.append(f"{path.relative_to(root)}: invalid review issue version or severity")

    result = {"project": str(root), "mode": mode, "stage": args.stage, "errors": errors, "warnings": warnings, "episode_files": len(episode_files), "valid": not errors}
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"Project: {root}")
        print(f"Result: {'PASS' if not errors else 'FAIL'}")
        for item in errors:
            print(f"ERROR: {item}")
        for item in warnings:
            print(f"WARN: {item}")
        print(f"Episode files: {len(episode_files)}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
