"""CLI: extract exam PDF to structured JSON."""

from __future__ import annotations

import argparse
from pathlib import Path

from modules.pdf_parse import pdf_to_json


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
        help="Output JSON path (default: <pdf>.json)",
    )
    args = parser.parse_args()
    out = pdf_to_json(args.pdf, args.output)
    assets_dir = out.parent / f"{Path(args.pdf).stem}_assets"
    print(f"Wrote {out}")
    if assets_dir.is_dir() and any(assets_dir.glob("*.png")):
        print(f"Wrote assets in {assets_dir}")


if __name__ == "__main__":
    main()
