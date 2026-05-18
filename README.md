# QuestionPicker

**PDF 문제집**에서 주제에 해당하는 문항을 골라 새로운 시험지를 만드는 도구입니다.

---

## 빠른 사용 (매번)

PowerShell을 연 뒤, 아래 블록을 **통째로 복사**해 붙여넣습니다.  
**아래 세 곳만** 본인 환경에 맞게 고칩니다.

1. `cd ...\QuestionPicker` — `git clone` 으로 받은 **QuestionPicker** 폴더
2. `"C:\...\기출.pdf"` — 기출 PDF 파일 경로 (본인 경로에 맞게 설정)
3. `"윈도우10"` — 찾고 싶은 주제 (따옴표 포함 권장)

```powershell
cd C:\Users\본인이름\QuestionPicker
uv run python make_worksheet.py "C:\Users\본인이름\Documents\기출.pdf" --topic "윈도우10"
```

**결과물**

| 폴더 | 용도 |
|------|------|
| `pdf/` | 학생에게 줄 PDF (`MMDD-HHMM-<주제>.pdf`) |
| `docx/` | 선생님이 Word에서 수정할 파일 (같은 이름) |
| `json/` | 검색 결과 데이터 (다시 쓸 때 참고) |

같은 PDF를 다시 추출하려면 `--rebuild-json` 을 붙입니다.

```powershell
uv run python make_worksheet.py "C:\...\기출.pdf" --topic "윈도우10" --rebuild-json
```

매칭 문항 번호·점수를 보려면 `--print-matches` 를 추가합니다.

---

## 설치 (처음 한 번만)

### 필요한 것

- **Windows** PC
- **Microsoft Word** (설치되어 있어야 PDF까지 생성됩니다)
- **인터넷** (Git·uv·AI 모델 다운로드)

### 1. Git 설치

PC에 Git이 없으면 먼저 설치합니다.

1. 브라우저에서 [Git for Windows](https://git-scm.com/download/win) 를 열고 설치 프로그램을 받습니다.
2. 설치 마법사는 **기본값(Next)** 으로 진행해도 됩니다.
3. 설치가 끝나면 **Windows PowerShell**을 엽니다.
4. PowerShell에서 아래를 입력했을 때 버전 정보가 나오면 성공입니다.

```powershell
git --version
```

### 2. uv 설치

PowerShell에서 한 번 실행합니다. ([공식 안내](https://docs.astral.sh/uv/getting-started/installation/))

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

설치 후 **PowerShell을 한 번 닫았다가 다시** 엽니다.
마찬가지로 아래를 입력했을 때 버전 정보가 나오면 성공입니다.

```powershell
uv --version
```

### 3. QuestionPicker 받기 (`git clone`)

```powershell
cd C:\Users\본인이름\Documents (다른 경로여도 무방합니다)
git clone https://github.com/nqn4iwin/QuestionPicker.git
cd QuestionPicker
```

`clone` 이 끝나면 `Documents\QuestionPicker` 같은 경로에 코드가 있습니다. 이후 **빠른 사용**의 `cd` 도 이 **QuestionPicker** 폴더를 가리켜야 합니다.

### 4. 패키지 설치

**QuestionPicker** 폴더 안에서:

```powershell
uv sync
```

몇 분 걸릴 수 있습니다.

### 5. 첫 실행 참고

- **처음** PDF를 처리할 때 Hugging Face에서 임베딩 모델을 받습니다. **5~15분** 걸릴 수 있습니다.
- 두 번째부터 같은 PC에서는 훨씬 빠릅니다.
- Word가 PDF 변환 중에 docx 파일을 열어 두면 실패할 수 있습니다.

---

## 자주 나는 문제

| 증상 | 확인 |
|------|------|
| `git` 을 찾을 수 없음 | Git 설치 후 PowerShell 재시작, `git --version` 확인 |
| `uv` 를 찾을 수 없음 | uv 설치 후 PowerShell 재시작 |
| `cd QuestionPicker` 실패 | `git clone` 한 위치로 이동. 폴더 이름은 **QuestionPicker** 인지 확인 |
| PDF 변환 실패 | Word 설치 여부, docx를 Word에서 열고 있지 않은지 |
| 문항이 0개 | `--topic` 을 바꿔 보기. `--print-matches` 로 점수 확인 |
| 한글 경로 오류 | PDF·프로젝트 경로에 특수문자가 없는지 확인 |
| 매우 느림 | 첫 실행(모델 다운로드)인지 확인 |

---

## 내부 동작 (참고)

```text
PDF + 주제
  → PDF에서 JSON 추출 (캐시: json/*-<pdf이름>.json)
  → 주제 임베딩 검색 → json/*-<주제>.json
  → Word + PDF (docx/, pdf/)
```

---

## 부록: 단계별 명령 (개발·디버그용)

### PDF → JSON

```powershell
uv run python pdf_to_json.py your.pdf
```

| 옵션 | 설명 |
|------|------|
| `--no-embed` | 임베딩 없이 추출만 |

### 주제 검색만

```powershell
uv run python search_questions.py your.pdf --topic 네트워크 --print-matches
```

| 옵션 | 설명 |
|------|------|
| `--min-score` | 유사도 하한 (기본 `0.50`) |
| `--top` | 상위 N개만 |
| `--rebuild-json` | PDF에서 JSON 다시 추출 |

### JSON → Word + PDF

```powershell
uv run python json_to_word.py json/0518-1634-윈도우10.json
```

### (선택) 텍스트 정리

```powershell
uv run python normalize_json.py your.json
```

정리 후 검색 품질을 바꾸려면 `pdf_to_json` 재실행 또는 `--rebuild-embeddings` 가 필요할 수 있습니다.

### PDF 텍스트만 확인

```powershell
uv run python read_example_pdf.py your.pdf
```

---

## 부록: JSON 형식 (요약)

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
      "embedding": [0.012, -0.034],
      "source": { "page": 1, "columns": ["left"] },
      "assets": [{ "type": "image", "path": "your_assets/q35.png" }]
    }
  ],
  "answer_key": [{ "no": 1, "answer": 3 }]
}
```

검색 결과 JSON에는 `embedding` 필드를 넣지 않습니다. 비공개 Hugging Face 모델을 쓸 때만 `HF_TOKEN` 환경 변수를 설정합니다.
