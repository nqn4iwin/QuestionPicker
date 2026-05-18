"""CLI: semantic search over exam JSON by topic."""

from __future__ import annotations

import argparse
from pathlib import Path

from modules.output_paths import (
    default_json_path,
    find_latest_json_for_stem,
)
from modules.pdf_parse import pdf_to_json
from modules.question_search import (
    DEFAULT_MIN_SCORE,
    DEFAULT_MODEL,
    search_questions,
    write_filtered_document,
)


def _resolve_json_path(
    path: Path,
    *,
    rebuild_json: bool,
    embedding_model: str,
) -> Path:
    if path.suffix.lower() == ".pdf":
        stem = path.stem
        if rebuild_json:
            json_path = default_json_path(stem=stem)
            pdf_to_json(
                path,
                json_path,
                embed=True,
                embedding_model=embedding_model,
            )
            return json_path.resolve()
        existing = find_latest_json_for_stem(stem)
        if existing is not None:
            return existing.resolve()
        json_path = default_json_path(stem=stem)
        pdf_to_json(
            path,
            json_path,
            embed=True,
            embedding_model=embedding_model,
        )
        return json_path.resolve()
    if not path.is_file():
        raise FileNotFoundError(path)
    return path.resolve()


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Semantic search over exam JSON by topic (local embeddings, no LLM API)."
    )
    parser.add_argument(
        "input",
        help="Exam PDF or JSON (PDF runs pdf_to_json first if needed)",
    )
    parser.add_argument(
        "--topic",
        required=True,
        help="Search topic in natural language (e.g. 네트워크)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Filtered JSON path (default: json/MMDD-HHMM-<topic>.json)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"sentence-transformers model (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=None,
        help="Max number of hits (default: all above min-score)",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=DEFAULT_MIN_SCORE,
        help=f"Minimum cosine similarity (default: {DEFAULT_MIN_SCORE})",
    )
    parser.add_argument(
        "--rebuild-embeddings",
        action="store_true",
        help="Re-embed all questions and update the source JSON",
    )
    parser.add_argument(
        "--rebuild-json",
        action="store_true",
        help="When input is PDF, re-run pdf_to_json before search",
    )
    parser.add_argument(
        "--print-matches",
        action="store_true",
        help="Print match list to stdout",
    )
    args = parser.parse_args()

    input_path = Path(args.input)
    json_path = _resolve_json_path(
        input_path,
        rebuild_json=args.rebuild_json,
        embedding_model=args.model,
    )

    output_path = (
        Path(args.output)
        if args.output
        else default_json_path(topic=args.topic)
    )

    document = search_questions(
        json_path,
        args.topic,
        model_name=args.model,
        top_k=args.top,
        min_score=args.min_score,
        rebuild_embeddings=args.rebuild_embeddings,
    )
    out = write_filtered_document(document, output_path)

    if args.print_matches:
        for match in document.get("search", {}).get("matches", []):
            print(f"  {match['no']:>2}  score={match['score']}")

    print(f"Wrote {out} ({len(document.get('questions', []))} questions)")


if __name__ == "__main__":
    main()
