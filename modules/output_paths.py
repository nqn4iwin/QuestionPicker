"""Default output paths: json/ and docx/ with MMDD-HHMM-topic filenames."""

from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path

JSON_DIR = Path("json")
DOCX_DIR = Path("docx")

_FORBIDDEN = re.compile(r'[<>:"/\\|?*\x00-\x1f]')


def slugify_label(text: str, *, max_len: int = 40) -> str:
    """Filesystem-safe label; keeps Korean letters and digits."""
    label = _FORBIDDEN.sub("", text.strip())
    label = re.sub(r"\s+", "", label)
    if not label:
        return "untitled"
    return label[:max_len]


def timestamp_prefix(when: datetime | None = None) -> str:
    when = when or datetime.now()
    return when.strftime("%m%d-%H%M")


def ensure_output_dirs() -> None:
    JSON_DIR.mkdir(parents=True, exist_ok=True)
    DOCX_DIR.mkdir(parents=True, exist_ok=True)


def default_json_path(
    *,
    topic: str | None = None,
    stem: str | None = None,
    suffix: str = "",
) -> Path:
    """e.g. json/0518-1634-윈도우10.json or json/0518-1634-example.json"""
    ensure_output_dirs()
    prefix = timestamp_prefix()
    if topic is not None:
        label = slugify_label(topic)
    elif stem is not None:
        label = slugify_label(stem)
    else:
        label = "output"
    extra = f"-{suffix}" if suffix else ""
    return JSON_DIR / f"{prefix}-{label}{extra}.json"


def default_docx_path(
    *,
    json_path: Path | None = None,
    topic: str | None = None,
    stem: str | None = None,
) -> Path:
    """Match JSON stem when given; else same naming rule as default_json_path."""
    ensure_output_dirs()
    if json_path is not None:
        return DOCX_DIR / f"{json_path.stem}.docx"
    prefix = timestamp_prefix()
    if topic is not None:
        label = slugify_label(topic)
    elif stem is not None:
        label = slugify_label(stem)
    else:
        label = "output"
    return DOCX_DIR / f"{prefix}-{label}.docx"


def find_latest_json_for_stem(stem: str) -> Path | None:
    """Newest json/*-{stem}.json from a PDF extract (not search-only names)."""
    ensure_output_dirs()
    pattern = f"*-{slugify_label(stem)}.json"
    candidates = sorted(
        JSON_DIR.glob(pattern),
        key=lambda path: path.stat().st_mtime,
        reverse=True,
    )
    return candidates[0] if candidates else None


def topic_from_document(json_path: Path) -> str | None:
    try:
        data = json.loads(json_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    search = data.get("search")
    if isinstance(search, dict):
        topic = search.get("topic")
        if isinstance(topic, str) and topic.strip():
            return topic.strip()
    meta = data.get("meta")
    if isinstance(meta, dict):
        topic = meta.get("search_topic")
        if isinstance(topic, str) and topic.strip():
            return topic.strip()
    return None
