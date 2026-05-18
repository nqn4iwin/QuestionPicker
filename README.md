# pdf-questionnaire

컴활 기출 PDF를 구조화 JSON으로 뽑고, **주제(임베딩) 검색**으로 문항을 골라 Word 등으로 보내기 위한 도구 모음입니다.

## 요구 사항

- Python 3.13+
- [uv](https://github.com/astral-sh/uv)

```powershell
uv sync
```

첫 **PDF→JSON** 실행 시 Hugging Face에서 임베딩 모델을 받아 문항 벡터를 JSON에 저장합니다(용량 큼, 1회). 검색 시에는 **검색어만** 임베딩합니다. 비공개 모델이면 선택적으로 `HF_TOKEN`을 환경 변수에 둡니다.

## 파이프라인

```text
PDF
  → pdf_to_json.py          … 문항 JSON + 그림 PNG + 문항별 embedding
  → search_questions.py     … 주제 임베딩 후 JSON에 저장된 벡터와 비교
  → normalize_json.py       … (선택) 구두점 정리 — 텍스트 바꾼 뒤는 pdf_to_json 재실행 또는 --rebuild-embeddings
  → json_to_word.py         … (미구현, todo.md)
```

## 사용법

### 1. PDF → JSON (+ 이미지)

```powershell
uv run python pdf_to_json.py your.pdf
```

| 옵션 | 설명 |
|------|------|
| `--model` | JSON에 저장할 임베딩 모델 (기본 `dragonkue/multilingual-e5-small-ko-v2`) |
| `--no-embed` | 추출만 (벡터 없음; 첫 검색 시 JSON에 임베딩 추가) |

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
| `--min-score` | 유사도 하한 (기본 `0.50`, e5 모델 기준) |
| `--top` | 상위 N개만 |
| `--rebuild-embeddings` | JSON 안 문항 벡터 다시 계산·저장 |
| `--model` | `sentence-transformers` 모델 ID (JSON의 `meta.embedding_model`과 일치해야 함) |

기본 모델: `dragonkue/multilingual-e5-small-ko-v2`

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
  "meta": {
    "source": "...",
    "extractor": "pymupdf",
    "assets_dir": "...",
    "embedding_model": "dragonkue/multilingual-e5-small-ko-v2",
    "embedding_dims": 384
  },
  "questions": [
    {
      "no": 1,
      "content": "...",
      "choices": [{ "choice": 1, "text": "..." }],
      "embedding": [0.012, -0.034, "..."],
      "source": { "page": 1, "columns": ["left"] },
      "assets": [{ "type": "image", "path": "your_assets/q35.png" }]
    }
  ],
  "answer_key": [{ "no": 1, "answer": 3 }]
}
```

검색 결과 JSON(`.search-*.json`)에는 `embedding` 필드를 넣지 않습니다.
