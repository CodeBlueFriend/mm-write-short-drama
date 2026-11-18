#!/usr/bin/env python3
"""Advance one episode through the guarded planning and review state machine."""

from __future__ import annotations

import argparse
import json
import re
from datetime import datetime, timezone
from pathlib import Path


TRANSITIONS = {
    "not_started": {"planned"},
    "planned": {"draft"},
    "draft": {"in_review"},
    "in_review": {"revision", "approved"},
    "revision": {"in_review"},
    "approved": {"planned"},
    "stale": {"planned"},
}
PHASES = {
    "planned": "episode_planning", "draft": "episode_drafting",
    "in_review": "review", "revision": "revision", "approved": "approved",
}


def episode_number(value: str) -> str:
    match = re.fullmatch(r"(?:EP)?0*(\d+)", value, re.I)
    if not match or int(match.group(1)) < 1:
        raise argparse.ArgumentTypeError("use a positive episode number, for example EP003")
    return f"{int(match.group(1)):03d}"


def save(path: Path, value: dict) -> None:
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--episode", required=True, type=episode_number)
    parser.add_argument("--to", required=True, choices=("planned", "draft", "in_review", "revision", "approved"))
    parser.add_argument("--story-bible-revision", type=int)
    parser.add_argument("--matrix-revision", type=int)
    parser.add_argument("--blocking-issues", type=int)
    parser.add_argument("--rebuild-approved", action="store_true", help="Required to move approved work back to planned")
    args = parser.parse_args()
    if args.blocking_issues is not None and args.blocking_issues < 0:
        parser.error("--blocking-issues cannot be negative")

    path = args.project_dir.expanduser().resolve() / ".drama" / "project-state.json"
    if not path.exists():
        parser.error("missing .drama/project-state.json")
    state = json.loads(path.read_text(encoding="utf-8"))
    episodes = state.setdefault("episodes", {})
    episode = episodes.setdefault(args.episode, {
        "status": "not_started", "planRevision": 0, "scriptRevision": 0,
        "reviewRevision": 0, "basedOnStoryBibleRevision": 0,
        "basedOnMatrixRevision": 0, "openBlockingIssues": 0, "lastUpdated": None,
    })
    current = episode["status"]
    if args.to not in TRANSITIONS.get(current, set()):
        parser.error(f"invalid transition: {current} -> {args.to}")
    if current == "approved" and not args.rebuild_approved:
        parser.error("moving approved work back to planned requires --rebuild-approved after approved impact analysis")

    if args.story_bible_revision is not None:
        episode["basedOnStoryBibleRevision"] = args.story_bible_revision
    if args.matrix_revision is not None:
        episode["basedOnMatrixRevision"] = args.matrix_revision
    if args.blocking_issues is not None:
        episode["openBlockingIssues"] = args.blocking_issues
    if args.to == "approved":
        if episode["openBlockingIssues"] != 0:
            parser.error("cannot approve an episode with blocking issues")
        if not episode["basedOnStoryBibleRevision"] or not episode["basedOnMatrixRevision"]:
            parser.error("approval requires story-bible and matrix revisions")

    episode["status"] = args.to
    if args.to == "planned":
        episode["planRevision"] += 1
    elif args.to == "draft":
        episode["scriptRevision"] += 1
    elif args.to == "in_review":
        episode["reviewRevision"] += 1
    episode["lastUpdated"] = datetime.now(timezone.utc).isoformat()
    state["projectRevision"] = state.get("projectRevision", 1) + 1
    state["currentPhase"] = PHASES[args.to]
    index_path = path.parent / "artifact-index.json"
    if not index_path.exists():
        parser.error("missing .drama/artifact-index.json")
    index = json.loads(index_path.read_text(encoding="utf-8"))
    artifacts = index.setdefault("artifacts", {})
    known_paths = {item.get("path") for item in artifacts.values()}

    def upsert(key: str, artifact_path: str, dependencies: list[str], status: str) -> None:
        missing = [dependency for dependency in dependencies if dependency not in known_paths]
        if missing:
            parser.error(f"cannot register {artifact_path}; dependencies are not indexed: {', '.join(missing)}")
        old = artifacts.get(key, {})
        entry = {
            "path": artifact_path,
            "revision": old.get("revision", 0) + 1,
            "status": status,
            "dependsOn": dependencies,
            "validators": ["validate_project.py"],
            "contentHash": None,
        }
        artifacts[key] = entry
        known_paths.add(artifact_path)
        state.setdefault("artifacts", {})[key] = {
            field: entry[field] for field in ("path", "revision", "status", "dependsOn")
        }

    prefix = f"episode{args.episode}"
    plan_path = f"episodes/EP{args.episode}-plan.md"
    script_path = f"episodes/EP{args.episode}.md"
    review_path = f"reviews/EP{args.episode}-review.md"
    if args.to == "planned":
        upsert(prefix + "Plan", plan_path, ["04-story-bible.md", "06-episode-matrix.csv"], "draft")
    elif args.to == "draft":
        upsert(prefix + "Script", script_path, [plan_path, "04-story-bible.md", "06-episode-matrix.csv"], "draft")
    elif args.to == "in_review":
        upsert(prefix + "Review", review_path, [script_path], "in_review")
    elif args.to == "revision":
        for key in (prefix + "Script", prefix + "Review"):
            if key in artifacts:
                artifacts[key]["status"] = "stale" if key.endswith("Review") else "draft"
                state["artifacts"][key]["status"] = artifacts[key]["status"]
    elif args.to == "approved":
        for key in (prefix + "Script", prefix + "Review"):
            if key not in artifacts:
                parser.error(f"cannot approve; missing indexed artifact {key}")
            artifacts[key]["status"] = "approved"
            state["artifacts"][key]["status"] = "approved"

    index["projectRevision"] = state["projectRevision"]
    save(path, state)
    save(index_path, index)
    print(f"EP{args.episode}: {current} -> {args.to}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
