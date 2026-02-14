# BalanceOps

**BalanceOps = “실험 추적(SQLite) + 모델 레지스트리(current 승격) + FastAPI 배포 + Streamlit 대시보드 + CI”**를 한 레포에서 굴리는 최소 단위 제품형 템플릿입니다.

- **Tracking**: 실행(run) / 메트릭(metrics) / 아티팩트(artifacts) / 모델 스테이지(models: candidate/current)를 SQLite에 기록
- **Registry**: 조건(policy)에 따라 candidate → current 승격
- **Serving**: FastAPI로 `/predict` 제공
- **Dashboard**: Streamlit으로 최근 run/metric/current 모델 확인
- **CI**: GitHub Actions로 smoke + pytest

> 현재는 “E2E 확인용 더미 모델(DummyBalanceModel)”이 기본으로 포함되어 있습니다.

---

## TL;DR (Windows / PowerShell)

```powershell
# 0) - (추천) E2E 원샷 점검: .\scripts\e2e.ps1 (DB 초기화 → 더미 학습/승격 → API 구동 → HTTP 스모크 → 종료)
.\scripts\e2e.ps1
# 포트가 겹치면: .\scripts\e2e.ps1 -Port 8010

# 0-1) (크로스플랫폼) Python E2E 원샷 점검
python -m balanceops.tools.e2e
# 포트가 겹치면: python -m balanceops.tools.e2e --port 8010

# ---- 또는 아래를 단계별로 실행 ----

# 1) 가상환경 생성 + editable 설치(개발용 포함)
.\scripts\bootstrap.ps1

# 2) DB 초기화 + 데모 run 기록
.\scripts\run_once.ps1

# 3) 더미 모델 학습 + (조건부) current 승격
.\scripts\train_dummy.ps1

# 4) API 서버
.\scripts\serve.ps1

# (선택) HTTP 스모크 체크 (/health + /predict)
.\scripts\smoke_http.ps1

# (선택) 스모크 옵션 예시
# - /predict 404도 실패로 처리(=CI/배포 전 체크용)
# .\scripts\smoke_http.ps1 -FailOnPredict404
# - health만 확인하고 싶다면
# .\scripts\smoke_http.ps1 -SkipPredict
# - 일시적인 네트워크/서버 스타트업 대응: 재시도
# .\scripts\smoke_http.ps1 -Retries 2 -RetryDelaySec 1

# (선택) 대시보드
.\scripts\dashboard.ps1
```

## CLI 커맨드 (editable 설치 시)

아래 커맨드는 `python -m ...` 대신 사용할 수 있습니다.

- `balanceops-ci-check [--skip-e2e] [--include-tabular-baseline] [--port 8010]` : 로컬 CI 원샷 점검(포맷/린트/테스트/선택 스모크)
- `balanceops-e2e --port 8010` : E2E 원샷 점검
- `balanceops-smoke-http --host 127.0.0.1 --port 8000` : 실행 중인 API에 smoke 요청
- `balanceops-demo-run` : 더미 run 생성(artifact + DB 기록)
- `balanceops-promote --run-id <RUN_ID>` : run_id로 current 수동 승격
- `balanceops-train-tabular-baseline --dataset-spec <PATH> [--no-auto-promote]` : Tabular Baseline 학습(CSV/Dataset Spec)

## 주요 API 엔드포인트

- GET `/health` : 헬스 체크
- GET `/model` : current 모델 정보
- GET `/runs` : run 목록
  - Query:
    - `limit` (default: 20)
    - `offset` (default: 0)
    - `include_metrics` (default: true)
- GET `/runs/latest` : 최신 run
- GET `/runs/{run_id}` : 특정 run 상세

---

### 예시 (PowerShell)

```powershell
# health
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/health"

# current model info
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/model"

# runs list
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/runs?limit=10&offset=0&include_metrics=true"

# latest run
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/runs/latest"

# specific run
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/runs/<run_id>"

# predict
$body = @{ features = @(0.1,0.2,-0.3,1.0,0.5,0.0,-0.2,0.9) } | ConvertTo-Json -Compress
Invoke-RestMethod -Method Post -Uri "http://127.0.0.1:8000/predict" -ContentType "application/json" -Body $body

# version
Invoke-RestMethod -Method Get -Uri "http://127.0.0.1:8000/version"

```

---

## 모델 승격 흐름(자동/수동)

BalanceOps는 모델 파일을 `artifacts/models/`에 두고, **서빙은 항상 `current.joblib`** 을 사용합니다.

- **candidate 생성**: 학습/실험(run) 결과로 후보 모델이 생성됨
- **승격(promote)**: 조건(policy)을 만족하거나, 수동으로 candidate → current 승격
- **서빙(predict)**: FastAPI가 `current.joblib`을 로드해서 `/predict`를 제공

### 수동 승격(스크립트)

```powershell
# 최신 run을 current로 승격
.\scripts\promote.ps1 -Latest

# 특정 run을 current로 승격
.\scripts\promote.ps1 -RunId "<run_id>"
```

---

## CI 개요

GitHub Actions에서는 보통 아래를 확인합니다.

- **requirements 설치 스모크(Windows + Linux)**: `pip install -r requirements.txt`가 깨지지 않는지 확인
- **pytest/스모크 테스트**: 최소 단위 테스트 및 엔드포인트 스모크(레포 설정에 따라)

---

### (선택) pre-push 훅으로 푸시 전 자동 점검

푸시 전에 `balanceops-ci-check --skip-e2e`를 자동 실행해 CI 실패를 미리 잡습니다.

- 설치(Windows): `.\scripts\setup_hooks.ps1`
- 설치(Linux/macOS): `./scripts/setup_hooks.sh`
- 스킵: `git push --no-verify` 또는 `BALANCEOPS_SKIP_PRE_PUSH=1 git push`


### 원샷 점검 스크립트 (추천)

로컬에서 CI와 동일한 점검을 한 번에 실행합니다. (기본은 `.ci/` sandbox 사용)

- Windows(PowerShell): `.\scripts\check.ps1 -SkipE2E`
- Linux/macOS: `./scripts/check.sh --skip-e2e`

Tabular Baseline 스모크까지 포함(선택, 승격 없음 / `--no-auto-promote`):
- Windows(PowerShell): `.\scripts\check.ps1 -SkipE2E -IncludeTabularBaseline`
- Linux/macOS / Git Bash: `./scripts/check.sh --skip-e2e --include-tabular-baseline`

E2E까지 포함하려면:
- Windows: `.\scripts\check.ps1`
- Linux/macOS: `./scripts/check.sh`

포트 변경:
- Windows: `.\scripts\check.ps1 -Port 8010`
- Linux/macOS: `./scripts/check.sh --port 8010`

---

## Repo 추적(Track) - 원격 변경/추가 파일 빠르게 확인

원격(예: `origin/main`) 기준으로 **들어오는 커밋/변경 파일/추가된 파일(A)** 을 요약해 보고,
원격 접근이 안 되면 **로컬에서 staged/unstaged/추가 파일**을 중심으로 추적합니다.

기본적으로 **리포트(.md)** 를 저장합니다.

- 리포트 경로: `.ci/track/track_YYYYMMDD_HHMMSS.md`

### Windows (PowerShell)

```powershell
# 기본: origin/main 기준 추적 + 리포트 저장
.\scripts\track.ps1

# 원격 fetch 생략(로컬만)
.\scripts\track.ps1 -LocalOnly

# 원격/브랜치 지정
.\scripts\track.ps1 -Remote origin -Branch main

# 리포트 저장 끄기
.\scripts\track.ps1 -WriteReport:$false
```

### Linux/macOS / Git Bash (bash)

```bash
# 기본: origin/main 기준 추적 + 리포트 저장
./scripts/track.sh

# 원격 fetch 생략(로컬만)
LOCAL_ONLY=1 ./scripts/track.sh

# 원격/브랜치 지정
REMOTE=origin BRANCH=main ./scripts/track.sh

# 리포트 저장 끄기
WRITE_REPORT=0 ./scripts/track.sh
```

> 원격 fetch가 실패(오프라인/권한/remote 미설정 등)해도 스크립트는 종료하지 않고,
> 로컬 변경사항 및 추가된 파일을 중심으로 계속 출력합니다.


### 로컬에서 CI와 동일하게 한 번에 점검하기

- Windows(PowerShell): `.\scripts\ci_check.ps1`
  - e2e 스킵: `.\scripts\ci_check.ps1 -SkipE2E`
  - Tabular Baseline 스모크 포함(승격 없음): `.\scripts\ci_check.ps1 -SkipE2E -IncludeTabularBaseline`
  - 포트 변경(e2e 포함 시): `.\scripts\ci_check.ps1 -Port 8010`
- Cross-platform: `python -m balanceops.tools.ci_check`
  - e2e 스킵: `python -m balanceops.tools.ci_check --skip-e2e`
  - Tabular Baseline 스모크 포함(승격 없음): `python -m balanceops.tools.ci_check --skip-e2e --include-tabular-baseline`
  - 포트 변경(e2e 포함 시): `python -m balanceops.tools.ci_check --port 8010`

> 기본은 `.ci/` sandbox(DB/Artifacts/Current)로 실행합니다.
> 로컬 기본 경로(`data/`, `artifacts/`)를 쓰려면: `python -m balanceops.tools.ci_check --no-ci-env`


---

## Artifacts 구조

BalanceOps는 **DB(SQLite)** 에 run/metrics/artifacts를 기록하고, 파일 산출물은 `artifacts/` 아래에 남깁니다.

### Runs (`artifacts/runs/`)

각 실행(run)은 아래 구조로 저장됩니다.

```text
artifacts/
  runs/
    <run_dir_name>/
      manifest.json
    _latest.json
    _by_id/
      <run_id>.json
```

#### `run_dir_name` 규칙

- 기본 형태: `YYYYMMDD_HHMMSS_<kind>_<shortid>`
  - 예: `20260126_092143_demo_8e013cbf`
  - `shortid`는 `run_id(UUID)`의 앞 8자리입니다.
  - 시간은 **UTC** 기준입니다. (필요하면 KST로 변경 가능)
- 레거시 실행이 남아있는 경우, 폴더명이 UUID(`artifacts/runs/<run_id>/`)일 수 있습니다.
  - 이 경우에도 아래 포인터 파일들을 통해 동일하게 접근합니다.

#### `manifest.json`

각 run 폴더에는 `manifest.json`이 생성됩니다.

- run_id / created_at / kind / status
- metrics 요약(주요 지표 스냅샷)
- artifacts_dir / db_path

#### 포인터 파일: _latest.json / _by_id/<run_id>.json
- artifacts/runs/_latest.json
    - 가장 최근 run을 가리키는 포인터입니다.
    - API의 /runs/latest가 가능한 경우 이 파일을 우선 사용합니다.
- artifacts/runs/_by_id/<run_id>.json
    - run_id(UUID) → manifest_path 매핑입니다.
    - 폴더명이 UUID가 아니어도 run_id만으로 run 위치를 빠르게 찾기 위해 사용합니다.
    - API /runs/{run_id}, 대시보드(run detail)에서 이 포인터가 있으면 파일 스캔 없이 manifest를 찾아옵니다.

### Models (`artifacts/models/`)

```text
artifacts/
  models/
    candidates/
      <run_id>_dummy.joblib
    current.joblib
```

- candidates/: 각 run의 후보 모델
- current.joblib: 현재 서빙에 사용하는 모델(승격 시 갱신)

### 경로 설정(환경변수)

기본 경로는 아래와 같고, 필요 시 환경변수로 변경할 수 있습니다.

- `BALANCEOPS_DB` (기본: `data/balanceops.db`)
- `BALANCEOPS_ARTIFACTS` (기본: `artifacts/`)
- `BALANCEOPS_CURRENT_MODEL` (기본: `artifacts/models/current.joblib`)

예시(Windows PowerShell):

```powershell
$env:BALANCEOPS_DB = "data/balanceops.db"
$env:BALANCEOPS_ARTIFACTS = "artifacts"
$env:BALANCEOPS_CURRENT_MODEL = "artifacts/models/current.joblib"
```
---

## Troubleshooting

### 1. CI에서 `ruff format --check .`가 실패해요
로컬에서 포맷을 먼저 맞춘 뒤 다시 푸시하세요.

```powershell
ruff format .
ruff check .
pytest -q
```

### 2. pre-push에서 막혀요 (로컬 CI 체크 실패)
git push 전에 훅이 ruff/pytest를 실행합니다. 아래 “원샷 점검”으로 한 번에 확인할 수 있어요.

```powershell
.\scripts\check.ps1
```

### 3. Dashboard에서 API /version 을 가져오지 못했습니다
대개 아래 중 하나입니다.

- API 서버가 꺼져있음
- API URL이 잘못됨(포트/호스트)
- 방화벽/네트워크 문제
- 서버가 응답은 했지만 /version이 에러를 반환함

해결 방법

- API 실행
.\scripts\serve.ps1

- 대시보드의 API URL이 http://127.0.0.1:8000(또는 실제 서버 주소)인지 확인

- 대시보드에서 새로고침 버튼을 눌러 캐시를 갱신

### 4. Dashboard에 No runs yet가 떠요
아직 실험(run)이 생성되지 않은 상태입니다. 아래 중 하나를 실행해 run을 만든 뒤 새로고침하세요.

.\scripts\run_once.ps1
# 또는
python -m balanceops.pipeline.demo_run

### 5. /predict가 NO_CURRENT_MODEL로 실패해요
current 모델이 아직 승격되지 않았습니다. 더미 학습/승격을 실행해 current를 만든 뒤 다시 호출하세요.

.\scripts\train_dummy.ps1
# 또는
python -m balanceops.pipeline.train_dummy

### 6. 포트 충돌이 나요 (8000 / 8501)
이미 같은 포트를 쓰는 프로세스가 있을 수 있어요.

- API(FastAPI): 기본 8000
- Dashboard(Streamlit): 기본 8501

해결

- 기존 실행 중인 터미널/프로세스를 종료하거나
- 다른 포트로 실행(예: API는 8001, 대시보드는 8502 등)

### 7. Windows에서 스크립트 실행이 차단돼요
PowerShell 실행 정책 때문에 .ps1 실행이 막힐 수 있습니다.

현재 사용자 범위에서만 허용하려면:

Set-ExecutionPolicy -Scope CurrentUser RemoteSigned

### 8. VS Code에서 `httpx` 같은 import를 못 찾는다고(Pylance) 떠요
이 경고는 **터미널(base/.venv)을 무엇으로 쓰느냐**보다, VS Code가 **어떤 Python 인터프리터(가상환경)를 선택했느냐**에 따라 발생합니다.

해결 순서(Windows 기준):

1) VS Code에서 `Ctrl+Shift+P` → **Python: Select Interpreter**
2) `BalanceOps\.venv\Scripts\python.exe` (또는 `.venv`)를 선택
3) 필요하면 창 재로드(Developer: Reload Window)

그리고 선택된 인터프리터에서 `httpx`가 설치돼 있어야 합니다.

```powershell
# 가장 안전: 현재 인터프리터에 설치
python -m pip install -r requirements.txt

# 또는 단일 패키지만
python -m pip install httpx
```

## Docker / Compose (API + Dashboard)

로컬에 Python을 설치하지 않아도 **API + 대시보드**를 한 번에 띄울 수 있습니다.

```bash
docker compose up --build
```
- API: http://localhost:8000/health
- Dashboard: http://localhost:18501


## Tabular Baseline (CSV)

### 0) Linux/macOS / Git Bash (bash) 실행

```bash
# 인자 없이 데모 실행(데모 CSV 생성 + 학습/추적, 기본 no-auto-promote)
./scripts/train_tabular_baseline.sh

# 내 CSV로 실행
./scripts/train_tabular_baseline.sh --csv-path ./data/my.csv --target-col label

# Dataset Spec(JSON)로 실행
./scripts/train_tabular_baseline.sh --dataset-spec ./examples/dataset_specs/csv_demo.json

# 금융(신용) 데모 (승격 없이 안전 실행)
./scripts/train_tabular_baseline.sh --dataset-spec ./examples/dataset_specs/finance_credit_demo.json --no-auto-promote
```

### 1) 인자 없이 데모 실행 (Windows/PowerShell)

```powershell
.\scripts\train_tabular_baseline.ps1
```

실행 시 `.ci/datasets/toy_binary.csv` 데모 CSV를 자동 생성하고 학습/추적까지 수행합니다.

### 2) 내 CSV로 실행

```powershell
.\scripts\train_tabular_baseline.ps1 -CsvPath .\data\my.csv -TargetCol label
```

### 3) Dataset Spec(JSON)로 실행

```powershell
balanceops-train-tabular-baseline --dataset-spec .\examples\dataset_specs\csv_demo.json

python -m balanceops.pipeline.train_tabular_baseline --dataset-spec .\examples\dataset_specs\csv_demo.json
```

- Dataset Spec 필드(요약)
  - `kind`: `csv`
  - `params.path`: CSV 경로
  - `params.target_col`: 타깃 컬럼명
  - `params.one_hot`: 범주형 one-hot 여부(기본 `true`)
  - `params.dropna`: 결측행 제거 여부(기본 `true`)
  - `split`: (옵션) `seed` / `test_size` 같은 분할 힌트  
    - 현재 baseline은 **CLI 인자 우선**(옵션이 있으면)으로 동작합니다.

### 4) 금융(신용) 데모 예시 실행 (Dataset Spec)

- 데이터: `examples/datasets/finance_credit_toy.csv`
- 스펙: `examples/dataset_specs/finance_credit_demo.json`
- 타깃 컬럼: `default` (0/1)

```powershell
# (추천) current 승격 없이 안전하게 학습만
balanceops-train-tabular-baseline --dataset-spec .\examples\dataset_specs\finance_credit_demo.json --no-auto-promote

python -m balanceops.pipeline.train_tabular_baseline --dataset-spec .\examples\dataset_specs\finance_credit_demo.json --no-auto-promote

# 최신 run 포인터 확인
type .\artifacts\runs\_latest.json
```

실행 결과는 `artifacts/` 아래에 기록됩니다.

- 최신 run 포인터: `artifacts\runs\_latest.json`
- candidate 모델: `artifacts\models\candidates\<run_id>_tabular_baseline.joblib`

---

## Dashboard에서 방금 만든 run 빠르게 찾기

### 1) 서버 실행 (터미널 2개 권장)

```powershell
# 터미널 A: API 실행
.\scripts\serve.ps1

# 터미널 B: 대시보드 실행
.\scripts\dashboard.ps1
```

대시보드 실행 후 터미널에 출력되는 주소(예: `http://127.0.0.1:8501` 또는 안내된 포트)로 접속합니다.

### 2) 최신 run_id 확인

```powershell
type .\artifacts\runs\_latest.json
```

여기서 `run_id` / `run_dir_name` 값을 복사합니다.

### 3) 대시보드에서 run 검색

- **Recent Runs** 화면에서 검색/필터 입력칸에 `run_id` 또는 `run_dir_name`을 붙여넣습니다.
- 메트릭 기준으로 보고 싶다면 `bal_acc`, `recall_1` 같은 메트릭 이름으로 필터링합니다.
- 선택한 run의 `manifest.json`, `dataset.json` 경로가 함께 표시되므로 재현(재학습)과 비교가 쉬워집니다.

### Troubleshooting (대시보드가 API를 못 읽을 때)

- API가 켜져 있는지 확인: `.\scripts\serve.ps1`
- 대시보드 설정된 API URL/포트가 실제 실행 포트와 같은지 확인
- `/version` 실패 메시지가 뜨면 먼저 API 터미널 로그를 확인

> 포트(8501/18501 등)는 환경/스크립트에 따라 다를 수 있으니, **dashboard.ps1 실행 시 출력되는 URL**을 기준으로 안내합니다.