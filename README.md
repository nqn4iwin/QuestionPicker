# pdf-questionnaire

컴활 기출 PDF를 구조화 JSON으로 뽑고, **주제(임베딩) 검색**으로 문항을 골라 Word 등으로 보내기 위한 도구 모음입니다.

## 요구 사항

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)

```powershell
uv sync
```

첫 **검색** 실행 시 Hugging Face에서 한국어 임베딩 모델을 받습니다(용량 큼, 1회).

## 파이프라인

```text
PDF
  → pdf_to_json.py          … 문항 JSON + 그림 PNG ({stem}_assets/q{N}.png)
  → search_questions.py     … 주제로 문항 필터 (로컬 임베딩)
  → normalize_json.py       … (선택) 구두점 정리
  → json_to_word.py         … (미구현, todo.md)
```

## 사용법

### 1. PDF → JSON (+ 이미지)

```powershell
uv run python pdf_to_json.py your.pdf
```

생성물(기본, gitignore 대상): `your.json`, `your_assets/`

### 2. 주제 검색

PDF만 넘겨도 됩니다. JSON이 없으면 1단계를 먼저 실행합니다.

```powershell
uv run python search_questions.py your.pdf --topic 네트워크 --print-matches
```

| 옵션 | 설명 |
|------|------|
| `--topic` | 검색 주제 (필수) |
| `-o` | 출력 JSON 경로 |
| `--min-score` | 유사도 하한 (기본 `0.28`) |
| `--top` | 상위 N개만 |
| `--rebuild-index` | 임베딩 캐시 재생성 |
| `--model` | `sentence-transformers` 모델 ID |

기본 모델: `jhgan/ko-sroberta-multitask`

출력: `your.search-<hash>.json` — 매칭 문항만, `search.matches`에 점수.

### 3. (선택) 텍스트 정리

```powershell
uv run python normalize_json.py your.json
```

기본은 구두점·공백만 (`--kiwi`로 Kiwi 합치기 optional). 출력: `your.corrected.json`

### 4. PDF 텍스트만 확인

```powershell
uv run python read_example_pdf.py your.pdf
```

## JSON 형식 (요약)

```json
{
  "meta": { "source": "...", "extractor": "pymupdf", "assets_dir": "..." },
  "questions": [
    {
      "no": 1,
      "content": "...",
      "choices": [{ "choice": 1, "text": "..." }],
      "source": { "page": 1, "columns": ["left"] },
      "assets": [{ "type": "image", "path": "your_assets/q35.png" }]
    }
  ],
  "answer_key": [{ "no": 1, "answer": 3 }]
}
```
