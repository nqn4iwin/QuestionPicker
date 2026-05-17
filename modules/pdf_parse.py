"""Parse PyMuPDF extraction into structured JSON (single-column question order)."""

from __future__ import annotations

import json
import re
from pathlib import Path

import fitz

from modules.pdf_extract import extract_pdf_figures, extract_pdf_lines, save_figure_clip

CHOICE_MARKERS = "①②③④"
CHOICE_TO_INT = {"①": 1, "②": 2, "③": 3, "④": 4}
CHOICE_SPLIT = re.compile(r"([①②③④])")
QUESTION_END = re.compile(r"(\d+)\.\s*\??\s*$")
QUESTION_START = re.compile(r"^(\d+)\.\s+(.+)$")
SECTION_TITLE = re.compile(r"^제\s*과목\s+(.+?)\s*\d*\s*$")
ANSWER_PAIR = re.compile(r"(\d+)\.([①②③④])")

SKIP_LINE = re.compile(
    r"(시나공|기출문제|※\s*다음|답란\s*\(|허락 없이|른 매체에|"
    r"^&\s*정답|년 컴퓨터활용능력|^\.\s*허락|^\d{4}$|이 자료는|"
    r"^-\s*\d+\s*-$)",
)

FIGURE_CONTENT = re.compile(
    r"아래\s*(그림|워크시트|표)|아래\s*워크시트|아래의\s|"
    r"아래\s+.*대화상자|찾기\s*및\s*바꾸기",
)

QUOTE_NORMALIZE = str.maketrans(
    {
        "\u2018": "'",
        "\u2019": "'",
        "\u201c": '"',
        "\u201d": '"',
    }
)


def normalize_text(text: str) -> str:
    """Normalize typographic quotes from PDF text to ASCII quotes."""
    return text.translate(QUOTE_NORMALIZE)


def _line_starts_with_choice(text: str) -> bool:
    return bool(re.match(r"^[①②③④]", text))


def _append_to_last_choice(question: dict[str, object], text: str) -> None:
    choices = question.get("choices", [])
    if not isinstance(choices, list) or not choices:
        return
    last = choices[-1]
    if not isinstance(last, dict):
        return
    merged = normalize_text(f"{last.get('text', '')} {text}".strip())
    last["text"] = merged


def _set_choice_page(question: dict[str, object], line: dict[str, object]) -> None:
    question["_last_choice_page"] = line["page"]


def _same_page_as_last_choice(question: dict[str, object], line: dict[str, object]) -> bool:
    last_page = question.get("_last_choice_page")
    return last_page is not None and line["page"] == last_page


def _should_skip(text: str) -> bool:
    stripped = text.strip()
    if not stripped or stripped in {".", ","}:
        return True
    return bool(SKIP_LINE.search(stripped))


def _marker_to_choice(marker: str) -> int:
    choice = CHOICE_TO_INT.get(marker)
    if choice is None:
        raise ValueError(f"Unknown choice marker: {marker!r}")
    return choice


def _parse_choices(text: str) -> list[dict[str, object]]:
    if not any(mark in text for mark in CHOICE_MARKERS):
        return []

    parts = CHOICE_SPLIT.split(text)
    choices: list[dict[str, object]] = []
    idx = 1
    while idx < len(parts) - 1:
        marker = parts[idx]
        body = parts[idx + 1].strip(" ,.")
        if body:
            choices.append(
                {
                    "choice": _marker_to_choice(marker),
                    "text": normalize_text(body),
                }
            )
        idx += 2
    return choices


def _find_question_marker(text: str) -> tuple[int, str, str] | None:
    """Return (number, text_before_marker, text_after_marker)."""
    match = QUESTION_START.match(text)
    if match:
        number = int(match.group(1))
        if 1 <= number <= 40:
            return number, "", match.group(2).strip()

    match = QUESTION_END.search(text)
    if match:
        number = int(match.group(1))
        if 1 <= number <= 40:
            return number, text[: match.start()].strip(), ""

    match = re.search(r"^(.*?)\s+(\d{1,2})\.\s+(.+)$", text)
    if match:
        number = int(match.group(2))
        if 1 <= number <= 40:
            return number, match.group(1).strip(), match.group(3).strip()

    return None


def _strip_number_from_stem(stem: str, number: int) -> str:
    stem = re.sub(rf"\s*{number}\.\s*\??\s*$", "", stem).strip()
    stem = re.sub(rf"^{number}\.\s+", "", stem).strip()
    return stem


def _starts_bullet(line: str) -> bool:
    return line.startswith(("•", "・", "▪", "- "))


def _ends_sentence(text: str) -> bool:
    stripped = text.rstrip()
    if not stripped:
        return False
    if stripped.endswith(("?", "!", "…")):
        return True
    if re.search(r"(다|요|음|임)\.\s*$", stripped):
        return True
    if stripped.endswith("."):
        return True
    return False


def build_content(stem: str, body_lines: list[str]) -> str:
    """Merge stem and body_lines; keep \\n only between logical paragraphs/bullets."""
    paragraphs: list[str] = []
    current = stem.strip()

    for raw in body_lines:
        line = raw.strip()
        if not line:
            continue
        if not current:
            current = line
            continue
        if _starts_bullet(line):
            paragraphs.append(current)
            current = line
        elif _starts_bullet(current) or not _ends_sentence(current):
            current = f"{current} {line}"
        else:
            paragraphs.append(current)
            current = line

    if current:
        paragraphs.append(current)

    return "\n".join(paragraphs)


def _parse_answer_key_line(text: str) -> list[dict[str, object]]:
    return [
        {"no": int(number), "answer": _marker_to_choice(answer)}
        for number, answer in ANSWER_PAIR.findall(text)
    ]


def _wants_figure_asset(content: str) -> bool:
    return bool(FIGURE_CONTENT.search(content))


def _figure_in_stem_gap(
    figure: dict[str, object],
    layout: dict[str, object] | None,
) -> bool:
    """Image sits between the question stem and its first choice row (same page/column)."""
    if not layout:
        return False
    if int(figure["page"]) != int(layout["page"]):
        return False
    if str(figure["column"]) != str(layout["column"]):
        return False
    y_first_choice = layout.get("y_first_choice")
    if y_first_choice is None:
        return False
    y0 = float(figure["y0"])
    y_start = float(layout["y_start"])
    return y_start - 5.0 <= y0 < float(y_first_choice) - 5.0


def _should_attach_figure(
    question: dict[str, object],
    figure: dict[str, object],
    layout: dict[str, object] | None,
) -> bool:
    content = str(question.get("content", ""))
    if _wants_figure_asset(content):
        return True
    return _figure_in_stem_gap(figure, layout)


def _flush_question(
    question: dict[str, object] | None,
) -> dict[str, object] | None:
    if not question:
        return None
    number = int(question["no"])
    stem = _strip_number_from_stem(str(question.get("stem", "")), number)
    body_lines = question.get("body_lines", [])
    if not isinstance(body_lines, list):
        body_lines = []
    cleaned_body = [str(line) for line in body_lines if str(line).strip()]

    choices = question.get("choices", [])
    if isinstance(choices, list):
        for choice in choices:
            if isinstance(choice, dict) and "text" in choice:
                choice["text"] = normalize_text(str(choice["text"]))

    flushed: dict[str, object] = {
        "no": number,
        "content": normalize_text(build_content(stem, cleaned_body)),
        "choices": choices,
        "source": question.get("source", {}),
    }
    assets = question.get("assets")
    if isinstance(assets, list) and assets:
        flushed["assets"] = assets
    return flushed


def parse_lines_to_document(
    lines: list[dict[str, object]], source: Path
) -> dict[str, object]:
    questions: list[dict[str, object]] = []
    answer_key: list[dict[str, object]] = []
    question_starts: list[dict[str, object]] = []
    figure_layouts: dict[int, dict[str, object]] = {}

    current_question: dict[str, object] | None = None
    answer_mode = False

    def _record_first_choice_y(line: dict[str, object]) -> None:
        if not current_question:
            return
        layout = current_question.get("_figure_layout")
        if not isinstance(layout, dict) or layout.get("y_first_choice") is not None:
            return
        if int(line["page"]) == int(layout["page"]) and str(line["column"]) == str(
            layout["column"]
        ):
            layout["y_first_choice"] = float(line["y"])

    def flush_current_question() -> None:
        nonlocal current_question
        if current_question:
            number = int(current_question["no"])
            layout = current_question.get("_figure_layout")
            if isinstance(layout, dict):
                figure_layouts[number] = layout
            flushed = _flush_question(current_question)
            if flushed:
                questions.append(flushed)
            current_question = None

    def start_question(number: int, stem: str, line: dict[str, object]) -> None:
        nonlocal current_question
        flush_current_question()
        current_question = {
            "no": number,
            "stem": normalize_text(stem),
            "body_lines": [],
            "choices": [],
            "assets": [],
            "source": {
                "page": line["page"],
                "columns": [line["column"]],
            },
        }
        question_starts.append(
            {
                "no": number,
                "page": int(line["page"]),
                "column": str(line["column"]),
                "y": float(line["y"]),
            }
        )
        current_question["_figure_layout"] = {
            "page": int(line["page"]),
            "column": str(line["column"]),
            "y_start": float(line["y"]),
            "y_first_choice": None,
        }

    def append_source_column(line: dict[str, object]) -> None:
        if not current_question:
            return
        source_info = current_question["source"]
        assert isinstance(source_info, dict)
        columns = source_info.setdefault("columns", [])
        assert isinstance(columns, list)
        column = line["column"]
        if column not in columns:
            columns.append(column)

    for line in lines:
        text = normalize_text(str(line["text"]).strip())
        if _should_skip(text):
            continue

        if text == "정답" or text.startswith("정답 "):
            answer_mode = True
            flush_current_question()
            continue

        if answer_mode:
            answer_key.extend(_parse_answer_key_line(text))
            continue

        if SECTION_TITLE.match(text):
            continue

        marker = _find_question_marker(text)
        if marker:
            number, before, after = marker
            stem = " ".join(part for part in (before, after) if part).strip()
            start_question(number, stem, line)
            choices = _parse_choices(text)
            if choices and current_question:
                current_question["choices"].extend(choices)
                _set_choice_page(current_question, line)
                _record_first_choice_y(line)
            continue

        choices = _parse_choices(text)
        if choices and current_question and _line_starts_with_choice(text):
            append_source_column(line)
            current_question["choices"].extend(choices)
            _set_choice_page(current_question, line)
            _record_first_choice_y(line)
            continue

        if current_question and current_question.get("choices"):
            if not _same_page_as_last_choice(current_question, line):
                continue
            append_source_column(line)
            _append_to_last_choice(current_question, text)
            continue

        if current_question:
            append_source_column(line)
            body_lines = current_question["body_lines"]
            assert isinstance(body_lines, list)
            body_lines.append(text)

    flush_current_question()

    deduped: dict[int, int] = {}
    for item in answer_key:
        deduped[int(item["no"])] = int(item["answer"])
    answer_key_sorted = [
        {"no": number, "answer": answer} for number, answer in sorted(deduped.items())
    ]

    questions.sort(key=lambda q: int(q["no"]))

    return {
        "meta": {
            "source": source.name,
            "source_path": str(source.resolve()),
            "extractor": "pymupdf",
            "layout_note": "Questions are stored in single-column reading order (not PDF 2-column).",
            "sections_note": "Subject sections are not included; may be added in a future schema.",
        },
        "questions": questions,
        "answer_key": answer_key_sorted,
        "_question_starts": question_starts,
        "_figure_layouts": figure_layouts,
    }


def _assign_question_for_figure(
    figure: dict[str, object],
    question_starts: list[dict[str, object]],
) -> int | None:
    page = int(figure["page"])
    column = str(figure["column"])
    y0 = float(figure["y0"])

    anchors = [
        anchor
        for anchor in question_starts
        if int(anchor["page"]) == page and str(anchor["column"]) == column
    ]
    if not anchors:
        anchors = [anchor for anchor in question_starts if int(anchor["page"]) == page]
    if not anchors:
        return None

    anchors.sort(key=lambda anchor: float(anchor["y"]))
    chosen: dict[str, object] | None = None
    for anchor in anchors:
        if float(anchor["y"]) <= y0 + 8.0:
            chosen = anchor
        else:
            break
    if chosen is None:
        return None
    return int(chosen["no"])


def attach_figure_assets(
    document: dict[str, object],
    pdf_path: Path,
    assets_dir: Path,
) -> None:
    """Extract figures, save as q{N}.png, and attach paths to matching questions."""
    question_starts = document.pop("_question_starts", [])
    if not isinstance(question_starts, list):
        question_starts = []

    figure_layouts = document.pop("_figure_layouts", {})
    if not isinstance(figure_layouts, dict):
        figure_layouts = {}

    questions = document.get("questions", [])
    if not isinstance(questions, list):
        return

    by_number: dict[int, dict[str, object]] = {
        int(question["no"]): question for question in questions
    }
    figures = extract_pdf_figures(pdf_path)
    per_question_count: dict[int, int] = {}

    with fitz.open(pdf_path) as doc:
        for figure in figures:
            number = _assign_question_for_figure(figure, question_starts)
            if number is None:
                continue
            question = by_number.get(number)
            if question is None:
                continue
            layout = figure_layouts.get(number)
            if not isinstance(layout, dict):
                layout = None
            if not _should_attach_figure(question, figure, layout):
                continue

            per_question_count[number] = per_question_count.get(number, 0) + 1
            index = per_question_count[number]
            filename = f"q{number}.png" if index == 1 else f"q{number}_{index}.png"
            rel_path = f"{assets_dir.name}/{filename}"
            dest = assets_dir / filename

            page = doc[int(figure["page"]) - 1]
            save_figure_clip(page, figure["bbox"], dest)

            assets = question.setdefault("assets", [])
            if not isinstance(assets, list):
                continue
            assets.append(
                {
                    "type": "image",
                    "path": rel_path,
                    "page": int(figure["page"]),
                    "bbox": figure["bbox"],
                }
            )

    meta = document.get("meta")
    if isinstance(meta, dict) and any(
        isinstance(question.get("assets"), list) and question["assets"]
        for question in questions
    ):
        meta["assets_dir"] = assets_dir.name


def pdf_to_json(pdf_path: Path | str, output_path: Path | str | None = None) -> Path:
    pdf = Path(pdf_path).resolve()
    if not pdf.is_file():
        raise FileNotFoundError(pdf)

    out = Path(output_path) if output_path else pdf.with_suffix(".json")
    assets_dir = out.parent / f"{pdf.stem}_assets"

    lines = extract_pdf_lines(pdf)
    document = parse_lines_to_document(lines, pdf)
    attach_figure_assets(document, pdf, assets_dir)

    out.write_text(
        json.dumps(document, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return out
