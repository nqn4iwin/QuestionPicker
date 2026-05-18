"""CLI: export exam JSON to Word (.docx)."""

from __future__ import annotations

import argparse
from pathlib import Path

from modules.output_paths import default_docx_path, topic_from_document
from modules.word_export import json_to_docx_and_pdf


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export exam JSON to Word (.docx) and PDF (.pdf). "
            "PDF requires Windows and locally installed Microsoft Word."
        )
    )
    parser.add_argument(
        "json",
        help="Input JSON (e.g. json/0518-1634-윈도우10.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output .docx path (default: docx/<same-stem-as-json>.docx)",
    )
    args = parser.parse_args()

    json_path = Path(args.json).resolve()
    if args.output:
        output_path = Path(args.output)
    else:
        output_path = default_docx_path(json_path=json_path)

    docx_out, pdf_out = json_to_docx_and_pdf(json_path, output_path)
    topic = topic_from_document(json_path)
    if topic:
        print(f"Topic: {topic}")
    print(f"Wrote {docx_out}")
    print(f"Wrote {pdf_out}")


if __name__ == "__main__":
    main()
