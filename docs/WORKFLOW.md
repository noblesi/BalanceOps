# BalanceOps Workflow (Task-based Commits)

## 목표
- 변경을 “태스크 단위”로 쪼개서 커밋
- 커밋 메시지 규칙을 통일
- 로컬/CI에서 재현 가능하게 점검 루틴을 고정

---

## 태스크 단위 커밋 기준
하나의 커밋은 아래 중 1개 목적만 포함합니다.

- 기능 1개 추가 / 수정 1개
- 문서 1개 주제 정리
- 스크립트 1개 추가/수정
- 테스트 1개 묶음 추가/수정
- 리팩토링 1개 범위(모듈 1개 등)

❌ 피하기
- “문서 + 기능 + 리팩토링” 섞인 커밋
- 여러 태스크를 한 커밋에 몰아넣기

---

## 커밋 메시지 규칙
### Subject 형식
`<프리픽스>: <한 줄 요약>`

프리픽스 예시:
- 문서 / 도구 / 스크립트 / API / 대시보드 / 테스트 / 수정 / 정리 / 빌드 / CI

예시:
- `도구: origin 변경 추적(track) 스크립트 추가`
- `문서: Troubleshooting 섹션 추가`
- `대시보드: created_at KST 표시`

### Body(권장)
- Why: 왜 바꿨는가?
- What: 무엇을 바꿨는가?
- Impact/Notes: 영향, 사용법, 주의점

---

## 기본 점검 루틴(권장)
### 1) 변경 확인
```powershell
git status -sb
git diff
```

### 2) 로컬 CI 원샷 점검
.\scripts\check.ps1

### 3) 태스크 범위만 stage
git add <files...>
git diff --cached

### 4) 커밋 (템플릿 사용)
git commit

### 5) push
git push

---

## 릴리스(Versioning & Tagging)

### 1) 원칙
- 변경 기록은 `CHANGELOG.md`에 남깁니다.
- 릴리스 버전은 `vX.Y.Z` 태그로 고정합니다. (예: `v0.1.0`)
- 태그는 **CI가 green**인 커밋에서만 찍습니다.

### 2) 릴리스 체크리스트
1. `CHANGELOG.md`의 `[Unreleased]`를 정리하고, 새 버전 섹션을 추가
2. (선택) `pyproject.toml`의 `version`을 릴리스 버전으로 갱신
3. 로컬 점검:
   - Windows: `.\scripts\check.ps1`
   - Linux/macOS: `./scripts/check.sh`
4. 태그 생성 + 푸시:
   - `git tag -a v0.1.0 -m "BalanceOps v0.1.0"`
   - `git push origin v0.1.0`

### 3) GitHub Releases(선택)
- 릴리스 노트는 `CHANGELOG.md`의 해당 버전 섹션을 그대로 사용합니다.
