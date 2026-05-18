"""CLI: normalize exam JSON text before Word export."""

from __future__ import annotations

import argparse

from modules.json_normalize import normalize_json_file


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Normalize exam JSON text before Word export."
    )
    parser.add_argument(
        "json",
        help="Input JSON (e.g. json/0518-1634-example.json)",
    )
    parser.add_argument(
        "-o",
        "--output",
        help="Output path (default: json/MMDD-HHMM-<stem>-corrected.json)",
    )
    parser.add_argument(
        "--kiwi",
        action="store_true",
        help="Also run Kiwi merge pass (default: punctuation only).",
    )
    args = parser.parse_args()

    dest, log = normalize_json_file(
        args.json,
        args.output,
        use_kiwi=args.kiwi,
    )
    print(f"Wrote {dest}")
    print(f"Corrections: {len(log)}")


if __name__ == "__main__":
    main()
