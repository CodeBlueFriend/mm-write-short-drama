#!/usr/bin/env python3
"""Create a versioned short-drama project skeleton without overwriting files."""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
from pathlib import Path

from production_specs import PLAN, SPECS, SOURCE_MODES, apply_choices, empty_plan, empty_specs, empty_source


CSV_HEADERS = {
    "timeline.csv": "event_id,date,start_time,end_time,event,location,participants,duration,source_episode,source_scene,depends_on,status\n",
    "character-state.csv": "episode,scene,character,location,physical,emotion,relationships,resources,current_goal,wardrobe,source,status\n",
    "knowledge-state.csv": "fact_id,character,knowledge,learned_episode,learned_scene,source,certainty,supersedes,status\n",
    "relationships.csv": "relationship_id,episode,scene,party_a,party_b,trust,power,intimacy,public_status,private_status,change,source,status\n",
    "props-ledger.csv": "prop_id,prop,current_holder,location,condition,last_event,source_episode,source_scene,provenance,status\n",
    "evidence.csv": "evidence_id,evidence,created_episode,created_scene,current_holder,proves,known_by,chain_of_custody,source,status\n",
    "hooks-ledger.csv": "hook_id,setup_episode,hook_episode,type,audience_question,promise,answer_owner,resolve_by,actual_resolution,status,evidence,risk\n",
    "foreshadowing.csv": "foreshadow_id,setup,setup_episode,setup_scene,reinforcement,payoff_by,actual_payoff,status,evidence\n",
}


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def write_json(path: Path, value: dict) -> None:
    write_new(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def artifact_specs(source_mode: str, through: str) -> dict[str, dict]:
    specs: dict[str, dict] = {
        "productionSpecs": {"path": SPECS, "dependsOn": []},
        "episodePlan": {"path": PLAN, "dependsOn": [SPECS]},
        "projectBrief": {"path": "00-project-brief.md", "dependsOn": [SPECS]},
        "sourceEvidence": {"path": "source-evidence.json", "dependsOn": ["00-project-brief.md"]},
        "canon": {"path": "continuity/canon.yaml", "dependsOn": ["00-project-brief.md"]},
        "lockedDecisions": {"path": "locked-decisions.md", "dependsOn": []},
        "changeLog": {"path": "change-log.md", "dependsOn": []},
    }
    if through in {"story-bible", "full"}:
        if source_mode in {"original", "market_research"}:
            specs["originalDiscovery"] = {"path": "03-original-discovery.md", "dependsOn": ["00-project-brief.md"]}
            story_deps = ["00-project-brief.md", "03-original-discovery.md"]
        else:
            specs["sourceIndex"] = {"path": "01-source-index.md", "dependsOn": ["00-project-brief.md"]}
            specs["sourceTruth"] = {"path": "02-source-truth.md", "dependsOn": ["01-source-index.md"]}
            specs["adaptationMap"] = {"path": "03-adaptation-map.md", "dependsOn": ["02-source-truth.md"]}
            story_deps = ["00-project-brief.md", "03-adaptation-map.md"]
        if source_mode == "market_research":
            specs["marketResearch"] = {"path": "02-market-research.md", "dependsOn": ["source-evidence.json"]}
            story_deps.append("02-market-research.md")
        specs["storyTreatment"] = {"path": "03-story-treatment.md", "dependsOn": story_deps + ["source-evidence.json"]}
        specs["storyBible"] = {"path": "04-story-bible.md", "dependsOn": ["03-story-treatment.md"]}
    if through == "full":
        specs["seasonArchitecture"] = {"path": "05-season-architecture.md", "dependsOn": ["04-story-bible.md", PLAN]}
        specs["episodeMatrix"] = {"path": "06-episode-matrix.csv", "dependsOn": ["04-story-bible.md", "05-season-architecture.md"]}
        for name in CSV_HEADERS:
            key = "continuity_" + name.removesuffix(".csv").replace("-", "_")
            specs[key] = {"path": f"continuity/{name}", "dependsOn": ["04-story-bible.md", "06-episode-matrix.csv"]}
    return specs


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path, help="New or empty project directory")
    parser.add_argument("--mode", choices=("original", "adaptation", "market-research", "source-remix"), default="original", help="Three new-project routes; source-remix retains the legacy material route")
    parser.add_argument("--production-mode", choices=("live_action", "ai_drama", "hybrid", "unspecified"), default="unspecified")
    parser.add_argument("--source-mode", choices=tuple(SOURCE_MODES), help="Actual creator source choice, after production mode; requires selection receipts")
    parser.add_argument("--orientation", choices=("vertical", "horizontal", "custom"), default="vertical")
    parser.add_argument("--delivery-scope", choices=("diagnosis", "outline", "episodes", "screenplay", "review", "revision", "knowledge", "unspecified"), default="unspecified")
    parser.add_argument("--review-mode", choices=("strict", "assisted", "automatic"), default="strict")
    parser.add_argument("--language", default="zh-CN")
    parser.add_argument("--target-market", action="append", default=[], help="Repeat for multiple markets")
    parser.add_argument("--total-episodes", type=int, help="Legacy candidate only; record the actual outline total with workflow set-plan")
    duration = parser.add_mutually_exclusive_group()
    duration.add_argument("--duration-seconds", type=int)
    duration.add_argument("--duration-range", help="Single-episode range in seconds, e.g. 50-60")
    parser.add_argument("--episode-count", help="Flexible creator preference, e.g. 60, 约60集, or 40-60")
    parser.add_argument("--specs-user-quote")
    parser.add_argument("--specs-message-ref")
    parser.add_argument(
        "--through",
        choices=("brief", "story-bible", "full"),
        default="full",
        help="Create files only through the requested workflow stage",
    )
    args = parser.parse_args()
    if args.total_episodes is not None and args.total_episodes < 1:
        parser.error("--total-episodes must be positive")
    source_mode = args.mode.replace("-", "_")

    # Legacy mode/count flags alone are candidates, never user confirmation.
    production = empty_specs()
    if args.specs_user_quote is not None or args.specs_message_ref is not None:
        try:
            production = apply_choices(production,
                production_mode=args.production_mode if args.production_mode != "unspecified" else None,
                source_mode=args.source_mode,
                duration_seconds=args.duration_seconds, duration_range=args.duration_range,
                episode_count=args.episode_count, user_quote=args.specs_user_quote or "",
                message_ref=args.specs_message_ref or "")
        except ValueError as exc:
            parser.error(str(exc))
    elif any(v is not None for v in (args.source_mode, args.duration_seconds, args.duration_range, args.episode_count)):
        parser.error("production choices require --specs-user-quote and --specs-message-ref")
    selected_mode = production["productionMode"] or "unspecified"
    source_mode = production["sourceMode"] or source_mode

    root = args.project_dir.expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        parser.error(f"target is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    assets = Path(__file__).resolve().parent.parent / "assets"

    copies = {"project-brief-template.md": "00-project-brief.md"}
    if args.through in {"story-bible", "full"}:
        copies["story-bible-template.md"] = "04-story-bible.md"
        if source_mode in {"original", "market_research"}:
            copies["original-discovery-template.md"] = "03-original-discovery.md"
        else:
            copies["source-truth-template.md"] = "02-source-truth.md"
            copies["adaptation-map-template.md"] = "03-adaptation-map.md"
    if args.through == "full":
        copies["season-architecture-template.md"] = "05-season-architecture.md"
        copies["episode-matrix-template.csv"] = "06-episode-matrix.csv"
    for source_name, target_name in copies.items():
        shutil.copyfile(assets / source_name, root / target_name)

    write_json(root / "source-evidence.json", empty_source(source_mode))
    if args.through in {"story-bible", "full"}:
        write_new(root / "03-story-treatment.md", "# 完整故事底稿\n\n<!-- 用连续自然语言写到结局，先审读因果和动机，再展开大纲。 -->\n")
        if source_mode == "market_research":
            write_new(root / "02-market-research.md", "# 近期热门材料与改编取舍\n\n<!-- 记录实际查询日期、来源类型、热度口径、缺口、可用原文及实际改编/再创作取舍；用户要求原创参考时保留原创边界。 -->\n")

    if source_mode in {"adaptation", "source_remix"} and args.through in {"story-bible", "full"}:
        write_new(root / "01-source-index.md", "# 原著索引\n\n")

    canon = (
        'schemaVersion: "1.0.0"\nproject:\n  title: ""\n'
        f'  sourceMode: "{source_mode}"\n  productionMode: "{selected_mode}"\n'
        f'  orientation: "{args.orientation}"\n  status: draft\n'
        "immutable_facts: []\nconfirmed_facts: []\ncurrent_plans: []\ndiscarded: []\n"
    )
    write_new(root / "continuity" / "canon.yaml", canon)
    if args.through == "full":
        for name, header in CSV_HEADERS.items():
            write_new(root / "continuity" / name, header)

    write_new(root / "locked-decisions.md", "# 锁定决策\n\n")
    write_new(root / "change-log.md", "# 变更记录\n\n")
    if args.through == "full":
        for directory in ("episodes", "deliverables", "reviews", "qc", "context-packs"):
            (root / directory).mkdir(parents=True, exist_ok=True)

    specs = artifact_specs(source_mode, args.through)
    indexed = {
        key: {"path": spec["path"], "revision": 1, "status": "draft", "dependsOn": spec["dependsOn"], "validators": ["validate_project.py"], "contentHash": None}
        for key, spec in specs.items()
    }
    state_artifacts = {
        key: {"path": value["path"], "revision": value["revision"], "status": value["status"], "dependsOn": value["dependsOn"]}
        for key, value in indexed.items()
    }
    project_id = "drama-" + hashlib.sha256(root.name.encode("utf-8")).hexdigest()[:12]
    write_json(root / ".drama" / "project-state.json", {
        "schemaVersion": "1.0.0", "projectId": project_id, "projectRevision": 1,
        "sourceMode": source_mode, "productionMode": selected_mode,
        "orientation": args.orientation, "deliveryScope": args.delivery_scope,
        "reviewMode": args.review_mode, "language": args.language,
        "targetMarkets": args.target_market, "platformProfiles": [],
        "currentPhase": "brief", "totalEpisodes": None,
        "lockedDecisionsRevision": 0, "artifacts": state_artifacts, "episodes": {}
    })
    write_json(root / ".drama" / "artifact-index.json", {"schemaVersion": "1.0.0", "projectRevision": 1, "artifacts": indexed})
    write_json(root / SPECS, production)
    write_json(root / PLAN, empty_plan())
    write_new(root / ".drama" / "invalidation-log.jsonl", "")
    write_json(root / ".drama/workflow.json", {
        "schemaVersion": "1.0.0", "phase": "awaiting_production_specs" if any(production[f] is None for f in ("productionMode", "sourceMode", "duration", "episodeCountPreference")) else "source", "reviews": [],
        "outlineConfirmation": None, "confirmationHistory": [], "events": [],
    })
    write_json(root / ".humanizer" / "policy.json", {
        "schemaVersion": "1.0.0", "required": False, "mode": "local",
        "humanizerCommit": "9862685f575c65a8247f90369951df1b3416e3d6",
        "adapter": "short-drama", "adapterVersion": "1.0.0",
        "statusRule": "Local edits only where needed; unchanged text may pass after final semantic review. One rewriter per project.",
    })
    (root / ".humanizer" / "originals").mkdir(parents=True, exist_ok=True)

    print(f"Created {source_mode} short-drama project through {args.through}: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
