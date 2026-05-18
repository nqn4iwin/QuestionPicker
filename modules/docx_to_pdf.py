"""Convert .docx to .pdf via locally installed Microsoft Word (Windows only)."""

from __future__ import annotations

import sys
from pathlib import Path


def convert_docx_to_pdf(
    docx_path: Path | str,
    pdf_path: Path | str | None = None,
) -> Path:
    """Render a Word document to PDF using MS Word COM automation."""
    if sys.platform != "win32":
        raise RuntimeError(
            "docx→PDF는 Windows에서만 지원합니다. Microsoft Word가 설치된 PC에서 실행하세요."
        )

    docx = Path(docx_path).resolve()
    if not docx.is_file():
        raise FileNotFoundError(docx)

    pdf = Path(pdf_path).resolve() if pdf_path is not None else docx.with_suffix(".pdf")
    pdf.parent.mkdir(parents=True, exist_ok=True)

    try:
        from docx2pdf import convert
    except ImportError as exc:
        raise RuntimeError(
            "docx2pdf 패키지가 없습니다. 프로젝트 루트에서 uv sync 를 실행하세요."
        ) from exc

    try:
        convert(str(docx), str(pdf))
    except Exception as exc:
        raise RuntimeError(
            f"PDF 변환에 실패했습니다. Microsoft Word가 설치되어 있고 "
            f"다른 창에서 '{docx.name}' 을 열고 있지 않은지 확인하세요."
        ) from exc

    if not pdf.is_file():
        raise RuntimeError(f"PDF 파일이 생성되지 않았습니다: {pdf}")

    return pdf
