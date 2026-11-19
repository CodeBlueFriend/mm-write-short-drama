#!/usr/bin/env python3
"""Check expression edits and record an explicit final semantic review.

This is a conservative change detector, not a natural-language truth evaluator.
Every edited passage needs an actual before/after review; suspicious fact changes
remain blocked unless their exact change IDs have an editor approval.
"""
from __future__ import annotations
import argparse
import difflib
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


TOKENS = {
    "amount_or_date": re.compile(r"[零〇一二两三四五六七八九十百千万亿\d]+(?:\.\d+)?(?:元|块|万元|万|号|日|月|年|点|时|分|天|集|张|桌|成|%)?"),
    "subject_or_responsibility": re.compile(r"我|你|您|他|她|我们|你们|他们|她们|由.{1,8}(?:收|付|还|签|承担)|是.{1,8}(?:收|付|还|签|承担)"),
    "negation": re.compile(r"不|没|无|未|别|不能|不得|并非|从未|没有"),
    "condition_or_promise": re.compile(r"如果|只要|只有|除非|否则|才|就|必须|一定|答应|承诺|保证|之前|之后|以前|以后|直到|先|再"),
}
STRUCTURAL = re.compile(r"^(?:#{1,6}\s|人物[：:]|[A-Z][A-Z0-9_-]*[：:]|\s*\|)")


def inspect_changes(before: Path, after: Path) -> dict:
    left = before.read_text(encoding="utf-8-sig").splitlines()
    right = after.read_text(encoding="utf-8-sig").splitlines()
    changes = []
    matcher = difflib.SequenceMatcher(a=left, b=right, autojunk=False)
    for tag, i, j, k, l in matcher.get_opcodes():
        if tag == "equal":
            continue
        old, new = "\n".join(left[i:j]), "\n".join(right[k:l])
        flags = []
        if any(STRUCTURAL.match(x) for x in left[i:j] + right[k:l]):
            flags.append("protected_structure")
        for label, pattern in TOKENS.items():
            if pattern.findall(old) != pattern.findall(new):
                flags.append(label)
        # Names/props may be changed without touching a token above. Do not
        # auto-clear unflagged prose: all edits still require semantic reading.
        change_id = hashlib.sha256(json.dumps([i+1,j,k+1,l,old,new],ensure_ascii=False).encode()).hexdigest()[:16]
        changes.append({"id":change_id,"beforeLines":[i+1,j],"afterLines":[k+1,l],"before":old,"after":new,"flags":flags})
    return {"schemaVersion":"1.0.0","beforeHash":digest(before),"afterHash":digest(after),"changes":changes,"requiresSemanticReview":True}


def record_review(before: Path, after: Path, review_path: Path, output: Path) -> dict:
    report = inspect_changes(before, after)
    review = json.loads(review_path.read_text(encoding="utf-8"))
    errors = []
    if review.get("beforeHash") != report["beforeHash"] or review.get("afterHash") != report["afterHash"]:
        errors.append("review hashes do not match current before/after files")
    if not review.get("reviewer") or not review.get("evidence") or review.get("semanticVerified") is not True:
        errors.append("actual reviewer, evidence and semanticVerified=true are required")
    required_checks = {"characters","subject_object","negation","conditions","time","amounts","promises","voice","continuity"}
    if not required_checks.issubset(set(review.get("checked",[]))):
        errors.append("review must cover characters, subject/object, negation, conditions, time, amounts, promises, voice and continuity")
    decisions = {item.get("id"):item for item in review.get("changes",[])}
    for change in report["changes"]:
        decision = decisions.get(change["id"],{})
        if decision.get("meaningPreserved") is not True or not decision.get("reason"):
            errors.append(f"change {change['id']} requires a before/after semantic decision")
        if change["flags"] and not decision.get("editorApproval"):
            errors.append(f"change {change['id']} changes protected tokens; restore it or record exact editor approval")
    mode = review.get("mode","local")
    if mode not in {"off","local","full"}:
        errors.append("mode must be off, local or full")
    if mode == "off" and report["changes"]:
        errors.append("mode=off requires identical input and output")
    if mode != "off" and not review.get("callChain"):
        errors.append("record the actual editor/rule locations and call chain")
    if errors:
        raise ValueError("; ".join(errors))
    result={**report,"status":"passed","mode":mode,"review":review,"reviewedAt":datetime.now(timezone.utc).isoformat(),"beforePath":os.path.relpath(before.resolve(),output.parent.resolve())}
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    return result


def validate_record(after: Path, record_path: Path) -> list[str]:
    """Revalidate the saved attestation contract; this cannot judge prose meaning."""
    try:
        record=json.loads(record_path.read_text(encoding="utf-8"))
    except (OSError,ValueError) as exc:
        return [f"missing or invalid semantic review: {exc}"]
    if not isinstance(record,dict): return ["semantic record must be an object"]
    errors=[]
    try:
        current_hash=digest(after)
    except OSError as exc:
        return [f"cannot read current output: {exc}"]
    if record.get("status")!="passed" or record.get("afterHash")!=current_hash:
        errors.append("missing or stale semantic review")
    if not re.fullmatch(r"[0-9a-f]{64}",str(record.get("beforeHash",""))) or not record.get("reviewedAt"):
        errors.append("semantic review requires baseline hash and review time")
    review=record.get("review",{})
    if not isinstance(review,dict): return errors+["semantic review must be an object"]
    if review.get("beforeHash")!=record.get("beforeHash") or review.get("afterHash")!=record.get("afterHash"):
        errors.append("attestation hashes do not match the recorded edit")
    if not review.get("reviewer") or not review.get("evidence") or review.get("semanticVerified") is not True:
        errors.append("semantic reviewer, evidence and verified decision are required")
    checks={"characters","subject_object","negation","conditions","time","amounts","promises","voice","continuity"}
    if not checks.issubset(set(review.get("checked",[]))):
        errors.append("semantic review is missing one or more of the nine required checks")
    mode=record.get("mode")
    if mode not in {"off","local","full"} or review.get("mode","local")!=mode:
        errors.append("invalid or inconsistent polish mode")
    changes=record.get("changes")
    if not isinstance(changes,list):
        errors.append("semantic record requires a change list")
        changes=[]
    if mode=="off" and (changes or record.get("beforeHash")!=record.get("afterHash")):
        errors.append("off mode requires identical files and no changes")
    if mode!="off" and not review.get("callChain"):
        errors.append("edited output requires the actual call chain")
    baseline=record.get("beforePath")
    if not baseline:
        errors.append("semantic review is missing its preserved baseline path")
    else:
        before=(record_path.parent / baseline).resolve()
        try:
            actual=inspect_changes(before,after)
            if actual.get("beforeHash")!=record.get("beforeHash") or actual.get("changes")!=changes:
                errors.append("saved differences do not match the preserved baseline and current text")
        except (OSError,ValueError) as exc:
            errors.append(f"cannot revalidate preserved baseline: {exc}")
    decisions={item.get("id"):item for item in review.get("changes",[]) if isinstance(item,dict)}
    for change in changes:
        if not isinstance(change,dict):
            errors.append("invalid saved change")
            continue
        decision=decisions.get(change.get("id"),{})
        if decision.get("meaningPreserved") is not True or not decision.get("reason"):
            errors.append(f"change {change.get('id')} is missing a semantic decision")
        if change.get("flags") and not decision.get("editorApproval"):
            errors.append(f"change {change.get('id')} requires exact editor approval")
    return errors


def main() -> int:
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action",choices=("inspect","record","check"))
    parser.add_argument("--before",type=Path)
    parser.add_argument("--after",required=True,type=Path)
    parser.add_argument("--review",type=Path)
    parser.add_argument("--output",type=Path)
    args=parser.parse_args()
    try:
        if args.action=="check":
            if not args.review: raise ValueError("--review must point to an existing passed record")
            record=json.loads(args.review.read_text(encoding="utf-8"))
            errors=validate_record(args.after,args.review)
            if errors: raise ValueError("; ".join(errors))
            if args.before and record.get("beforeHash")!=digest(args.before):
                raise ValueError("baseline changed")
            result={"ok":True,"afterHash":record["afterHash"]}
        else:
            if not args.before: raise ValueError("--before is required")
            if args.action=="record":
                if not args.review or not args.output: raise ValueError("--review and --output are required")
                result=record_review(args.before,args.after,args.review,args.output)
            else:
                result=inspect_changes(args.before,args.after)
                if args.output:
                    args.output.parent.mkdir(parents=True,exist_ok=True)
                    args.output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        print(json.dumps(result,ensure_ascii=False,indent=2))
        return 0
    except (ValueError,OSError,json.JSONDecodeError) as exc:
        parser.error(str(exc))


if __name__=="__main__":
    raise SystemExit(main())
