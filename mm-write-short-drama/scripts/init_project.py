#!/usr/bin/env python3
"""Create a short-drama project skeleton without overwriting existing files."""

from __future__ import annotations

import argparse
import shutil
from pathlib import Path


CSV_HEADERS = {
    "timeline.csv": "event_id,date,time,event,location,participants,duration,source_episode,status\n",
    "character-state.csv": "episode,character,physical,emotion,relationships,resources,knowledge_summary,current_goal,status\n",
    "knowledge-state.csv": "fact_id,character,knowledge,learned_episode,learned_scene,source,certainty,status\n",
    "props-ledger.csv": "prop_id,prop,current_holder,location,condition,last_event,source_episode,status\n",
    "hooks-ledger.csv": "hook_id,hook,introduced_episode,progress_episode,planned_payoff,actual_payoff,status,notes\n",
}


def write_new(path: Path, content: str) -> None:
    if path.exists():
        raise FileExistsError(f"Refusing to overwrite: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path, help="New or empty project directory")
    parser.add_argument("--mode", choices=("original", "adaptation"), default="original")
    parser.add_argument(
        "--through",
        choices=("brief", "story-bible", "full"),
        default="full",
        help="Create files only through the requested workflow stage",
    )
    args = parser.parse_args()

    root = args.project_dir.expanduser().resolve()
    if root.exists() and any(root.iterdir()):
        parser.error(f"target is not empty: {root}")
    root.mkdir(parents=True, exist_ok=True)
    assets = Path(__file__).resolve().parent.parent / "assets"

    copies = {"project-brief-template.md": "00-project-brief.md"}
    if args.through in {"story-bible", "full"}:
        copies["story-bible-template.md"] = "04-story-bible.md"
        if args.mode == "original":
            copies["original-discovery-template.md"] = "03-original-discovery.md"
        else:
            copies["source-truth-template.md"] = "02-source-truth.md"
            copies["adaptation-map-template.md"] = "03-adaptation-map.md"
    if args.through == "full":
        copies["season-architecture-template.md"] = "05-season-architecture.md"
        copies["episode-matrix-template.csv"] = "06-episode-matrix.csv"
    for source_name, target_name in copies.items():
        shutil.copyfile(assets / source_name, root / target_name)

    if args.mode == "adaptation" and args.through in {"story-bible", "full"}:
        write_new(root / "01-source-index.md", "# 原著索引\n\n")

    canon = """project:\n  title: \"\"\n  mode: \"%s\"\n  status: draft\nimmutable_facts: []\nconfirmed_facts: []\ncurrent_plans: []\ndiscarded: []\n""" % args.mode
    write_new(root / "continuity" / "canon.yaml", canon)
    if args.through == "full":
        for name, header in CSV_HEADERS.items():
            write_new(root / "continuity" / name, header)

    write_new(root / "locked-decisions.md", "# 锁定决策\n\n")
    write_new(root / "change-log.md", "# 变更记录\n\n")
    if args.through == "full":
        for directory in ("episodes", "reviews", "context-packs"):
            (root / directory).mkdir(parents=True, exist_ok=True)

    print(f"Created {args.mode} short-drama project through {args.through}: {root}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
