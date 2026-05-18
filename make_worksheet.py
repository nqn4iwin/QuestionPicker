"""CLI: exam PDF + topic → filtered JSON, Word, and PDF (Windows + MS Word for PDF)."""

from __future__ import annotations

import argparse
from pathlib import Path

from modules.output_paths import default_docx_path, default_json_path
from modules.question_search import (
    DEFAULT_MIN_SCORE,
    DEFAULT_MODEL,
    search_questions,
    write_filtered_document,
)
from modules.word_export import json_to_docx_and_pdf
from search_questions import _resolve_json_path


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "From an exam PDF and a topic, write search JSON plus "
            "matching .docx and .pdf (PDF needs Windows and Microsoft Word)."
        )
    )
    parser.add_argument(
        "pdf",
        help="Input exam PDF path",
    )
    parser.add_argument(
        "--topic",
        required=True,
        help='Search topic (e.g. "윈도우10")',
    )
    parser.add_argument(
        "--rebuild-json",
        action="store_true",
        help="Re-extract PDF to JSON before search (ignore cached json/*-<pdf-stem>.json)",
    )
    parser.add_argument(
        "--print-matches",
        action="store_true",
        help="Print matched question numbers and scores",
    )
    parser.add_argument(
        "--min-score",
        type=float,
        default=DEFAULT_MIN_SCORE,
        help=f"Minimum similarity (default: {DEFAULT_MIN_SCORE})",
    )
    parser.add_argument(
        "--top",
        type=int,
        default=None,
        help="Keep at most N questions (default: all above min-score)",
    )
    args = parser.parse_args()

    pdf_path = Path(args.pdf).resolve()
    if not pdf_path.is_file():
        raise FileNotFoundError(pdf_path)

    json_path = _resolve_json_path(
        pdf_path,
        rebuild_json=args.rebuild_json,
        embedding_model=DEFAULT_MODEL,
    )

    search_json_path = default_json_path(topic=args.topic)
    document = search_questions(
        json_path,
        args.topic,
        model_name=DEFAULT_MODEL,
        top_k=args.top,
        min_score=args.min_score,
    )
    search_json_path = write_filtered_document(document, search_json_path)

    if args.print_matches:
        for match in document.get("search", {}).get("matches", []):
            print(f"  {match['no']:>2}  score={match['score']}")

    docx_path = default_docx_path(json_path=search_json_path)
    docx_out, pdf_out = json_to_docx_and_pdf(search_json_path, docx_path)

    count = len(document.get("questions", []))
    print(f"Topic: {args.topic}")
    print(f"Wrote {search_json_path} ({count} questions)")
    print(f"Wrote {docx_out}")
    print(f"Wrote {pdf_out}")


if __name__ == "__main__":
    main()
