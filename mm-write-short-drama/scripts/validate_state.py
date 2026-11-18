#!/usr/bin/env python3
"""Validate project-state, artifact dependencies, and invalidation log syntax."""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path


SCHEMA_VERSION = "1.0.0"
SOURCE_MODES = {"original", "adaptation", "source_remix", "market_research"}
PRODUCTION_MODES = {"live_action", "ai_drama", "hybrid", "unspecified"}
ORIENTATIONS = {"vertical", "horizontal", "custom"}
DELIVERY_SCOPES = {"diagnosis", "outline", "episodes", "screenplay", "review", "revision", "knowledge", "unspecified"}
REVIEW_MODES = {"strict", "assisted", "automatic"}
ARTIFACT_STATUSES = {"draft", "in_review", "approved", "stale", "unknown"}
EPISODE_STATUSES = {"not_started", "planned", "draft", "in_review", "revision", "approved", "stale"}


def load_json(path: Path, errors: list[str]) -> dict:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        errors.append(f"{path.name}: cannot read valid JSON: {exc}")
        return {}
    if not isinstance(value, dict):
        errors.append(f"{path.name}: root must be an object")
        return {}
    return value


def find_cycle(graph: dict[str, set[str]]) -> list[str] | None:
    visiting: set[str] = set()
    visited: set[str] = set()

    def walk(node: str, trail: list[str]) -> list[str] | None:
        if node in visiting:
            return trail[trail.index(node):] + [node]
        if node in visited:
            return None
        visiting.add(node)
        for child in graph.get(node, set()):
            cycle = walk(child, trail + [child])
            if cycle:
                return cycle
        visiting.remove(node)
        visited.add(node)
        return None

    for node in graph:
        cycle = walk(node, [node])
        if cycle:
            return cycle
    return None


def validate(root: Path) -> tuple[list[str], list[str]]:
    errors: list[str] = []
    warnings: list[str] = []
    drama = root / ".drama"
    state_path = drama / "project-state.json"
    index_path = drama / "artifact-index.json"
    log_path = drama / "invalidation-log.jsonl"
    for path in (state_path, index_path, log_path):
        if not path.exists():
            errors.append(f"missing state file: {path.relative_to(root)}")
    if errors:
        return errors, warnings

    state = load_json(state_path, errors)
    index = load_json(index_path, errors)
    if not state or not index:
        return errors, warnings
    if state.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("project-state.json: unsupported schemaVersion")
    if index.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("artifact-index.json: unsupported schemaVersion")
    if state.get("sourceMode") not in SOURCE_MODES:
        errors.append("project-state.json: invalid sourceMode")
    if state.get("productionMode") not in PRODUCTION_MODES:
        errors.append("project-state.json: invalid productionMode")
    if state.get("orientation") not in ORIENTATIONS:
        errors.append("project-state.json: invalid orientation")
    if state.get("deliveryScope") not in DELIVERY_SCOPES:
        errors.append("project-state.json: invalid deliveryScope")
    if state.get("reviewMode") not in REVIEW_MODES:
        errors.append("project-state.json: invalid reviewMode")
    if not isinstance(state.get("projectRevision"), int) or state.get("projectRevision", 0) < 1:
        errors.append("project-state.json: projectRevision must be a positive integer")
    if state.get("projectRevision") != index.get("projectRevision"):
        errors.append("state and artifact index projectRevision differ")

    artifacts = index.get("artifacts")
    if not isinstance(artifacts, dict):
        errors.append("artifact-index.json: artifacts must be an object")
        artifacts = {}
    paths: dict[str, str] = {}
    for key, item in artifacts.items():
        if not isinstance(item, dict):
            errors.append(f"artifact {key}: entry must be an object")
            continue
        path = item.get("path")
        if not isinstance(path, str) or not path:
            errors.append(f"artifact {key}: missing path")
            continue
        if path in paths:
            errors.append(f"artifact path duplicated by {paths[path]} and {key}: {path}")
        paths[path] = key
        if item.get("status") not in ARTIFACT_STATUSES:
            errors.append(f"artifact {key}: invalid status")
        if not isinstance(item.get("revision"), int) or item.get("revision", -1) < 0:
            errors.append(f"artifact {key}: revision must be a non-negative integer")
        if not isinstance(item.get("dependsOn"), list):
            errors.append(f"artifact {key}: dependsOn must be a list")
        if not (root / path).exists():
            warnings.append(f"artifact file is absent: {path}")

    graph: dict[str, set[str]] = {path: set() for path in paths}
    for item in artifacts.values():
        if not isinstance(item, dict) or item.get("path") not in graph:
            continue
        for dependency in item.get("dependsOn", []):
            if dependency not in paths:
                errors.append(f"{item['path']}: dependency is not indexed: {dependency}")
            else:
                graph[item["path"]].add(dependency)
    cycle = find_cycle(graph)
    if cycle:
        errors.append("artifact dependency cycle: " + " -> ".join(cycle))

    state_artifacts = state.get("artifacts", {})
    if not isinstance(state_artifacts, dict):
        errors.append("project-state.json: artifacts must be an object")
    else:
        for key, item in artifacts.items():
            state_item = state_artifacts.get(key)
            if not isinstance(state_item, dict):
                errors.append(f"project-state.json: missing artifact {key}")
            elif any(state_item.get(field) != item.get(field) for field in ("path", "revision", "status", "dependsOn")):
                errors.append(f"project-state.json: artifact {key} is out of sync with index")

    episodes = state.get("episodes")
    if not isinstance(episodes, dict):
        errors.append("project-state.json: episodes must be an object")
        episodes = {}
    for number, episode in episodes.items():
        if not re.fullmatch(r"\d{3}", number):
            errors.append(f"episode key must be three digits: {number}")
        if not isinstance(episode, dict) or episode.get("status") not in EPISODE_STATUSES:
            errors.append(f"episode {number}: invalid state")
            continue
        for field in ("planRevision", "scriptRevision", "reviewRevision", "basedOnStoryBibleRevision", "basedOnMatrixRevision", "openBlockingIssues"):
            if not isinstance(episode.get(field), int) or episode.get(field, -1) < 0:
                errors.append(f"episode {number}: {field} must be a non-negative integer")
        if episode.get("status") == "approved":
            if episode.get("openBlockingIssues") != 0:
                errors.append(f"episode {number}: approved with blocking issues")
            if not episode.get("basedOnStoryBibleRevision") or not episode.get("basedOnMatrixRevision"):
                errors.append(f"episode {number}: approved without upstream revisions")
            from workflow_lib import validate_episode_review
            for error in validate_episode_review(root, number):
                errors.append(f"episode {number}: {error}")
            for key, field in (("storyBible", "basedOnStoryBibleRevision"), ("episodeMatrix", "basedOnMatrixRevision")):
                if artifacts.get(key, {}).get("revision") != episode.get(field):
                    errors.append(f"episode {number}: obsolete {key} revision")

    for line_number, line in enumerate(log_path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            event = json.loads(line)
        except json.JSONDecodeError as exc:
            errors.append(f"invalidation-log.jsonl line {line_number}: {exc}")
            continue
        if event.get("schemaVersion") != SCHEMA_VERSION:
            errors.append(f"invalidation-log.jsonl line {line_number}: unsupported schemaVersion")
    return errors, warnings


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    parser.add_argument("--json", action="store_true", dest="as_json")
    args = parser.parse_args()
    root = args.project_dir.expanduser().resolve()
    if not root.is_dir():
        parser.error(f"project directory does not exist: {root}")
    errors, warnings = validate(root)
    result = {"project": str(root), "valid": not errors, "errors": errors, "warnings": warnings}
    if args.as_json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        print(f"State: {'PASS' if not errors else 'FAIL'}")
        for item in errors:
            print(f"ERROR: {item}")
        for item in warnings:
            print(f"WARN: {item}")
    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
