"""CLI: extract exam PDF to structured JSON."""

from __future__ import annotations

import argparse
from pathlib import Path

from modules.output_paths import default_json_path
from modules.pdf_parse import pdf_to_json
from modules.question_search import DEFAULT_MODEL


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Extract exam PDF to structured JSON (single-column question order)."
    )
    parser.add_argument(
        "pdf",
        nargs="?",
        default="example.pdf",
        help="Input PDF path (default: example.pdf)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output JSON path (default: json/MMDD-HHMM-<pdf이름>.json)",
    )
    parser.add_argument(
        "--model",
        default=DEFAULT_MODEL,
        help=f"Embedding model stored in JSON (default: {DEFAULT_MODEL})",
    )
    parser.add_argument(
        "--no-embed",
        action="store_true",
        help="Skip embedding (JSON without vectors; search will embed on first run)",
    )
    args = parser.parse_args()
    pdf = Path(args.pdf)
    out_path = (
        Path(args.output)
        if args.output
        else default_json_path(stem=pdf.stem)
    )
    out = pdf_to_json(
        pdf,
        out_path,
        embed=not args.no_embed,
        embedding_model=args.model,
    )
    assets_dir = out.parent / f"{out.stem}_assets"
    print(f"Wrote {out}")
    if assets_dir.is_dir() and any(assets_dir.glob("*.png")):
        print(f"Wrote assets in {assets_dir}")


if __name__ == "__main__":
    main()
