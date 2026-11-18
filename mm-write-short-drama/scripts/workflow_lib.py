"""Content-bound workflow receipts. Models read and judge; this module verifies evidence.

Receipts are audit records, not proof that a model's literary judgment is correct.
Never infer approval from a counter or silently migrate a legacy project.
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
import shutil
import uuid
from datetime import datetime, timezone
from pathlib import Path

VERSION = "1.0.0"
TREATMENT = "03-story-treatment.md"
OUTLINE = "05-season-architecture.md"
SOURCE = "source-evidence.json"
LOCK_INPUTS = ["00-project-brief.md", "locked-decisions.md", "continuity/canon.yaml"]
CONTEXT = [SOURCE, TREATMENT, "04-story-bible.md", OUTLINE,
           "06-episode-matrix.csv", *LOCK_INPUTS]
DOMAINS = {
    "treatment": {"causality", "motivation", "ending", "source_fidelity"},
    "outline": {"causality", "motivation", "escalation", "choice_cost", "payoff", "source_fidelity"},
    "batch": {"causality", "motivation", "knowledge", "continuity", "payoff", "rhythm", "voice"},
    "final": {"causality", "motivation", "knowledge", "continuity", "payoff", "rhythm", "voice", "genre", "front_matter", "source_fidelity"},
}
HARD = {"knowledge_state", "locked_fact", "timeline", "prop", "causality", "foreshadowing"}
SCENE = re.compile(r"^#{1,4}\s+(\d+-\d+)\s+", re.M)


def actor_lines(content: str) -> list[tuple[int, str]]:
    """Return only visible screenplay, retaining original line coordinates."""
    rows, hidden, comment = [], False, False
    for number, line in enumerate(content.splitlines(), 1):
        stripped = line.strip()
        if "<!--" in stripped:
            comment = "-->" not in stripped
            continue
        if comment:
            if "-->" in stripped:
                comment = False
            continue
        if re.match(r"^##\s+(本集控制信息|本集连续性更新|改编记录)\s*$", stripped):
            hidden = True
            continue
        if SCENE.match(stripped):
            hidden = False
        if not hidden:
            rows.append((number, line))
    return rows


def now() -> str:
    return datetime.now(timezone.utc).isoformat()


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path}")
    return value


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def local(root: Path, name: str) -> Path:
    path = (root / name).resolve()
    if not path.is_relative_to(root.resolve()):
        raise ValueError(f"path escapes project: {name}")
    return path


def episode_id(value: str | int) -> str:
    match = re.fullmatch(r"(?:EP)?0*(\d+)", str(value), re.I)
    if not match or int(match[1]) < 1:
        raise ValueError(f"invalid episode: {value}")
    return f"{int(match[1]):03d}"


def episode_range(value: str) -> list[str]:
    ids = []
    for segment in value.split(","):
        bounds = segment.split("-")
        first = int(episode_id(bounds[0]))
        last = int(episode_id(bounds[-1]))
        if len(bounds) > 2 or last < first:
            raise ValueError("invalid episode range")
        ids.extend(f"{n:03d}" for n in range(first, last + 1))
    if len(ids) != len(set(ids)):
        raise ValueError("duplicate episode in range")
    return ids


def load_workflow(root: Path) -> dict:
    path = root / ".drama/workflow.json"
    if not path.exists():
        raise ValueError("missing workflow.json; legacy project needs explicit migration, approval remains unknown")
    return read_json(path)


def snapshots(root: Path, paths: list[str]) -> dict:
    result = {}
    for name in dict.fromkeys(paths):
        path = local(root, name)
        if not path.is_file():
            raise ValueError(f"missing required input: {name}")
        result[name] = digest(path)
    return result


def changed_inputs(root: Path, values: dict) -> list[str]:
    return [name for name, sha in values.items()
            if not local(root, name).is_file() or digest(local(root, name)) != sha]


def source_errors(root: Path) -> list[str]:
    try:
        state, source = read_json(root / ".drama/project-state.json"), read_json(root / SOURCE)
        mode = state["sourceMode"]
        errors = []
        if source.get("sourceMode") != mode:
            errors.append("source evidence route does not match project")
        if mode == "original":
            if not str(source.get("originalIdea", "")).strip():
                errors.append("original source requires creator's actual idea")
        else:
            records = source.get("records", [])
            if not records:
                errors.append("source route needs evidence records; failed sources must remain explicitly unavailable")
            for record in records:
                for key in ("title", "contentType", "accessStatus", "coverage", "limitations"):
                    if key not in record:
                        errors.append(f"source record missing {key}")
                if record.get("accessStatus") == "read":
                    if not record.get("visibleEvidence") or not (record.get("url") or record.get("path")):
                        errors.append("read source requires locator and visible evidence")
                    if record.get("path"):
                        path = Path(record["path"])
                        path = path if path.is_absolute() else local(root, record["path"])
                        if not path.is_file() or record.get("sha256") != digest(path):
                            errors.append(f"source snapshot changed or missing: {record['path']}")
                elif not record.get("limitations"):
                    errors.append("unavailable source must explain its gap")
            if mode in {"adaptation", "source_remix"} and not source.get("authorizationStatus"):
                errors.append("adaptation requires recorded authorization status (unknown is allowed)")
            if mode == "market_research":
                for key in ("queryDate", "windowDays", "platform", "region", "genre"):
                    if not source.get(key):
                        errors.append(f"market research missing {key}")
                try:
                    datetime.strptime(source.get("queryDate", ""), "%Y-%m-%d")
                except ValueError:
                    errors.append("queryDate must be an actual YYYY-MM-DD date")
                for record in records:
                    for key in ("url", "observedAt", "chartPeriod", "metricMeaning", "heatVerification"):
                        if not record.get(key):
                            errors.append(f"market record missing {key}")
                if not source.get("originalityDecisions"):
                    errors.append("market research needs new goals, causal order and ending with differences from references")
        return errors
    except (OSError, ValueError, KeyError) as exc:
        return [f"invalid source evidence: {exc}"]


def source_dependencies(root: Path) -> list[str]:
    """Bind actual local sources, not just their catalog; preserve external files as snapshots."""
    result = []
    for record in read_json(root / SOURCE).get("records", []):
        if record.get("accessStatus") != "read" or not record.get("path"):
            continue
        original = Path(record["path"])
        original = original.resolve() if original.is_absolute() else local(root, record["path"])
        if original.is_relative_to(root):
            result.append(str(original.relative_to(root)))
        else:
            snapshot = root / ".drama/source-snapshots" / (digest(original) + original.suffix)
            snapshot.parent.mkdir(parents=True, exist_ok=True)
            if not snapshot.exists():
                shutil.copyfile(original, snapshot)
            if digest(snapshot) != digest(original):
                raise ValueError("source snapshot changed")
            result.append(str(snapshot.relative_to(root)))
    for name in ["01-source-index.md", "02-source-truth.md", "03-adaptation-map.md", "02-market-research.md"]:
        if (root / name).is_file():
            result.append(name)
    return result


def review_pack(root: Path, stage: str, episodes: list[str], front_matter: str | None = None,
                chunk_lines: int = 400) -> dict:
    workflow = load_workflow(root)
    errors = source_errors(root)
    if stage == "outline":
        errors += gate_errors(root, "treatment")
    if stage in {"batch", "final"}:
        errors += writing_errors(root)
    if errors:
        raise ValueError("; ".join(errors))
    if chunk_lines < 30:
        raise ValueError("chunk-lines must be at least 30")
    if stage == "treatment":
        inputs = [TREATMENT]
        dependencies = [SOURCE]
    elif stage == "outline":
        inputs = ["04-story-bible.md", OUTLINE]
        dependencies = [SOURCE, TREATMENT]
    else:
        if not episodes:
            raise ValueError("episode review requires --episodes")
        episodes = [episode_id(n) for n in episodes]
        if len(set(episodes)) != len(episodes):
            raise ValueError("duplicate episodes in review scope")
        inputs = [f"episodes/EP{n}.md" for n in episodes]
        dependencies = list(CONTEXT)
        dependencies += [str(p.relative_to(root)) for p in sorted((root / "continuity").glob("*")) if p.is_file()]
        if front_matter:
            dependencies.append(front_matter)
        elif stage == "final":
            raise ValueError("final review requires --front-matter")
    dependencies += LOCK_INPUTS + source_dependencies(root)
    bound = snapshots(root, inputs + dependencies)
    session_id = "READ-" + uuid.uuid4().hex[:12]
    directory = root / ".drama/readings" / session_id
    directory.mkdir(parents=True)
    chunks, coverage = [], []
    # First pass contains only final text. Dependency snapshots stay in the receipt.
    for name in inputs:
        raw = local(root, name).read_text(encoding="utf-8-sig")
        numbered = actor_lines(raw) if stage in {"batch", "final"} else list(enumerate(raw.splitlines(), 1))
        lines = [line for _, line in numbered]
        if not lines:
            raise ValueError(f"empty review input: {name}")
        scenes = SCENE.findall("\n".join(lines))
        if stage in {"batch", "final"} and not scenes:
            raise ValueError(f"no reviewable scene headings: {name}")
        if stage in {"batch", "final"}:
            expected_number = int(re.search(r"EP(\d+)", name)[1])
            title = re.search(r"^#\s+第\s*(\d+)\s*集", raw, re.M)
            if not title or int(title[1]) != expected_number or any(int(s.split("-")[0]) != expected_number for s in scenes):
                raise ValueError(f"episode title or scene number does not match source file: {name}")
            if len(set(scenes)) != len(scenes):
                raise ValueError(f"duplicate scene numbers: {name}")
        coverage.append({"path": name, "sha256": bound[name], "lineCount": len(raw.splitlines()),
                         "visibleLines": [number for number, _ in numbered], "scenes": scenes})
        for start in range(0, len(lines), chunk_lines):
            end = min(start + chunk_lines, len(lines))
            chunk_id = f"C{len(chunks)+1:04d}"
            chunk_file = directory / f"{chunk_id}.md"
            # 20 lines of preceding material preserve the adjacent handoff.
            lo = max(0, start - 20)
            chunk_file.write_text(f"# {chunk_id} {name} source lines {numbered[lo][0]}–{numbered[end-1][0]}\n\n" + "\n".join(lines[lo:end]) + "\n", encoding="utf-8")
            chunks.append({"id": chunk_id, "path": str(chunk_file.relative_to(root)), "source": name,
                           "start": start + 1, "end": end, "sha256": digest(chunk_file)})
    session = {"schemaVersion": VERSION, "sessionId": session_id, "stage": stage,
               "episodes": episodes, "frontMatter": front_matter, "createdAt": now(),
               "inputs": bound, "coverage": coverage, "chunks": chunks,
               "firstRead": None, "contextRevealed": False, "status": "reading_incomplete"}
    save_json(directory / "session.json", session)
    return session


def session_path(root: Path, session_id: str) -> Path:
    if not re.fullmatch(r"READ-[a-f0-9]{12}", session_id):
        raise ValueError("invalid review session ID")
    return root / ".drama/readings" / session_id / "session.json"


def evidence_errors(root: Path, evidence: list, allowed: dict, body_only: bool = False) -> list[str]:
    if not isinstance(evidence, list) or not evidence:
        return ["evidence must contain actual source excerpts"]
    errors = []
    for ref in evidence:
        name, quote = ref.get("path"), ref.get("quote")
        content = local(root, name).read_text(encoding="utf-8-sig") if name in allowed else ""
        if body_only:
            content = "\n".join(line for _, line in actor_lines(content))
        if name not in allowed or not quote or quote not in content:
            errors.append(f"evidence not found in reviewed source: {name}: {quote}")
    return errors


def submit_first_read(root: Path, session_id: str, report_path: Path) -> dict:
    path = session_path(root, session_id)
    session, report = read_json(path), read_json(report_path)
    if session.get("firstRead"):
        raise ValueError("first-read notes are immutable; create a fresh session to reread")
    errors = session_errors(root, session)
    expected = [chunk["id"] for chunk in session["chunks"]]
    if report.get("readChunks") != expected:
        errors.append("reading incomplete: readChunks must include every chunk in viewing order")
    if not report.get("reviewer") or not report.get("causalRetelling"):
        errors.append("first read requires reviewer and causalRetelling, with explicit facts vs guesses")
    if report.get("knowledgeOfExpectations") not in {"blind", "informed"}:
        errors.append("declare knowledgeOfExpectations as blind or informed; never label an informed replay blind")
    observations = report.get("observations", [])
    if {o.get("chunkId") for o in observations} != set(expected):
        errors.append("first read requires live reader observations for each chunk")
    allowed = {row["path"]: row["sha256"] for row in session["coverage"]}
    for observation in observations:
        for key in ("protagonistIntent", "concern", "forcedChange", "understanding"):
            if not observation.get(key):
                errors.append(f"reader observation missing {key}")
        errors += evidence_errors(root, observation.get("evidence"), allowed, session["stage"] in {"batch", "final"})
    if errors:
        raise ValueError("; ".join(errors))
    saved = path.parent / "first-read.json"
    save_json(saved, report)
    session["firstRead"] = {"path": str(saved.relative_to(root)), "sha256": digest(saved), "recordedAt": now()}
    session["status"] = "first_read_complete"
    save_json(path, session)
    return session


def reveal_context(root: Path, session_id: str) -> dict:
    path = session_path(root, session_id)
    session = read_json(path)
    if not session.get("firstRead") or session_errors(root, session):
        raise ValueError("complete the current-text first read before revealing author context")
    input_names = {row["path"] for row in session["coverage"]}
    text = []
    for name in session["inputs"]:
        if name not in input_names:
            text.append(f"# {name}\n\n{local(root, name).read_text(encoding='utf-8-sig')}")
    outstanding = prior_blockers(root, session)
    if outstanding:
        text.append("# Historical unresolved issues (second pass only)\n\n" + json.dumps(outstanding, ensure_ascii=False, indent=2))
    context_path = path.parent / "second-pass-context.md"
    context_path.write_text("\n\n".join(text) + "\n", encoding="utf-8")
    session["contextRevealed"] = True
    session["contextPath"] = str(context_path.relative_to(root))
    session["contextHash"] = digest(context_path)
    save_json(path, session)
    return session


def session_errors(root: Path, session: dict) -> list[str]:
    errors = ["review inputs changed: " + name for name in changed_inputs(root, session["inputs"])]
    for chunk in session.get("chunks", []):
        if not local(root, chunk["path"]).is_file() or digest(local(root, chunk["path"])) != chunk["sha256"]:
            errors.append("review chunk changed: " + chunk["id"])
    first = session.get("firstRead")
    if first and (not local(root, first["path"]).is_file() or digest(local(root, first["path"])) != first["sha256"]):
        errors.append("first-read receipt changed")
    if session.get("contextRevealed") and (not local(root, session["contextPath"]).is_file() or digest(local(root, session["contextPath"])) != session.get("contextHash")):
        errors.append("second-pass context changed")
    return errors


def issue_applies(issue: dict, episodes: list[str] | None) -> bool:
    if not episodes:
        return True
    scope = issue.get("impactScope", [])
    # Non-episode scopes such as outline/front_matter are project-wide.
    if not scope or any(not re.fullmatch(r"(?:EP)?\d+", str(item), re.I) for item in scope):
        return True
    return bool({episode_id(item) for item in scope}.intersection(episodes))


def blocking_issues(report: dict, episodes: list[str] | None = None) -> list[dict]:
    result = []
    for issue in report.get("issues", []):
        if not issue_applies(issue, episodes):
            continue
        if issue.get("severity") not in {"P0", "P1"}:
            continue
        if issue.get("status") == "fixed" and issue.get("retest", {}).get("passed") is True and issue["retest"].get("evidence"):
            continue
        if issue.get("severity") == "P1" and issue.get("status") == "accepted_by_user" and issue.get("category") not in HARD and issue.get("userAcceptance", {}).get("quote") and issue["userAcceptance"].get("messageRef"):
            continue
        result.append(issue)
    return result


def tracked_blockers(root: Path, stage: str, episodes: list[str] | None, until: str | None = None) -> list[dict]:
    """Compute issue state across overlapping reports, including later partial reviews."""
    issues = {}
    for entry in load_workflow(root).get("reviews", []):
        if entry["sessionId"] == until:
            break
        if entry["stage"] != stage:
            continue
        if episodes and not set(episodes).intersection(entry.get("episodes", [])):
            continue
        path = session_path(root, entry["sessionId"])
        if not path.is_file() or digest(path) != entry["sessionHash"]:
            raise ValueError("historical review receipt changed; cannot discard its issues")
        old = read_json(path)
        receipt = old.get("report", {})
        report_path = local(root, receipt.get("path", "missing"))
        if not report_path.is_file() or digest(report_path) != receipt.get("sha256"):
            raise ValueError("historical issue report changed; cannot discard its issues")
        for issue in read_json(report_path).get("issues", []):
            issues[issue["issueId"]] = issue
    return blocking_issues({"issues": list(issues.values())}, episodes)


def prior_blockers(root: Path, session: dict) -> list[dict]:
    """A fresh report cannot erase unresolved issues merely by omitting them."""
    return tracked_blockers(root, session["stage"], session.get("episodes"), session["sessionId"])


def promise_errors(root: Path, session: dict, report: dict) -> list[str]:
    errors = []
    if session["stage"] not in {"batch", "final"}:
        return errors
    end = max(map(int, session["episodes"]))
    total = read_json(root / ".drama/project-state.json").get("totalEpisodes")
    rows = []
    for name, id_key, due_key in [("foreshadowing.csv", "foreshadow_id", "payoff_by"), ("hooks-ledger.csv", "hook_id", "resolve_by")]:
        path = root / "continuity" / name
        if path.exists():
            with path.open(encoding="utf-8-sig", newline="") as handle:
                for row in csv.DictReader(handle):
                    if row.get(id_key) and int(re.sub(r"\D", "", row.get("setup_episode", "0")) or "0") <= end:
                        rows.append((row[id_key], row, due_key))
    audit = {item.get("id"): item for item in report.get("promiseAudit", [])}
    for promise_id, row, due_key in rows:
        item = audit.get(promise_id)
        if not item:
            errors.append(f"promise audit missing: {promise_id}")
            continue
        due = [int(n) for n in re.findall(r"\d+", row.get(due_key, ""))]
        last_due = max(due) if due else None
        state = item.get("status")
        if state == "future":
            if not last_due or last_due <= end or (total and end >= total):
                errors.append(f"overdue promise cannot be future: {promise_id}")
            if not item.get("owner") or not item.get("plannedRange"):
                errors.append(f"future promise needs owner and planned range: {promise_id}")
        elif state == "resolved":
            errors += evidence_errors(root, item.get("setupEvidence"), session["inputs"])
            errors += evidence_errors(root, item.get("payoffEvidence"), session["inputs"])
        elif not any(i.get("promiseId") == promise_id and i.get("severity") in {"P0", "P1"} for i in report.get("issues", [])):
            errors.append(f"unresolved promise needs a blocking issue: {promise_id}")
    return errors


def report_errors(root: Path, session: dict, report: dict) -> list[str]:
    errors = session_errors(root, session)
    if not session.get("firstRead") or not session.get("contextRevealed"):
        errors.append("both first read and context comparison must be completed")
    if report.get("sessionId") != session["sessionId"] or report.get("stage") != session["stage"]:
        errors.append("review report does not belong to this stage/session")
    if report.get("coverage") != session["coverage"]:
        errors.append("review coverage incomplete or wrong content version")
    if not report.get("reviewer") or report.get("complete") is not True:
        errors.append("review is incomplete")
    checks = report.get("checks", [])
    if {c.get("domain") for c in checks} != DOMAINS[session["stage"]]:
        errors.append("review domain coverage incomplete")
    for check in checks:
        if check.get("result") not in {"pass", "fail", "not_applicable"} or not check.get("reason"):
            errors.append("each check requires result and reason")
        errors += evidence_errors(root, check.get("evidence"), session["inputs"])
        if check.get("result") == "fail" and not check.get("issueIds"):
            errors.append("failed check needs issueIds")
    issues = report.get("issues")
    if not isinstance(issues, list):
        errors.append("issues must be a list; counters are not review evidence")
        issues = []
    ids = [i.get("issueId") for i in issues]
    if len(set(ids)) != len(ids):
        errors.append("duplicate issue ID")
    for previous in prior_blockers(root, session):
        followup = next((issue for issue in issues if issue.get("issueId") == previous["issueId"]), None)
        if not followup:
            errors.append("unresolved issues cannot disappear from a new report: " + previous["issueId"])
        elif followup.get("severity") not in {"P0", "P1"}:
            errors.append("blocking issues require an explicit resolution, not a silent severity downgrade: " + previous["issueId"])
    for issue in issues:
        for field in ("issueId", "severity", "category", "location", "reason", "returnTo", "impactScope", "regressionCheck"):
            if not issue.get(field):
                errors.append(f"review issue missing {field}")
        if issue.get("severity") not in {"P0", "P1", "P2", "P3"}:
            errors.append("invalid issue severity")
        if issue.get("status") not in {"open", "fixed", "accepted_by_user", "wont_fix", "superseded"}:
            errors.append("invalid issue status")
        errors += evidence_errors(root, issue.get("evidence"), session["inputs"])
        if issue.get("status") == "fixed":
            errors += evidence_errors(root, issue.get("retest", {}).get("evidence"), session["inputs"])
    for check in checks:
        if any(i not in ids for i in check.get("issueIds", [])):
            errors.append("check references an unknown issue")
    methods = report.get("methods", [])
    if not methods:
        errors.append("record a method decision or a specific reason to skip it")
    for method in methods:
        if method.get("status") not in {"applied", "skipped"} or not method.get("reason"):
            errors.append("method needs applied/skipped and reason")
        if method.get("status") == "applied":
            if not all(method.get(k) for k in ("capabilityId", "decisionId", "action", "changedDecision")):
                errors.append("applied method needs capability, decision ID, action and actual changed decision")
            errors += evidence_errors(root, method.get("evidence"), session["inputs"])
    errors += promise_errors(root, session, report)
    return errors


def record_review(root: Path, session_id: str, report_path: Path) -> dict:
    path = session_path(root, session_id)
    session, report = read_json(path), read_json(report_path)
    if session.get("report"):
        raise ValueError("review session already submitted; use a new session after revision")
    errors = report_errors(root, session, report)
    if errors:
        raise ValueError("; ".join(errors))
    saved = path.parent / "report.json"
    save_json(saved, report)
    blocked = blocking_issues(report)
    session["report"] = {"path": str(saved.relative_to(root)), "sha256": digest(saved)}
    session["status"] = "blocked" if blocked else "passed"
    session["openBlockingIssues"] = len(blocked)
    session["completedAt"] = now()
    save_json(path, session)
    workflow = load_workflow(root)
    workflow.setdefault("reviews", []).append({"sessionId": session_id, "stage": session["stage"],
                                                "episodes": session["episodes"], "sessionHash": digest(path)})
    workflow["phase"] = "revision" if blocked else ("awaiting_outline_confirmation" if session["stage"] == "outline" else session["stage"] + "_reviewed")
    save_json(root / ".drama/workflow.json", workflow)
    if not blocked and session["stage"] == "batch":
        approve_artifacts(root, ["episodeMatrix"])
    return session


def approve_artifacts(root: Path, keys: list[str]) -> None:
    """Mirror real review/confirmation evidence into the existing artifact index."""
    state_path, index_path = root / ".drama/project-state.json", root / ".drama/artifact-index.json"
    state, index = read_json(state_path), read_json(index_path)
    altered = False
    for key in keys:
        item = index.get("artifacts", {}).get(key)
        if not item or not local(root, item["path"]).is_file():
            continue
        content_hash = digest(local(root, item["path"]))
        if item.get("status") == "approved" and item.get("contentHash") == content_hash:
            continue
        if item.get("contentHash") and item["contentHash"] != content_hash:
            item["revision"] += 1
        item.update(status="approved", contentHash=content_hash)
        state["artifacts"][key] = {field: item[field] for field in ("path", "revision", "status", "dependsOn")}
        altered = True
    if altered:
        state["projectRevision"] = index["projectRevision"] = max(state["projectRevision"], index["projectRevision"]) + 1
        save_json(state_path, state)
        save_json(index_path, index)


def current_review(root: Path, stage: str, episodes: list[str] | None = None) -> tuple[dict | None, list[str]]:
    workflow = load_workflow(root)
    required = set(episodes or [])
    for entry in reversed(workflow.get("reviews", [])):
        if entry.get("stage") != stage or not required.issubset(set(entry.get("episodes", []))):
            continue
        path = session_path(root, entry["sessionId"])
        if not path.exists() or digest(path) != entry.get("sessionHash"):
            return None, [f"{stage} review receipt changed"]
        session = read_json(path)
        errors = session_errors(root, session)
        if not set(LOCK_INPUTS).issubset(session.get("inputs", {})):
            errors.append(f"{stage} review does not bind current locked project inputs; reread this version")
        receipt = session.get("report", {})
        report_path = local(root, receipt.get("path", "missing"))
        if not report_path.is_file() or digest(report_path) != receipt.get("sha256"):
            return None, [f"{stage} report changed or missing"]
        report = read_json(report_path)
        errors += report_errors(root, session, report)
        if blocking_issues(report, episodes):
            errors.append(f"{stage} review has blocking issues")
        latest_blockers = tracked_blockers(root, stage, episodes)
        if latest_blockers:
            errors.append(f"{stage} has unresolved issues in current overlapping reviews: " + ", ".join(issue["issueId"] for issue in latest_blockers))
        return session, errors
    return None, [f"missing complete current {stage} review"]


def gate_errors(root: Path, stage: str) -> list[str]:
    try:
        return current_review(root, stage)[1]
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"{stage} review invalid: {exc}"]


def confirm_outline(root: Path, decision: str, quote: str, message_ref: str, scope: str) -> dict:
    workflow = load_workflow(root)
    if not quote.strip() or not message_ref.strip() or not scope.strip():
        raise ValueError("confirmation needs the actual user quote, message reference and scope")
    if decision == "confirm":
        errors = source_errors(root) + gate_errors(root, "treatment") + gate_errors(root, "outline")
        if errors:
            raise ValueError("; ".join(errors))
    receipt = {"decision": decision, "userQuote": quote, "messageRef": message_ref,
               "scope": scope, "recordedAt": now(), "inputs": snapshots(root, [SOURCE, TREATMENT, "04-story-bible.md", OUTLINE, *LOCK_INPUTS])}
    workflow.setdefault("confirmationHistory", []).append(receipt)
    workflow["outlineConfirmation"] = receipt if decision == "confirm" else None
    workflow["phase"] = "outline_confirmed" if decision == "confirm" else "outline_revision"
    save_json(root / ".drama/workflow.json", workflow)
    if decision == "confirm":
        approve_artifacts(root, ["storyTreatment", "storyBible", "seasonArchitecture"])
    return receipt


def writing_errors(root: Path) -> list[str]:
    try:
        workflow = load_workflow(root)
        errors = source_errors(root) + gate_errors(root, "treatment") + gate_errors(root, "outline")
        confirmation = workflow.get("outlineConfirmation")
        if not confirmation or confirmation.get("decision") != "confirm":
            errors.append("awaiting explicit user confirmation of this outline version")
        elif not set(LOCK_INPUTS).issubset(confirmation.get("inputs", {})):
            errors.append("outline confirmation missing locked project inputs; reread and confirm this version")
        elif changed_inputs(root, confirmation.get("inputs", {})):
            errors.append("outline confirmation stale; re-review and obtain explicit confirmation of the changed version")
        return errors
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"writing gate: {exc}"]


def validate_episode_review(root: Path, number: str) -> list[str]:
    errors = writing_errors(root)
    try:
        number = episode_id(number)
        _, issues = current_review(root, "batch", [number])
        errors += issues
        state = read_json(root / ".drama/project-state.json")
        episode = state.get("episodes", {}).get(number, {})
        if episode.get("status") == "approved":
            artifacts = read_json(root / ".drama/artifact-index.json").get("artifacts", {})
            for key, field in (("storyBible", "basedOnStoryBibleRevision"), ("episodeMatrix", "basedOnMatrixRevision")):
                item = artifacts.get(key, {})
                if item.get("status") == "stale" or item.get("revision") != episode.get(field):
                    errors.append(f"EP{number} approval uses obsolete {key} revision")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"batch review invalid: {exc}")
    return errors


def semantic_errors(root: Path, number: str) -> list[str]:
    number = episode_id(number)
    path, script = root / f".drama/polish/EP{number}.json", root / f"episodes/EP{number}.md"
    if not path.is_file():
        return [f"EP{number} missing final semantic/polish review"]
    from polish_guard import validate_record
    return [f"EP{number}: {error}" for error in validate_record(script, path)]


def validate_release(project: Path, episodes: list[str], front_matter: Path | None = None) -> list[str]:
    root = project.resolve()
    errors = writing_errors(root)
    try:
        ids = [episode_id(n) for n in episodes]
        numbers = list(map(int, ids))
        if not ids or len(set(ids)) != len(ids) or numbers != list(range(min(numbers), max(numbers) + 1)):
            errors.append("delivery range must be ordered, unique and contiguous")
        state = read_json(root / ".drama/project-state.json")
        total = state.get("totalEpisodes")
        if not total or (numbers and max(numbers) > total):
            errors.append("delivery range requires the correct total episode count")
        for number in ids:
            episode = state.get("episodes", {}).get(number, {})
            if episode.get("status") != "approved":
                errors.append(f"EP{number} is not approved")
            errors += validate_episode_review(root, number)
            errors += semantic_errors(root, number)
        final, final_errors = current_review(root, "final", ids)
        errors += final_errors
        if not front_matter:
            errors.append("formal delivery requires reviewed front matter")
        elif final:
            relative = str(front_matter.resolve().relative_to(root))
            if final.get("frontMatter") != relative or relative not in final["inputs"]:
                errors.append("front matter was not included in this final review")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        errors.append(f"release gate: {exc}")
    return list(dict.fromkeys(errors))


def synchronize(root: Path) -> dict:
    """Persist invalidation discovered on resume; never mark a draft approved."""
    workflow = load_workflow(root)
    confirmation = workflow.get("outlineConfirmation")
    detected = set(changed_inputs(root, confirmation.get("inputs", {}))) if confirmation else set()
    missing_locks = set(LOCK_INPUTS) - set(confirmation.get("inputs", {})) if confirmation else set()
    detected.update(missing_locks)
    if confirmation and (detected or missing_locks):
        workflow["outlineConfirmation"] = None
        workflow["phase"] = "outline_revision"
        workflow.setdefault("events", []).append({"at": now(), "kind": "outline_confirmation_invalidated", "changed": sorted(detected)})
        save_json(root / ".drama/workflow.json", workflow)
    elif any(entry.get("stage") == "outline" for entry in workflow.get("reviews", [])) and gate_errors(root, "outline"):
        workflow["phase"] = "outline_revision"
        save_json(root / ".drama/workflow.json", workflow)
    state_path, index_path = root / ".drama/project-state.json", root / ".drama/artifact-index.json"
    state, index = read_json(state_path), read_json(index_path)
    changed = bool(detected)
    stale_episodes = []
    for number, episode in state.get("episodes", {}).items():
        review_errors = validate_episode_review(root, number) if episode.get("status") == "approved" else []
        if episode.get("status") == "approved" and review_errors:
            episode["status"] = "stale"
            changed = True
            stale_episodes.append("EP" + number)
            detected.update(error.split("review inputs changed: ", 1)[1] for error in review_errors if "review inputs changed: " in error)
            for key in (f"episode{number}Script", f"episode{number}Review"):
                for obj in (state, index):
                    if key in obj.get("artifacts", {}):
                        obj["artifacts"][key]["status"] = "stale"
    if changed:
        from impact_analysis import calculate
        artifacts = index.get("artifacts", {})
        known_paths = {item["path"] for item in artifacts.values()}
        direct, indirect = calculate(detected & known_paths, artifacts)
        for key, item in artifacts.items():
            if item["path"] in detected | direct | indirect:
                item["status"] = "stale"
                state["artifacts"][key]["status"] = "stale"
        revision = max(state["projectRevision"], index["projectRevision"]) + 1
        state["projectRevision"] = index["projectRevision"] = revision
        save_json(state_path, state)
        save_json(index_path, index)
        event = {"schemaVersion": VERSION, "eventId": "INV-" + uuid.uuid4().hex[:12], "timestamp": now(),
                 "changed": sorted(detected), "direct": sorted(direct), "indirect": sorted(indirect), "episodes": stale_episodes,
                 "applied": True, "reason": "resume detected stale content-bound reviews; no prose was rewritten"}
        with (root / ".drama/invalidation-log.jsonl").open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(event, ensure_ascii=False) + "\n")
    return {"phase": workflow["phase"], "writingErrors": writing_errors(root),
            "episodes": {n: e["status"] for n, e in state.get("episodes", {}).items()}}
