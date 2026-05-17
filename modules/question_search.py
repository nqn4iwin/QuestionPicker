"""Semantic question search with local sentence embeddings (no LLM API)."""

from __future__ import annotations

import hashlib
import json
import pickle
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_MODEL = "jhgan/ko-sroberta-multitask"
FALLBACK_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"


def question_search_text(question: dict[str, Any]) -> str:
    """Text blob used for embedding one question."""
    parts: list[str] = []
    content = question.get("content")
    if isinstance(content, str) and content.strip():
        parts.append(content.strip())
    choices = question.get("choices", [])
    if isinstance(choices, list):
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            text = choice.get("text")
            if isinstance(text, str) and text.strip():
                parts.append(text.strip())
    return "\n".join(parts)


def _cache_path(json_path: Path, model_name: str) -> Path:
    digest = hashlib.sha256(
        f"{json_path.resolve()}|{json_path.stat().st_mtime_ns}|{model_name}".encode()
    ).hexdigest()[:16]
    return json_path.parent / f".{json_path.stem}.embeddings.{digest}.pkl"


def _load_encoder(model_name: str):
    from sentence_transformers import SentenceTransformer

    try:
        return SentenceTransformer(model_name)
    except Exception:
        if model_name != FALLBACK_MODEL:
            return SentenceTransformer(FALLBACK_MODEL)
        raise


def _encode(model, texts: list[str]) -> np.ndarray:
    vectors = model.encode(
        texts,
        normalize_embeddings=True,
        show_progress_bar=False,
    )
    return np.asarray(vectors, dtype=np.float32)


def _load_or_build_index(
    json_path: Path,
    model_name: str,
    *,
    rebuild: bool = False,
) -> tuple[list[int], list[str], np.ndarray, str]:
    document = json.loads(json_path.read_text(encoding="utf-8"))
    questions = document.get("questions", [])
    if not isinstance(questions, list):
        raise ValueError("JSON has no questions array")

    numbers: list[int] = []
    texts: list[str] = []
    for question in questions:
        if not isinstance(question, dict):
            continue
        number = int(question["no"])
        blob = question_search_text(question)
        if not blob.strip():
            continue
        numbers.append(number)
        texts.append(blob)

    if not texts:
        raise ValueError("No question text to embed")

    cache = _cache_path(json_path, model_name)
    if not rebuild and cache.is_file():
        with cache.open("rb") as handle:
            cached = pickle.load(handle)
        if (
            cached.get("numbers") == numbers
            and cached.get("texts") == texts
            and cached.get("model") == model_name
        ):
            return numbers, texts, cached["embeddings"], model_name

    model = _load_encoder(model_name)
    used_model = getattr(model, "model_name", None) or model_name
    embeddings = _encode(model, texts)
    with cache.open("wb") as handle:
        pickle.dump(
            {
                "numbers": numbers,
                "texts": texts,
                "embeddings": embeddings,
                "model": used_model,
            },
            handle,
        )
    return numbers, texts, embeddings, used_model


def search_questions(
    json_path: Path | str,
    topic: str,
    *,
    model_name: str = DEFAULT_MODEL,
    top_k: int | None = None,
    min_score: float = 0.28,
    rebuild_index: bool = False,
) -> dict[str, Any]:
    """Return ranked matches and a filtered document subset."""
    path = Path(json_path).resolve()
    topic = topic.strip()
    if not topic:
        raise ValueError("topic must not be empty")

    numbers, _texts, matrix, used_model = _load_or_build_index(
        path, model_name, rebuild=rebuild_index
    )

    model = _load_encoder(used_model if used_model else model_name)
    query = _encode(model, [topic])[0]
    scores = matrix @ query

    ranked = sorted(
        zip(numbers, scores.tolist(), strict=True),
        key=lambda item: item[1],
        reverse=True,
    )
    if top_k is not None:
        ranked = ranked[:top_k]

    matches = [
        {"no": number, "score": round(float(score), 4)}
        for number, score in ranked
        if score >= min_score
    ]
    selected = {item["no"] for item in matches}

    document = json.loads(path.read_text(encoding="utf-8"))
    questions = document.get("questions", [])
    filtered_questions = [
        question
        for question in questions
        if isinstance(question, dict) and int(question.get("no", -1)) in selected
    ]
    filtered_questions.sort(key=lambda q: int(q["no"]))

    answer_key = document.get("answer_key", [])
    filtered_answers = [
        item
        for item in answer_key
        if isinstance(item, dict) and int(item.get("no", -1)) in selected
    ]

    meta = document.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}
    meta = {
        **meta,
        "search_topic": topic,
        "search_model": used_model,
        "search_min_score": min_score,
        "search_match_count": len(matches),
    }

    return {
        "meta": meta,
        "questions": filtered_questions,
        "answer_key": filtered_answers,
        "search": {
            "topic": topic,
            "model": used_model,
            "min_score": min_score,
            "matches": matches,
        },
    }


def write_filtered_document(
    document: dict[str, Any],
    output_path: Path | str,
) -> Path:
    dest = Path(output_path).resolve()
    dest.write_text(
        json.dumps(document, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return dest
