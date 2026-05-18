"""Conservative text cleanup for exam JSON (generic punctuation + Kiwi merge only)."""

from __future__ import annotations

import re
from dataclasses import dataclass
from functools import lru_cache
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from kiwipiepy import Kiwi

HANGUL = re.compile(r"[가-힣]")
HANGUL_RUN = re.compile(r"[가-힣][가-힣\s]*[가-힣]|[가-힣]")

MASK_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"[①②③④]"),
    re.compile(r"=[^①②③④\n]+"),
    re.compile(r"\[[^\]\n]{1,40}\]"),
    re.compile(r"\([^)\n]{0,60}\)"),
    re.compile(r"'[^'\n]{1,80}'"),
    re.compile(r'"[^"\n]{1,80}"'),
]

PLACEHOLDER = "\x00M{index}\x00"


@dataclass
class Correction:
    rule: str
    before: str
    after: str

    def as_dict(self) -> dict[str, str]:
        return {"rule": self.rule, "from": self.before, "to": self.after}


@lru_cache(maxsize=1)
def _kiwi() -> Kiwi:
    from kiwipiepy import Kiwi

    return Kiwi()


def _content_tokens(kiwi: Kiwi, text: str) -> list[str]:
    return [token.form for token in kiwi.tokenize(text) if token.form]


def _should_merge(left: str, right: str, kiwi: Kiwi) -> bool:
    if not left or not right:
        return False
    if not HANGUL.fullmatch(left) or not HANGUL.fullmatch(right):
        return False
    if len(left) > 4 and len(right) > 4:
        return False
    merged = left + right
    split = f"{left} {right}"
    merged_tokens = _content_tokens(kiwi, merged)
    split_tokens = _content_tokens(kiwi, split)
    if len(merged_tokens) < len(split_tokens):
        return True
    if len(merged_tokens) == 1 and len(split_tokens) >= 2:
        return True
    if len(merged_tokens) == 1 and merged_tokens[0] == merged:
        return True
    return False


def _try_merge_word_boundary(left_word: str, right_word: str, kiwi: Kiwi) -> str | None:
    """If PDF broke a word across a space, merge when Kiwi prefers the combined form."""
    if not left_word or not right_word:
        return None
    if len(left_word) > 2 and len(right_word) > 2:
        return None
    for cut in range(1, len(right_word)):
        prefix = right_word[:cut]
        if not _should_merge(left_word, prefix, kiwi):
            continue
        return left_word + prefix + right_word[cut:]
    if _should_merge(left_word, right_word, kiwi):
        return left_word + right_word
    return None


def _merge_spurious_spaces(run: str, kiwi: Kiwi) -> str:
    parts = run.split(" ")
    if len(parts) < 2:
        return run
    merged_parts = [parts[0]]
    for part in parts[1:]:
        combined = _try_merge_word_boundary(merged_parts[-1], part, kiwi)
        if combined is not None:
            merged_parts[-1] = combined
        else:
            merged_parts.append(part)
    return " ".join(merged_parts)


def _apply_kiwi_to_run(run: str, kiwi: Kiwi, corrections: list[Correction]) -> str:
    original = run
    run = _merge_spurious_spaces(run, kiwi)
    if run != original:
        corrections.append(
            Correction(rule="kiwi_merge", before=original, after=run)
        )
    return run


def apply_punctuation_rules(text: str, corrections: list[Correction]) -> str:
    """Whitespace and punctuation only (no Korean substring replacements)."""
    original = text
    lines = text.split("\n")
    cleaned: list[str] = []
    for line in lines:
        line = re.sub(r"[ \t]+", " ", line)
        line = re.sub(r" *([,.\?!:;])", r"\1", line)
        line = re.sub(r", *\.", ".", line)
        line = re.sub(r",\s*,+", ",", line)
        line = re.sub(r"\?\s*\?", "?", line)
        cleaned.append(line.strip())
    text = "\n".join(cleaned)
    text = re.sub(r"\n{3,}", "\n\n", text)
    if text != original:
        corrections.append(
            Correction(rule="punctuation", before=original, after=text)
        )
    return text


def _mask_text(text: str) -> tuple[str, list[str]]:
    masks: list[str] = []

    def replacer(match: re.Match[str]) -> str:
        masks.append(match.group(0))
        return PLACEHOLDER.format(index=len(masks) - 1)

    for pattern in MASK_PATTERNS:
        text = pattern.sub(replacer, text)
    return text, masks


def _unmask_text(text: str, masks: list[str]) -> str:
    for index, value in enumerate(masks):
        text = text.replace(PLACEHOLDER.format(index=index), value)
    return text


def _apply_kiwi_segmented(text: str, kiwi: Kiwi, corrections: list[Correction]) -> str:
    parts: list[str] = []
    last = 0
    for match in HANGUL_RUN.finditer(text):
        parts.append(text[last : match.start()])
        parts.append(_apply_kiwi_to_run(match.group(0), kiwi, corrections))
        last = match.end()
    parts.append(text[last:])
    return "".join(parts)


def normalize_exam_text(text: str, *, use_kiwi: bool = True) -> tuple[str, list[Correction]]:
    """Normalize one content/choice string. Skips pure-ASCII strings."""
    corrections: list[Correction] = []
    if not text or not HANGUL.search(text):
        cleaned = apply_punctuation_rules(text, corrections)
        return cleaned, corrections

    cleaned = apply_punctuation_rules(text, corrections)
    masked, masks = _mask_text(cleaned)
    if use_kiwi:
        kiwi = _kiwi()
        masked = _apply_kiwi_segmented(masked, kiwi, corrections)
    result = _unmask_text(masked, masks)
    return result, corrections
