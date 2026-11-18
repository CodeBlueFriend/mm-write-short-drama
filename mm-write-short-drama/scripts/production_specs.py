"""User-selected production constraints, separate from the story's actual episode plan."""
from __future__ import annotations

import copy
import hashlib
import json
import re
from datetime import datetime, timezone
from pathlib import Path

SPECS = ".drama/production-specs.json"
PLAN = ".drama/episode-plan.json"
MODES = ("live_action", "ai_drama")
FIELDS = ("productionMode", "duration", "episodeCountPreference")


def profiles() -> dict:
    return read_json(Path(__file__).resolve().parent.parent / "assets/production-profiles.json")


def read_json(path: Path) -> dict:
    value = json.loads(path.read_text(encoding="utf-8-sig"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path.name}")
    return value


def save_json(path: Path, value: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def empty_specs() -> dict:
    return {"schemaVersion": "1.0.0", "policyVersion": profiles()["policyVersion"],
            "productionMode": None, "duration": None, "episodeCountPreference": None,
            "selections": {}}


def empty_plan() -> dict:
    return {"schemaVersion": "1.0.0", "plannedTotalEpisodes": None, "planReason": None,
            "specsHash": None, "plannedAt": None}


def positive(value: int) -> bool:
    return type(value) is int and value > 0


def parse_episode_count(raw: str) -> dict:
    value = re.sub(r"\s+", "", raw)
    value = re.sub(r"^(?:大概|大约|约|预计|期望)", "", value)
    value = re.sub(r"(?:左右|上下|集)$", "", value)
    value = re.sub(r"(?:左右|上下|集)$", "", value)
    match = re.fullmatch(r"(\d+)(?:[-—–~～至到](\d+))?", value)
    if not match or int(match[1]) < 1 or (match[2] and int(match[2]) < int(match[1])):
        raise ValueError("episode count must be positive: e.g. 60, 约60集, or 40-60")
    first, last = int(match[1]), int(match[2]) if match[2] else None
    return {"kind": "range" if last is not None else "target", "raw": raw,
            "target": first if last is None else None, "min": first if last is not None else None,
            "max": last, "flexible": True}


def duration_value(mode: str, seconds: int | None, interval: str | None) -> dict:
    if seconds is not None and interval is not None:
        raise ValueError("choose either duration-seconds or duration-range")
    if interval is not None:
        match = re.fullmatch(r"\s*(\d+)\s*[-—–~～至到]\s*(\d+)\s*", interval)
        if not match:
            raise ValueError("duration-range requires positive seconds, e.g. 50-60")
        low, high = map(int, match.groups())
        target = None
    else:
        low = high = target = seconds
    if not positive(low) or not positive(high) or low > high:
        raise ValueError("duration requires positive seconds and an ascending range")
    policy = profiles()["profiles"][mode]
    if high > policy.get("hardMaxSeconds", high):
        raise ValueError("真人短剧单集时长上限为180秒（3分钟）")
    common = policy["commonRangeSeconds"]
    classification = "standard" if common[0] <= low <= high <= common[1] else "custom"
    if high > policy.get("unconventionalAboveSeconds", high):
        classification = "unconventional"
    return {"minSeconds": low, "maxSeconds": high, "targetSeconds": target,
            "classification": classification}


def structure_errors(specs: dict) -> list[str]:
    """Pending choices are valid data; malformed or unreceipted choices are not."""
    errors = []
    if specs.get("schemaVersion") != "1.0.0" or specs.get("policyVersion") != profiles()["policyVersion"]:
        errors.append("production specs schema/policy version requires explicit migration")
    mode = specs.get("productionMode")
    if mode is not None and mode not in MODES:
        errors.append("productionMode must be live_action or ai_drama")
    selections = specs.get("selections")
    if not isinstance(selections, dict):
        return errors + ["production specs selections must be an object"]
    for field in FIELDS:
        value, receipt = specs.get(field), selections.get(field)
        if value is not None:
            if not isinstance(receipt, dict) or receipt.get("value") != value or any(
                not isinstance(receipt.get(k), str) or not receipt[k].strip()
                for k in ("userQuote", "messageRef", "selectedAt")
            ):
                errors.append(f"{field} requires matching actual user selection receipt")
        elif receipt is not None:
            errors.append(f"{field} has a receipt without a selection")
    duration = specs.get("duration")
    if duration is not None:
        try:
            if not isinstance(duration, dict) or mode not in MODES:
                raise ValueError("choose production mode before duration")
            target = duration.get("targetSeconds")
            interval = f'{duration["minSeconds"]}-{duration["maxSeconds"]}' if target is None else None
            if duration_value(mode, target, interval) != duration:
                raise ValueError("duration fields do not agree")
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"invalid duration: {exc}")
    preference = specs.get("episodeCountPreference")
    if preference is not None:
        try:
            if not isinstance(preference, dict) or parse_episode_count(preference["raw"]) != preference:
                raise ValueError("episode count fields do not agree")
        except (KeyError, TypeError, ValueError) as exc:
            errors.append(f"invalid episode count preference: {exc}")
    return errors


def has_selection(specs: dict, field: str) -> bool:
    receipts = specs.get("selections")
    receipt = receipts.get(field) if isinstance(receipts, dict) else None
    return (specs.get(field) is not None and isinstance(receipt, dict)
            and receipt.get("value") == specs[field]
            and all(isinstance(receipt.get(k), str) and receipt[k].strip()
                    for k in ("userQuote", "messageRef", "selectedAt")))


def selection_errors(root: Path, require_plan: bool = False) -> list[str]:
    try:
        specs = read_json(root / SPECS)
        errors = structure_errors(specs)
        labels = {"productionMode": "制作方式（真人短剧或AI剧）", "duration": "单集时长", "episodeCountPreference": "期望集数（具体数或范围，可浮动）"}
        for field in FIELDS:
            if not has_selection(specs, field):
                errors.append(f"production specs awaiting user selection: {labels[field]}")
                break
        state = read_json(root / ".drama/project-state.json")
        if specs.get("productionMode") and state.get("productionMode") != specs["productionMode"]:
            errors.append("project productionMode differs from user selection")
        if require_plan:
            plan = read_json(root / PLAN)
            errors += plan_errors(root, plan, state)
        return errors
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return [f"production specs require user selections: {exc}"]


def spec_hash(root: Path) -> str:
    return hashlib.sha256((root / SPECS).read_bytes()).hexdigest()


def plan_errors(root: Path, plan: dict, state: dict) -> list[str]:
    if not positive(plan.get("plannedTotalEpisodes")):
        return ["episode plan awaiting actual total episode count and planning reason"]
    errors = []
    if plan.get("schemaVersion") != "1.0.0" or not str(plan.get("planReason") or "").strip() or not plan.get("plannedAt"):
        errors.append("episode plan requires valid version, planning reason and date")
    if plan.get("specsHash") != spec_hash(root):
        errors.append("episode plan is stale after production selections changed")
    if state.get("totalEpisodes") != plan["plannedTotalEpisodes"]:
        errors.append("project totalEpisodes differs from actual episode plan")
    return errors


def readiness(root: Path) -> dict:
    try:
        specs = read_json(root / SPECS)
        errors = selection_errors(root)
        missing = next((f for f in FIELDS if not has_selection(specs, f)), None)
        next_required = "episodeCount" if missing == "episodeCountPreference" else missing
        plan = read_json(root / PLAN) if (root / PLAN).is_file() else empty_plan()
        if not missing and not errors and selection_errors(root, require_plan=True):
            next_required = "episodePlan"
        advisory = []
        duration = specs.get("duration")
        if isinstance(duration, dict) and duration.get("classification") == "unconventional":
            advisory.append("所选AI剧时长超过120秒，按用户明确选择保留为非常规方案。")
        return {"status": "pending" if missing or errors else "ready", "nextRequired": next_required,
                **{f: specs.get(f) for f in FIELDS}, "plannedTotalEpisodes": plan.get("plannedTotalEpisodes"),
                "planReason": plan.get("planReason"), "advisories": advisory, "errors": errors,
                "profiles": profiles()["profiles"]}
    except (OSError, ValueError, KeyError, TypeError) as exc:
        return {"status": "pending", "nextRequired": "productionMode", "errors": [str(exc)],
                "profiles": profiles()["profiles"], "advisories": []}


def apply_choices(specs: dict, *, production_mode: str | None = None,
                  duration_seconds: int | None = None, duration_range: str | None = None,
                  episode_count: str | None = None, user_quote: str, message_ref: str) -> dict:
    if not user_quote.strip() or not message_ref.strip():
        raise ValueError("production choices need the actual user quote and message reference")
    if all(v is None for v in (production_mode, duration_seconds, duration_range, episode_count)):
        raise ValueError("supply at least one production choice")
    result = copy.deepcopy(specs)
    if structure_errors(result):
        raise ValueError("invalid existing production specs; repair or explicitly migrate before selecting")
    values = {}
    if production_mode is not None:
        if production_mode not in MODES:
            raise ValueError("choose live_action or ai_drama")
        if result.get("productionMode") != production_mode:
            result["duration"] = None
            result["selections"].pop("duration", None)
            # An existing count preference remains a preference when changing format.
        values["productionMode"] = production_mode
        result["productionMode"] = production_mode
    if duration_seconds is not None or duration_range is not None:
        if result.get("productionMode") not in MODES:
            raise ValueError("choose production mode before duration")
        values["duration"] = duration_value(result["productionMode"], duration_seconds, duration_range)
        result["duration"] = values["duration"]
    if episode_count is not None:
        if result.get("duration") is None:
            raise ValueError("choose duration before episode count")
        values["episodeCountPreference"] = parse_episode_count(episode_count)
    at = datetime.now(timezone.utc).isoformat()
    for field, value in values.items():
        result[field] = value
        result["selections"][field] = {"value": value, "userQuote": user_quote,
                                       "messageRef": message_ref, "selectedAt": at}
    return result


def set_specs(root: Path, **choices) -> dict:
    path = root / SPECS
    specs = read_json(path) if path.is_file() else empty_specs()
    updated = apply_choices(specs, **choices)
    state = read_json(root / ".drama/project-state.json")
    state.update(productionMode=updated.get("productionMode") or "unspecified", totalEpisodes=None)
    save_json(path, updated)
    save_json(root / PLAN, empty_plan())
    save_json(root / ".drama/project-state.json", state)
    # Keep the skeleton's duplicate routing field consistent, without parsing or
    # rewriting the creator's immutable facts elsewhere in the YAML document.
    canon = root / "continuity/canon.yaml"
    if canon.is_file():
        lines = canon.read_text(encoding="utf-8").splitlines(keepends=True)
        in_project = False
        for number, line in enumerate(lines):
            if line.strip() == "project:" and not line.startswith((" ", "\t")):
                in_project = True
                continue
            if in_project and line.strip() and not line.startswith((" ", "\t")):
                break
            if in_project and line.startswith("  productionMode:"):
                lines[number] = "  productionMode: " + json.dumps(state["productionMode"]) + "\n"
                canon.write_text("".join(lines), encoding="utf-8")
                break
    return readiness(root)


def set_plan(root: Path, total: int, reason: str) -> dict:
    errors = selection_errors(root)
    if errors:
        raise ValueError("; ".join(errors))
    if not positive(total) or not reason.strip():
        raise ValueError("episode plan needs positive total-episodes and a non-empty planning reason")
    state = read_json(root / ".drama/project-state.json")
    plan = {"schemaVersion": "1.0.0", "plannedTotalEpisodes": total, "planReason": reason,
            "specsHash": spec_hash(root), "plannedAt": datetime.now(timezone.utc).isoformat()}
    state["totalEpisodes"] = total
    save_json(root / PLAN, plan)
    save_json(root / ".drama/project-state.json", state)
    return readiness(root)
