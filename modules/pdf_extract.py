import re
import sys
from pathlib import Path

import fitz

_HEADER_FOOTER = re.compile(
    r"^(상시\d+|-\s*\d+\s*-|저작권 안내|기출문제.*정답.*)$",
    re.MULTILINE,
)


def _configure_stdout_utf8() -> None:
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8")
        except (OSError, ValueError):
            pass


def _join_span_texts(spans: list[dict]) -> str:
    """Join span texts; insert a space when fragments would otherwise glue together."""
    parts: list[str] = []
    for span in spans:
        piece = span.get("text", "")
        if not piece:
            continue
        if parts:
            prev = parts[-1]
            if not prev.endswith((" ", "-", "[", "(", "·")) and not piece.startswith(
                (" ", "]", ")", ",", ".", ":", ";")
            ):
                prev_char = prev[-1]
                next_char = piece[0]
                if prev_char.isalnum() or ord(prev_char) > 0x2E80:
                    if next_char.isalnum() or next_char in "[(" or ord(next_char) > 0x2E80:
                        parts[-1] = prev + " "
        parts.append(piece)
    return "".join(parts).strip()


def _line_items_from_page(page: fitz.Page) -> list[tuple[float, float, float, str]]:
    """Return (y0, x0, x1, text) for each visual line on the page."""
    items: list[tuple[float, float, float, str]] = []
    page_dict = page.get_text("dict", flags=fitz.TEXT_PRESERVE_WHITESPACE)

    for block in page_dict.get("blocks", []):
        if block.get("type") != 0:
            continue
        for line in block.get("lines", []):
            spans = line.get("spans", [])
            if not spans:
                continue
            spans = sorted(spans, key=lambda span: span["bbox"][0])
            text = _join_span_texts(spans)
            if not text:
                continue
            bbox = line.get("bbox") or spans[0].get("bbox")
            if not bbox:
                continue
            items.append((bbox[1], bbox[0], bbox[2], text))

    return items


def _partition_by_layout(
    items: list[tuple[float, float, float, str]], page_width: float
) -> tuple[list[tuple[float, float, str]], list[tuple[float, float, str]], list[tuple[float, float, str]]]:
    """Split lines into full-width, left-column, and right-column groups."""
    margin = page_width * 0.08
    full: list[tuple[float, float, str]] = []
    left: list[tuple[float, float, str]] = []
    right: list[tuple[float, float, str]] = []
    split_x = page_width * 0.52

    for y, x0, x1, text in items:
        width = x1 - x0
        center = (x0 + x1) / 2
        spans_page = x0 <= margin and x1 >= page_width - margin
        if spans_page or width >= page_width * 0.55:
            full.append((y, x0, text))
        elif center < split_x:
            left.append((y, x0, text))
        else:
            right.append((y, x0, text))

    for group in (full, left, right):
        group.sort(key=lambda row: (round(row[0], 1), row[1]))
    return full, left, right


def _merge_same_row(
    items: list[tuple[float, float, str]], y_tolerance: float = 6.0
) -> list[tuple[float, float, str]]:
    """Merge fragments on the same visual row, ordered left-to-right by x."""
    if not items:
        return []

    sorted_items = sorted(items, key=lambda row: (row[0], row[1]))
    clusters: list[list[tuple[float, float, str]]] = []

    for y, x, text in sorted_items:
        if clusters and abs(clusters[-1][0][0] - y) <= y_tolerance:
            clusters[-1].append((y, x, text))
        else:
            clusters.append([(y, x, text)])

    merged: list[tuple[float, float, str]] = []
    for cluster in clusters:
        cluster.sort(key=lambda row: row[1])
        row_y = min(fragment[0] for fragment in cluster)
        row_x = cluster[0][1]
        row_text = " ".join(fragment[2] for fragment in cluster)
        merged.append((row_y, row_x, row_text))

    return merged


def _lines_to_text(
    merged: list[tuple[float, float, str]], paragraph_gap: float = 14.0
) -> str:
    if not merged:
        return ""

    lines: list[str] = []
    prev_y: float | None = None

    for y, _x, text in merged:
        if prev_y is not None and y - prev_y > paragraph_gap:
            if lines and lines[-1] != "":
                lines.append("")
        lines.append(text)
        prev_y = y

    body = "\n".join(lines)
    body = _HEADER_FOOTER.sub("", body)
    body = re.sub(r"\n{3,}", "\n\n", body)
    return body.strip()


def extract_page_text(page: fitz.Page) -> str:
    raw = _line_items_from_page(page)
    full, left, right = _partition_by_layout(raw, page.rect.width)

    ordered: list[tuple[float, float, str]] = []
    if full:
        ordered.extend(_merge_same_row(full))
    if left:
        ordered.extend(_merge_same_row(left))
    if right:
        ordered.extend(_merge_same_row(right))

    return _lines_to_text(ordered)


def extract_pdf_lines(pdf_path: Path | str) -> list[dict[str, object]]:
    """Extract ordered lines with page/column metadata for structured parsing."""
    path = Path(pdf_path).resolve()
    lines: list[dict[str, object]] = []

    with fitz.open(path) as doc:
        for page_num, page in enumerate(doc, start=1):
            raw = _line_items_from_page(page)
            full, left, right = _partition_by_layout(raw, page.rect.width)

            for column, group in (("full", full), ("left", left), ("right", right)):
                for y, x, text in _merge_same_row(group):
                    lines.append(
                        {
                            "page": page_num,
                            "column": column,
                            "y": y,
                            "x": x,
                            "text": text,
                        }
                    )

    return lines


def column_for_bbox(page_width: float, x0: float, x1: float) -> str:
    """Classify a bbox into full-width, left-column, or right-column (matches line layout)."""
    margin = page_width * 0.08
    width = x1 - x0
    center = (x0 + x1) / 2
    split_x = page_width * 0.52
    spans_page = x0 <= margin and x1 >= page_width - margin
    if spans_page or width >= page_width * 0.55:
        return "full"
    if center < split_x:
        return "left"
    return "right"


def _is_watermark_bbox(page_width: float, x0: float, y0: float, x1: float, y1: float) -> bool:
    """Skip repeated center-column decorative images on exam pages."""
    area = (x1 - x0) * (y1 - y0)
    if area < 40_000:
        return False
    center_x = (x0 + x1) / 2 / page_width
    return 0.35 <= center_x <= 0.65 and 250 <= y0 <= 540


def extract_pdf_figures(
    pdf_path: Path | str,
    *,
    min_area: float = 8_000.0,
    header_y_max: float = 55.0,
) -> list[dict[str, object]]:
    """Return figure image blocks: page, column, bbox, y0, y1, area."""
    path = Path(pdf_path).resolve()
    figures: list[dict[str, object]] = []
    seen: set[tuple[int, int, int, int]] = set()

    with fitz.open(path) as doc:
        for page_num, page in enumerate(doc, start=1):
            page_width = page.rect.width
            for block in page.get_text("dict").get("blocks", []):
                if block.get("type") != 1:
                    continue
                bbox = block.get("bbox")
                if not bbox or len(bbox) != 4:
                    continue
                x0, y0, x1, y1 = bbox
                area = (x1 - x0) * (y1 - y0)
                if area < min_area or y0 < header_y_max:
                    continue
                if _is_watermark_bbox(page_width, x0, y0, x1, y1):
                    continue
                key = tuple(round(v, 1) for v in bbox)
                dedupe_key = (page_num, *key)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                figures.append(
                    {
                        "page": page_num,
                        "column": column_for_bbox(page_width, x0, x1),
                        "bbox": [float(x0), float(y0), float(x1), float(y1)],
                        "y0": float(y0),
                        "y1": float(y1),
                        "area": float(area),
                    }
                )

    figures.sort(key=lambda fig: (int(fig["page"]), str(fig["column"]), float(fig["y0"])))
    return figures


def save_figure_clip(
    page: fitz.Page,
    bbox: list[float] | tuple[float, float, float, float],
    dest: Path,
    zoom: float = 2.0,
) -> None:
    """Render a clipped page region to PNG."""
    rect = fitz.Rect(bbox)
    matrix = fitz.Matrix(zoom, zoom)
    pixmap = page.get_pixmap(matrix=matrix, clip=rect, alpha=False)
    dest.parent.mkdir(parents=True, exist_ok=True)
    pixmap.save(str(dest))


def extract_pdf_text(pdf_path: Path | str) -> list[str]:
    path = Path(pdf_path).resolve()
    texts: list[str] = []
    with fitz.open(path) as doc:
        for page in doc:
            texts.append(extract_page_text(page))
    return texts


def print_example_pdf_contents(pdf_path: Path | str | None = None) -> None:
    """Read example.pdf and print layout-aware text from every page."""
    path = Path(pdf_path) if pdf_path is not None else Path("example.pdf")
    for i, text in enumerate(extract_pdf_text(path), start=1):
        print(f"--- Page {i} ---")
        print(text if text else "(no extractable text on this page)")

