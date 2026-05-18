"""CLI: export exam JSON to Word (.docx)."""

from __future__ import annotations

import argparse
from pathlib import Path

from modules.output_paths import default_docx_path, topic_from_document
from modules.word_export import json_to_docx


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Export exam JSON to Word with 2-column pages. "
            "Each question stays in one block (no split across columns/pages)."
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

    out = json_to_docx(json_path, output_path)
    topic = topic_from_document(json_path)
    if topic:
        print(f"Topic: {topic}")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
