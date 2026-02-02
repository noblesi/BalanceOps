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

## 주요 API 엔드포인트

- GET `/health` : 헬스 체크
- GET `/model` : current 모델 정보
- GET `/runs` : run 목록
  - Query:
    - 'limit' (default: 20)
    - 'offset' (default: 0)
    - 'include_metrics' (default: false)
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

