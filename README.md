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
