#!/usr/bin/env python3
"""Verify and record a model-executed Humanizer pass without storing prose."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

HUMANIZER_COMMIT = "9862685f575c65a8247f90369951df1b3416e3d6"
ADAPTER_VERSION = "1.0.0"
PROTECTED = re.compile(
    r"```[\s\S]*?```|`[^`\n]+`|https?://[^\s)>\]}，。；、！？]+|"
    r"\{\{[^{}]+\}\}|\$\{[^{}]+\}|<%[\s\S]*?%>|"
    r"^\s*\[[A-Za-z][^\]\n]{0,80}\]\s*$|"
    r"(?<!\w)@[-\w.]+|\b\d{1,2}:\d{2}(?::\d{2})?(?:\.\d{1,3})?\b|"
    r"\([^()\n]+:[+-]?(?:\d+(?:\.\d+)?|\.\d+)\)"
, re.MULTILINE)


def digest(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def protected(text: str) -> list[str]:
    return PROTECTED.findall(text)


def load(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def validate_structure(path: Path, text: str) -> list[str]:
    errors: list[str] = []
    if not text.strip():
        errors.append("result is empty")
    if path.suffix.lower() == ".json":
        try:
            json.loads(text)
        except json.JSONDecodeError as exc:
            errors.append(f"invalid JSON: {exc.msg}")
    return errors


def verification(draft: Path, final: Path) -> dict:
    before, after = load(draft), load(final)
    errors = validate_structure(final, after)
    if protected(before) != protected(after):
        errors.append("protected tokens changed, disappeared, or were reordered")
    before_lines = len(before.splitlines())
    after_lines = len(after.splitlines())
    if before_lines >= 20 and after_lines < max(1, before_lines // 3):
        errors.append("possible silent truncation")
    return {
        "ok": not errors,
        "errors": errors,
        "source_sha256": digest(before),
        "result_sha256": digest(after),
        "protected_count": len(protected(before)),
        "source_lines": before_lines,
        "result_lines": after_lines,
    }


def log_path(final: Path, explicit: Path | None) -> Path:
    return explicit or final.parent / ".humanizer" / "runs.jsonl"


def append_record(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(data, ensure_ascii=False, sort_keys=True) + "\n")


def records(path: Path) -> list[dict]:
    if not path.exists():
        return []
    result = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            result.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate and audit a model-executed Humanizer pass")
    sub = parser.add_subparsers(dest="command", required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--draft", type=Path, required=True)
    verify.add_argument("--final", type=Path, required=True)
    record = sub.add_parser("record")
    record.add_argument("--draft", type=Path, required=True)
    record.add_argument("--final", type=Path, required=True)
    record.add_argument("--adapter", required=True)
    record.add_argument("--log", type=Path)
    record.add_argument("--attestation", choices=["model-edit-complete"], required=True)
    check = sub.add_parser("check")
    check.add_argument("--final", type=Path, required=True)
    check.add_argument("--log", type=Path)
    fail = sub.add_parser("fail")
    fail.add_argument("--draft", type=Path, required=True)
    fail.add_argument("--final", type=Path, required=True)
    fail.add_argument("--adapter", required=True)
    fail.add_argument("--reason", choices=["model_error", "timeout", "validation_failed"], required=True)
    fail.add_argument("--log", type=Path)
    args = parser.parse_args()

    if args.command == "verify":
        report = verification(args.draft, args.final)
        print(json.dumps(report, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 2

    if args.command == "record":
        report = verification(args.draft, args.final)
        status = "completed" if report["ok"] else "validation_failed"
        entry = {
            **report,
            "status": status,
            "humanizer_commit": HUMANIZER_COMMIT,
            "adapter_version": ADAPTER_VERSION,
            "adapter": args.adapter,
            "final_path": str(args.final.resolve()),
            "completed_at": datetime.now(timezone.utc).isoformat(),
            "attestation": args.attestation,
        }
        audit_path = log_path(args.final, args.log)
        originals = audit_path.parent / "originals"
        originals.mkdir(parents=True, exist_ok=True)
        snapshot = originals / f"{report['source_sha256']}{args.draft.suffix or '.txt'}"
        if not snapshot.exists():
            snapshot.write_text(load(args.draft), encoding="utf-8")
        entry["original_snapshot"] = str(snapshot.resolve())
        append_record(audit_path, entry)
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        return 0 if report["ok"] else 2

    if args.command == "fail":
        source = load(args.draft)
        entry = {
            "status": args.reason,
            "source_sha256": digest(source),
            "result_sha256": digest(load(args.final)) if args.final.exists() else None,
            "humanizer_commit": HUMANIZER_COMMIT,
            "adapter_version": ADAPTER_VERSION,
            "adapter": args.adapter,
            "final_path": str(args.final.resolve()),
            "completed_at": datetime.now(timezone.utc).isoformat(),
        }
        append_record(log_path(args.final, args.log), entry)
        print(json.dumps(entry, ensure_ascii=False, indent=2))
        return 4

    path = log_path(args.final, args.log)
    if not args.final.exists():
        print(json.dumps({"processed": False, "result_sha256": None, "log": str(path), "error": "final file missing"}, ensure_ascii=False))
        return 3
    current_hash = digest(load(args.final))
    match = next((r for r in reversed(records(path)) if r.get("final_path") == str(args.final.resolve())), None)
    ok = bool(match and match.get("status") == "completed" and match.get("result_sha256") == current_hash)
    print(json.dumps({"processed": ok, "result_sha256": current_hash, "log": str(path)}, ensure_ascii=False))
    return 0 if ok else 3


if __name__ == "__main__":
    raise SystemExit(main())
