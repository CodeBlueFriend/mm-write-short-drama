#!/usr/bin/env python3
"""Resume a writing project, record two-pass reviews and confirm a specific outline."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from workflow_lib import (
    DOMAINS, confirm_outline, episode_range, load_workflow, read_json, record_review,
    review_pack, reveal_context, save_json, session_path, submit_first_read,
    synchronize, validate_release, writing_errors,
)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("project_dir", type=Path)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("status", help="Resume, detect changed inputs and persist stale states")
    pack = sub.add_parser("review-pack", help="Create ordered raw-text chunks, with no author answers in pass one")
    pack.add_argument("--stage", choices=tuple(DOMAINS), required=True)
    pack.add_argument("--episodes", type=episode_range, default=[])
    pack.add_argument("--front-matter", type=Path)
    pack.add_argument("--chunk-lines", type=int, default=400)
    for command in ("first-read", "reveal-context", "record-review", "report-template"):
        p = sub.add_parser(command)
        p.add_argument("--session", required=True)
        if command in {"first-read", "record-review"}:
            p.add_argument("--report", type=Path, required=True)
        if command == "report-template":
            p.add_argument("--output", type=Path, required=True)
    confirm = sub.add_parser("confirm-outline", help="Record an actual user decision; never infer from automatic mode")
    confirm.add_argument("--decision", choices=("confirm", "revise"), required=True)
    confirm.add_argument("--quote", required=True)
    confirm.add_argument("--message-ref", required=True)
    confirm.add_argument("--scope", required=True)
    sub.add_parser("check-writing")
    release = sub.add_parser("check-release")
    release.add_argument("--episodes", type=episode_range, required=True)
    release.add_argument("--front-matter", type=Path, required=True)
    args = parser.parse_args()
    root = args.project_dir.expanduser().resolve()
    try:
        load_workflow(root)
        if args.command == "status":
            result = synchronize(root)
        elif args.command == "review-pack":
            front = str(args.front_matter.resolve().relative_to(root)) if args.front_matter else None
            result = review_pack(root, args.stage, args.episodes, front, args.chunk_lines)
        elif args.command == "first-read":
            result = submit_first_read(root, args.session, args.report)
        elif args.command == "reveal-context":
            result = reveal_context(root, args.session)
        elif args.command == "record-review":
            result = record_review(root, args.session, args.report)
        elif args.command == "report-template":
            session = read_json(session_path(root, args.session))
            first = {"reviewer": "", "knowledgeOfExpectations": "informed", "readChunks": [],
                     "causalRetelling": "", "observations": [
                         {"chunkId": c["id"], "protagonistIntent": "", "concern": "", "forcedChange": "",
                          "understanding": "", "evidence": []} for c in session["chunks"]]}
            final = {"sessionId": args.session, "stage": session["stage"], "reviewer": "", "complete": False,
                     "coverage": session["coverage"], "checks": [
                         {"domain": d, "result": "", "reason": "", "evidence": [], "issueIds": []}
                         for d in sorted(DOMAINS[session["stage"]])], "issues": [], "methods": [], "promiseAudit": []}
            if args.output.exists():
                raise ValueError("refusing to overwrite report template")
            save_json(args.output, {"firstRead": first, "secondPass": final})
            result = {"template": str(args.output), "note": "Extract and fill the two objects separately after actually reading; template is not a review."}
        elif args.command == "confirm-outline":
            result = confirm_outline(root, args.decision, args.quote, args.message_ref, args.scope)
        elif args.command == "check-writing":
            errors = writing_errors(root)
            result = {"allowed": not errors, "errors": errors}
        else:
            errors = validate_release(root, args.episodes, args.front_matter)
            result = {"allowed": not errors, "errors": errors}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps(result, ensure_ascii=False, indent=2))
    if args.command in {"check-writing", "check-release"} and result["errors"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
