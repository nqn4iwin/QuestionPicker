"""Apply text normalization to a full exam JSON document."""

from __future__ import annotations

import json
from copy import deepcopy
from pathlib import Path
from typing import Any

from modules.text_normalize import Correction, normalize_exam_text


def _normalize_field(
    value: str,
    *,
    use_kiwi: bool,
) -> tuple[str, list[Correction]]:
    if not value.strip():
        return value, []
    if value.isascii() and not any("\uac00" <= char <= "\ud7a3" for char in value):
        return value, []
    return normalize_exam_text(value, use_kiwi=use_kiwi)


def normalize_document(
    document: dict[str, Any],
    *,
    use_kiwi: bool = False,
) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    doc = deepcopy(document)
    log: list[dict[str, Any]] = []

    questions = doc.get("questions", [])
    if not isinstance(questions, list):
        return doc, log

    for question in questions:
        if not isinstance(question, dict):
            continue
        number = int(question["no"])

        content = question.get("content")
        if isinstance(content, str):
            new_content, fixes = _normalize_field(content, use_kiwi=use_kiwi)
            if new_content != content:
                question["content"] = new_content
            for fix in fixes:
                log.append(
                    {
                        "no": number,
                        "field": "content",
                        **fix.as_dict(),
                    }
                )

        choices = question.get("choices", [])
        if isinstance(choices, list):
            for choice in choices:
                if not isinstance(choice, dict):
                    continue
                text = choice.get("text")
                if not isinstance(text, str):
                    continue
                new_text, fixes = _normalize_field(text, use_kiwi=use_kiwi)
                if new_text != text:
                    choice["text"] = new_text
                for fix in fixes:
                    log.append(
                        {
                            "no": number,
                            "field": f"choice_{choice.get('choice', '?')}",
                            **fix.as_dict(),
                        }
                    )

    meta = doc.setdefault("meta", {})
    if isinstance(meta, dict):
        meta["normalizer"] = "normalize_json (punctuation + optional kiwipiepy)"
        meta["correction_count"] = len(log)

    doc["corrections"] = log
    return doc, log


def normalize_json_file(
    input_path: Path | str,
    output_path: Path | str | None = None,
    *,
    use_kiwi: bool = False,
) -> tuple[Path, list[dict[str, Any]]]:
    src = Path(input_path).resolve()
    if not src.is_file():
        raise FileNotFoundError(src)

    dest = Path(output_path) if output_path else src.with_name(f"{src.stem}.corrected.json")

    document = json.loads(src.read_text(encoding="utf-8"))
    normalized, log = normalize_document(document, use_kiwi=use_kiwi)

    meta = normalized.get("meta")
    if isinstance(meta, dict):
        meta["normalized_from"] = src.name

    dest.write_text(
        json.dumps(normalized, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return dest, log
