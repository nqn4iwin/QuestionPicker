"""CLI: print layout-aware text extracted from a PDF."""

import sys
from pathlib import Path

from modules.pdf_extract import _configure_stdout_utf8, print_example_pdf_contents


def main() -> None:
    _configure_stdout_utf8()
    path = Path(sys.argv[1]) if len(sys.argv) > 1 else None
    print_example_pdf_contents(path)


if __name__ == "__main__":
    main()
