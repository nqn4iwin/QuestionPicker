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
  → json_to_word.py         … JSON → Word (2단, 문항 단위 분리 방지)
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

생성물(기본, gitignore): `json/MMDD-HHMM-<pdf이름>.json`, `json/MMDD-HHMM-<pdf이름>_assets/`

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

출력: `json/MMDD-HHMM-<검색어>.json` (예: `json/0518-1634-윈도우10.json`) — 매칭 문항만, `search.matches`에 점수.

### 3. (선택) 텍스트 정리

```powershell
uv run python normalize_json.py your.json
```

기본은 구두점·공백만 (`--kiwi`로 Kiwi 합치기 optional). 출력: `json/MMDD-HHMM-<stem>-corrected.json`

### 4. JSON → Word + PDF

```powershell
uv run python json_to_word.py json/0518-1634-윈도우10.json
```

**Windows + Microsoft Word** 가 설치된 PC에서 실행하세요. Word로 `.docx`를 만든 뒤 같은 파일명으로 `.pdf`까지 생성합니다.

| 옵션 | 설명 |
|------|------|
| `-o` | 출력 `.docx` 경로 (기본 `docx/<json과 같은 파일명>.docx`) |

생성물: `docx/<stem>.docx`, `pdf/<stem>.pdf` (stem은 JSON 파일명과 동일).

전체 시험지: 번호 순, 4문항·새 페이지, 표 행마다 `1|3` `2|4`. 검색 JSON: 번호 순, 4문항마다 **한 표 행**에 왼쪽 열·오른쪽 열로 위→아래 쌓기(예: 왼쪽 2·4 / 오른쪽 8·12). 문항 블록만 `cantSplit`. `assets` PNG 삽입.

### 5. PDF 텍스트만 확인

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
