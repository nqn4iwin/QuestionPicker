"""Semantic question search with local sentence embeddings (no LLM API)."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import numpy as np

DEFAULT_MODEL = "dragonkue/multilingual-e5-small-ko-v2"
FALLBACK_MODEL = "paraphrase-multilingual-MiniLM-L12-v2"
DEFAULT_MIN_SCORE = 0.50


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


def embed_document_questions(
    document: dict[str, Any],
    model_name: str = DEFAULT_MODEL,
) -> str:
    """Embed each question; store vectors on questions and model id in meta."""
    questions = document.get("questions", [])
    if not isinstance(questions, list):
        raise ValueError("JSON has no questions array")

    texts: list[str] = []
    targets: list[dict[str, Any]] = []
    for question in questions:
        if not isinstance(question, dict):
            continue
        blob = question_search_text(question)
        if not blob.strip():
            question.pop("embedding", None)
            continue
        texts.append(blob)
        targets.append(question)

    if not texts:
        raise ValueError("No question text to embed")

    model = _load_encoder(model_name)
    used_model = getattr(model, "model_name", None) or model_name
    vectors = _encode(model, texts)
    for question, vector in zip(targets, vectors, strict=True):
        question["embedding"] = vector.tolist()

    meta = document.get("meta")
    if not isinstance(meta, dict):
        meta = {}
        document["meta"] = meta
    meta["embedding_model"] = used_model
    meta["embedding_dims"] = int(vectors.shape[1])
    return used_model


def document_has_embeddings(document: dict[str, Any]) -> bool:
    questions = document.get("questions", [])
    if not isinstance(questions, list):
        return False
    return any(
        isinstance(question, dict)
        and isinstance(question.get("embedding"), list)
        and question["embedding"]
        for question in questions
    )


def _embedding_matrix(
    document: dict[str, Any],
) -> tuple[list[int], np.ndarray, str]:
    meta = document.get("meta", {})
    if not isinstance(meta, dict):
        meta = {}
    model_name = meta.get("embedding_model")
    if not isinstance(model_name, str) or not model_name:
        raise ValueError(
            "JSON has no embeddings; run pdf_to_json or search with --rebuild-embeddings"
        )

    questions = document.get("questions", [])
    if not isinstance(questions, list):
        raise ValueError("JSON has no questions array")

    numbers: list[int] = []
    rows: list[list[float]] = []
    for question in questions:
        if not isinstance(question, dict):
            continue
        embedding = question.get("embedding")
        if not isinstance(embedding, list) or not embedding:
            continue
        numbers.append(int(question["no"]))
        rows.append(embedding)

    if not rows:
        raise ValueError(
            "JSON has no embeddings; run pdf_to_json or search with --rebuild-embeddings"
        )

    matrix = np.asarray(rows, dtype=np.float32)
    expected_dims = meta.get("embedding_dims")
    if isinstance(expected_dims, int) and matrix.shape[1] != expected_dims:
        raise ValueError(
            f"Embedding dimension mismatch: expected {expected_dims}, got {matrix.shape[1]}"
        )
    return numbers, matrix, model_name


def rebuild_embeddings_in_json(
    json_path: Path | str,
    model_name: str = DEFAULT_MODEL,
) -> str:
    """Re-embed all questions and overwrite the JSON file."""
    path = Path(json_path).resolve()
    document = json.loads(path.read_text(encoding="utf-8"))
    used_model = embed_document_questions(document, model_name)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return used_model


def search_questions(
    json_path: Path | str,
    topic: str,
    *,
    model_name: str = DEFAULT_MODEL,
    top_k: int | None = None,
    min_score: float = DEFAULT_MIN_SCORE,
    rebuild_embeddings: bool = False,
) -> dict[str, Any]:
    """Return ranked matches and a filtered document subset."""
    path = Path(json_path).resolve()
    topic = topic.strip()
    if not topic:
        raise ValueError("topic must not be empty")

    if rebuild_embeddings:
        rebuild_embeddings_in_json(path, model_name)

    document = json.loads(path.read_text(encoding="utf-8"))
    if not document_has_embeddings(document):
        embed_document_questions(document, model_name)
        path.write_text(
            json.dumps(document, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )

    numbers, matrix, stored_model = _embedding_matrix(document)
    if model_name != stored_model:
        raise ValueError(
            f"JSON embeddings use {stored_model!r}; "
            f"pass --model {stored_model!r} or --rebuild-embeddings"
        )

    model = _load_encoder(stored_model)
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

    questions = document.get("questions", [])
    filtered_questions = []
    for question in questions:
        if not isinstance(question, dict):
            continue
        if int(question.get("no", -1)) not in selected:
            continue
        filtered = {k: v for k, v in question.items() if k != "embedding"}
        filtered_questions.append(filtered)
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
        k: v
        for k, v in meta.items()
        if k not in ("embedding_model", "embedding_dims")
    }
    meta = {
        **meta,
        "search_topic": topic,
        "search_model": stored_model,
        "search_min_score": min_score,
        "search_match_count": len(matches),
    }

    return {
        "meta": meta,
        "questions": filtered_questions,
        "answer_key": filtered_answers,
        "search": {
            "topic": topic,
            "model": stored_model,
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
