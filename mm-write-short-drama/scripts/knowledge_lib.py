#!/usr/bin/env python3
"""Shared, dependency-free helpers for the personal screenwriting knowledge base."""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import unicodedata
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any, Iterable


REQUIRED_FIELDS = (
    "id",
    "title",
    "rule",
    "rationale",
    "category",
    "stage",
    "genre",
    "production_mode",
    "priority",
    "exceptions",
    "positive_example",
    "negative_example",
    "source",
    "status",
    "version",
)

STAGES = {"planning", "structure", "episode", "scene", "dialogue", "review", "adaptation", "all"}
PRIORITIES = {"hard", "preferred", "optional", "experimental"}
STATUSES = {"draft", "active", "pending-conflict", "duplicate", "rejected", "deprecated", "archived"}
PRODUCTION_MODES = {"live-action", "ai", "hybrid", "unspecified", "all"}
BUILTIN_KB = Path(__file__).resolve().parents[1] / "knowledge-base"

CATEGORY_RULES = (
    ("去 AI 味", "review", ("ai味", "ai 味", "机器味", "模板腔", "解释腔")),
    ("对白与潜台词", "dialogue", ("对白", "台词", "潜台词", "口语", "声纹", "说话")),
    ("小说改编", "adaptation", ("改编", "原著", "小说", "忠实", "压缩")),
    ("分集与卡点", "episode", ("分集", "卡点", "追看", "付费点", "集尾", "前三集")),
    ("短剧开场", "episode", ("开场", "前十秒", "前3秒", "前三秒", "开篇")),
    ("反转悬念伏笔", "structure", ("反转", "悬念", "伏笔", "回收", "秘密")),
    ("场景设计", "scene", ("场景", "场次", "调度", "动作", "阻力")),
    ("人物与关系", "planning", ("人物", "角色", "关系", "主角", "反派", "人物弧")),
    ("冲突与升级", "structure", ("冲突", "升级", "对抗", "代价", "压力")),
    ("情绪节奏", "scene", ("情绪", "节奏", "铺垫", "爆发", "停顿")),
    ("真人制作", "review", ("拍摄", "演员", "预算", "场地", "真人制作")),
    ("AI 制作", "review", ("生成", "同框", "一致性", "ai制作", "ai 制作")),
)

PREFIXES = {
    "去 AI 味": "STYLE",
    "对白与潜台词": "DIALOGUE",
    "小说改编": "ADAPT",
    "分集与卡点": "EPISODE",
    "短剧开场": "OPENING",
    "反转悬念伏笔": "HOOK",
    "场景设计": "SCENE",
    "人物与关系": "CHAR",
    "冲突与升级": "CONFLICT",
    "情绪节奏": "EMOTION",
    "真人制作": "LIVE",
    "AI 制作": "AI",
    "通用编剧原则": "RULE",
}

CARD_RE = re.compile(
    r"<!--\s*knowledge-card:start\s*-->\s*```json\s*(\{.*?\})\s*```\s*<!--\s*knowledge-card:end\s*-->",
    re.S | re.I,
)
NEGATIVE_MARKERS = ("不得", "不能", "不要", "避免", "禁止", "不应", "无需", "不必", "不可")
MODAL_MARKERS = NEGATIVE_MARKERS + ("必须", "应当", "应该", "需要", "优先", "可以", "建议", "最好", "尽量")


def now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


def ensure_layout(root: Path) -> Path:
    root = root.expanduser().resolve()
    for name in ("inbox", "sources", "cards", "index", "conflicts", "archive"):
        (root / name).mkdir(parents=True, exist_ok=True)
    for relative, default in (
        ("index/cards.jsonl", ""),
        ("index/terms.jsonl", ""),
        ("index/ingest-log.jsonl", ""),
        ("conflicts/open.jsonl", ""),
        ("conflicts/duplicates.jsonl", ""),
        ("conflicts/resolutions.jsonl", ""),
    ):
        path = root / relative
        if not path.exists():
            path.write_text(default, encoding="utf-8")
    return root


def resolve_kb(value: str | Path | None) -> Path:
    if value:
        return ensure_layout(Path(value))
    for base in (Path.cwd(), *Path.cwd().parents):
        candidate = base / "knowledge-base"
        if candidate.is_dir():
            return ensure_layout(candidate)
    raise FileNotFoundError("knowledge-base not found; pass --kb /path/to/knowledge-base")


def search_roots(value: str | Path | None, include_builtin: bool = True) -> list[Path]:
    """Find personal data without creating directories; bundled rules are a fallback."""
    roots: list[Path] = []
    if value:
        personal = Path(value).expanduser().resolve()
        if not personal.is_dir():
            raise FileNotFoundError(f"knowledge-base not found: {personal}")
        roots.append(personal)
    else:
        for base in (Path.cwd(), *Path.cwd().parents):
            candidate = base / "knowledge-base"
            if candidate.is_dir():
                roots.append(candidate.resolve())
                break
    if include_builtin and BUILTIN_KB.is_dir() and BUILTIN_KB.resolve() not in roots:
        roots.append(BUILTIN_KB.resolve())
    if not roots:
        raise FileNotFoundError("knowledge-base not found; pass --kb /path/to/knowledge-base")
    return roots


def normalize_text(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).lower()
    return re.sub(r"[^\w\u4e00-\u9fff]+", "", value)


def tokenize(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKC", value).lower()
    words = set(re.findall(r"[a-z0-9_]{2,}", normalized))
    cjk_runs = re.findall(r"[\u4e00-\u9fff]+", normalized)
    for run in cjk_runs:
        words.update(run)
        if len(run) > 1:
            words.update(run[index : index + 2] for index in range(len(run) - 1))
    return words


def list_value(value: Any, default: str = "all") -> list[str]:
    if value is None or value == "":
        return [default]
    if isinstance(value, list):
        result = [str(item).strip() for item in value if str(item).strip()]
        return result or [default]
    return [item.strip() for item in re.split(r"[,，、/|]", str(value)) if item.strip()] or [default]


def classify(rule: str) -> tuple[str, list[str], list[str]]:
    lowered = rule.lower()
    for category, stage, keywords in CATEGORY_RULES:
        if any(keyword in lowered for keyword in keywords):
            production = ["ai"] if category == "AI 制作" else ["live-action"] if category == "真人制作" else ["all"]
            return category, [stage], production
    return "通用编剧原则", ["all"], ["all"]


def make_id(category: str, rule: str) -> str:
    prefix = PREFIXES.get(category, "RULE")
    digest = hashlib.sha256(normalize_text(rule).encode("utf-8")).hexdigest()[:10].upper()
    return f"{prefix}-{digest}"


def render_card(card: dict[str, Any]) -> str:
    title = str(card.get("title") or card.get("id") or "知识卡")
    payload = json.dumps(card, ensure_ascii=False, indent=2, sort_keys=False)
    return (
        f"# {title}\n\n"
        "<!-- knowledge-card:start -->\n"
        "```json\n"
        f"{payload}\n"
        "```\n"
        "<!-- knowledge-card:end -->\n\n"
        "## 人工备注\n\n"
        "- 待验证问题：\n"
        "- 适用边界：\n"
    )


def read_card(path: Path) -> dict[str, Any]:
    text = path.read_text(encoding="utf-8-sig")
    match = CARD_RE.search(text)
    if not match:
        raise ValueError("missing knowledge-card JSON block")
    data = json.loads(match.group(1))
    if not isinstance(data, dict):
        raise ValueError("knowledge card payload must be an object")
    data["_path"] = str(path)
    return data


def write_new_card(root: Path, card: dict[str, Any]) -> Path:
    path = root / "cards" / f"{card['id']}.md"
    if path.exists():
        raise FileExistsError(f"refusing to overwrite existing card: {path}")
    path.write_text(render_card(card), encoding="utf-8")
    return path


def archive_and_update(root: Path, card: dict[str, Any], updates: dict[str, Any]) -> Path:
    path = Path(card["_path"])
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    archive = root / "archive" / f"{card['id']}-v{card['version']}-{stamp}.md"
    if archive.exists():
        archive = root / "archive" / f"{card['id']}-v{card['version']}-{stamp}-{hashlib.sha1(path.read_bytes()).hexdigest()[:6]}.md"
    shutil.copy2(path, archive)
    clean = {key: value for key, value in card.items() if key != "_path"}
    clean.update(updates)
    clean["version"] = int(card.get("version", 1)) + 1
    clean["updated_at"] = now_iso()
    path.write_text(render_card(clean), encoding="utf-8")
    return archive


def iter_cards(root: Path) -> Iterable[dict[str, Any]]:
    for path in sorted((root / "cards").glob("*.md")):
        if path.name.lower() in {"readme.md", "card-template.md"}:
            continue
        yield read_card(path)


def append_jsonl(path: Path, record: dict[str, Any]) -> None:
    with path.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(record, ensure_ascii=False, sort_keys=False) + "\n")


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    records = []
    for number, line in enumerate(path.read_text(encoding="utf-8-sig").splitlines(), 1):
        if not line.strip():
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{number}: invalid JSON: {exc}") from exc
        if not isinstance(item, dict):
            raise ValueError(f"{path}:{number}: JSONL record must be an object")
        records.append(item)
    return records


def scope_overlap(left: dict[str, Any], right: dict[str, Any]) -> bool:
    for key in ("stage", "genre", "production_mode"):
        a = set(list_value(left.get(key)))
        b = set(list_value(right.get(key)))
        if "all" not in a and "all" not in b and not a.intersection(b):
            return False
    return True


def similarity(left: str, right: str) -> float:
    a, b = normalize_text(left), normalize_text(right)
    if not a or not b:
        return 0.0
    sequence = SequenceMatcher(None, a, b).ratio()
    ta, tb = tokenize(left), tokenize(right)
    jaccard = len(ta & tb) / max(1, len(ta | tb))
    return max(sequence, jaccard)


def conflict_similarity(left: str, right: str) -> float:
    def core(value: str) -> str:
        for marker in MODAL_MARKERS:
            value = value.replace(marker, "")
        return value
    return similarity(core(left), core(right))


def is_conflict(left: dict[str, Any], right: dict[str, Any]) -> tuple[bool, float, str]:
    if not scope_overlap(left, right):
        return False, 0.0, "scope-does-not-overlap"
    left_negative = any(marker in str(left.get("rule", "")) for marker in NEGATIVE_MARKERS)
    right_negative = any(marker in str(right.get("rule", "")) for marker in NEGATIVE_MARKERS)
    score = conflict_similarity(str(left.get("rule", "")), str(right.get("rule", "")))
    if left_negative != right_negative and score >= 0.52:
        return True, score, "opposite-modality-with-overlapping-scope"
    return False, score, "no-machine-detected-conflict"


def rebuild_index(root: Path) -> tuple[int, int]:
    cards = []
    terms: dict[str, list[str]] = {}
    for card in iter_cards(root):
        clean = {key: value for key, value in card.items() if key != "_path"}
        clean["card_path"] = str(Path(card["_path"]).relative_to(root.parent))
        search_text = " ".join(
            str(clean.get(key, ""))
            for key in ("id", "title", "rule", "rationale", "category", "stage", "genre", "production_mode", "exceptions", "capability_id", "triggers", "diagnosis", "action", "self_check")
        )
        clean["search_terms"] = sorted(tokenize(search_text))
        cards.append(clean)
        for term in clean["search_terms"]:
            terms.setdefault(term, []).append(str(clean["id"]))
    cards.sort(key=lambda item: str(item["id"]))
    index_path = root / "index" / "cards.jsonl"
    index_path.write_text(
        "".join(json.dumps(card, ensure_ascii=False, sort_keys=False) + "\n" for card in cards),
        encoding="utf-8",
    )
    (root / "index" / "terms.jsonl").write_text(
        "".join(
            json.dumps({"term": term, "rule_ids": rule_ids}, ensure_ascii=False) + "\n"
            for term, rule_ids in sorted(terms.items())
        ),
        encoding="utf-8",
    )
    return len(cards), len(terms)


def source_record(root: Path, original_name: str, content: bytes, suffix: str) -> dict[str, str]:
    digest = hashlib.sha256(content).hexdigest()
    date = datetime.now().strftime("%Y%m%d")
    source_id = f"SRC-{date}-{digest[:12].upper()}"
    safe_name = re.sub(r"[^A-Za-z0-9._\-\u4e00-\u9fff]+", "-", Path(original_name).name).strip("-") or f"source{suffix}"
    stored = root / "sources" / f"{source_id}--{safe_name}"
    if stored.exists():
        if hashlib.sha256(stored.read_bytes()).hexdigest() != digest:
            raise RuntimeError(f"immutable source collision: {stored}")
    else:
        stored.write_bytes(content)
    return {
        "source_id": source_id,
        "stored_path": str(stored.relative_to(root.parent)),
        "original_name": original_name,
        "sha256": digest,
        "captured_at": now_iso(),
    }


def relative_or_absolute(path: Path, base: Path) -> str:
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path.resolve())
