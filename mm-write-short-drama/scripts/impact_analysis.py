#!/usr/bin/env python3
"""Report artifact dependency impact; mark dependents stale only with approval."""

from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path


def load(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def save(path: Path, value: dict) -> None:
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def resolve_changed(values: list[str], artifacts: dict) -> set[str]:
    by_key = {key: item["path"] for key, item in artifacts.items()}
    known_paths = set(by_key.values())
    changed: set[str] = set()
    for value in values:
        normalized = value.replace("\\", "/").lstrip("./")
        if value in by_key:
            changed.add(by_key[value])
        elif normalized in known_paths:
            changed.add(normalized)
        else:
            raise ValueError(f"changed artifact is not indexed: {value}")
    return changed


def calculate(changed: set[str], artifacts: dict) -> tuple[set[str], set[str]]:
    reverse: dict[str, set[str]] = {}
    for item in artifacts.values():
        for dependency in item.get("dependsOn", []):
            reverse.setdefault(dependency, set()).add(item["path"])
    direct = set().union(*(reverse.get(path, set()) for path in changed))
    all_impacted = set(direct)
    frontier = set(direct)
    while frontier:
        next_frontier = set().union(*(reverse.get(path, set()) for path in frontier)) - all_impacted
        all_impacted.update(next_frontier)
        frontier = next_frontier
    return direct, all_impacted - direct


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--changed", action="append", required=True, help="Indexed artifact key or relative path; repeat as needed")
    parser.add_argument("--apply", action="store_true", help="Mark impacted artifacts stale and append the invalidation log")
    parser.add_argument("--approved-by", help="Required with --apply; records who authorized invalidation")
    parser.add_argument("--reason", help="Required with --apply")
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    if args.apply and (not args.approved_by or not args.reason):
        parser.error("--apply requires --approved-by and --reason")

    root = args.project_dir.expanduser().resolve()
    index_path = root / ".drama" / "artifact-index.json"
    state_path = root / ".drama" / "project-state.json"
    if not index_path.exists() or not state_path.exists():
        parser.error("missing .drama project state; migrate or initialize the project first")
    index = load(index_path)
    state = load(state_path)
    artifacts = index.get("artifacts", {})
    try:
        changed = resolve_changed(args.changed, artifacts)
    except ValueError as exc:
        parser.error(str(exc))
    direct, indirect = calculate(changed, artifacts)
    impacted = direct | indirect
    affected_episodes = sorted(
        f"EP{number}"
        for number, episode in state.get("episodes", {}).items()
        if episode.get("status") != "not_started"
        and (
            bool({"source-evidence.json", "03-story-treatment.md", "04-story-bible.md", "05-season-architecture.md"} & changed)
            or "06-episode-matrix.csv" in changed
            or any(path.startswith(f"episodes/EP{number}") or path.startswith(f"episodes/ep{number}") for path in changed)
        )
    )
    validators = sorted({validator for item in artifacts.values() if item.get("path") in impacted for validator in item.get("validators", [])})

    event_id = f"INV-{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
    if args.apply:
        by_path = {item["path"]: (key, item) for key, item in artifacts.items()}
        for path in impacted:
            key, item = by_path[path]
            item["status"] = "stale"
            if key in state.get("artifacts", {}):
                state["artifacts"][key]["status"] = "stale"
        for label in affected_episodes:
            state["episodes"][label[2:]]["status"] = "stale"
        revision = max(index.get("projectRevision", 1), state.get("projectRevision", 1)) + 1
        index["projectRevision"] = revision
        state["projectRevision"] = revision
        save(index_path, index)
        save(state_path, state)
        workflow_path = root / ".drama/workflow.json"
        if workflow_path.exists() and {"source-evidence.json", "03-story-treatment.md", "04-story-bible.md", "05-season-architecture.md"} & changed:
            workflow = load(workflow_path)
            workflow["outlineConfirmation"] = None
            workflow["phase"] = "outline_revision"
            save(workflow_path, workflow)
        event = {
            "schemaVersion": "1.0.0", "eventId": event_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "changed": sorted(changed), "direct": sorted(direct),
            "indirect": sorted(indirect), "episodes": affected_episodes, "applied": True,
            "reason": f"{args.reason} (approved by {args.approved_by})"
        }
        with (root / ".drama" / "invalidation-log.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")

    result = {
        "project": str(root), "changed": sorted(changed),
        "direct": sorted(direct), "indirect": sorted(indirect),
        "episodes": affected_episodes, "validators": validators, "applied": args.apply,
    }
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print("Impact analysis" + (" (applied)" if args.apply else " (report only)"))
        for label, values in (("Changed", changed), ("Direct", direct), ("Indirect", indirect), ("Episodes", affected_episodes), ("Re-run", validators)):
            print(f"{label}: {', '.join(sorted(values)) if values else 'none'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
