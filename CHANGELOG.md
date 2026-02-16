# Changelog

All notable changes to this project will be documented in this file.

This format is based on **Keep a Changelog**, and this project aims to follow **Semantic Versioning**.

- Keep a Changelog: https://keepachangelog.com/en/1.1.0/
- Semantic Versioning: https://semver.org/spec/v2.0.0.html

---

## [Unreleased]

### Added
- (예) 새 기능/스크립트/문서

### Changed
- (예) 동작 변경/개선

### Fixed
- (예) 버그 수정

---

## [0.1.0] - 2026-02-XX

### Added
- 실험 추적(Tracking): run/metrics/artifacts를 SQLite + artifacts/에 기록
- 모델 레지스트리(Registry): candidate → current 승격(promote)
- 서빙(Serving): FastAPI `/predict` 제공 + `/version` 빌드/커밋 식별 정보 제공
- 대시보드(Dashboard): 최근 run/metric/current 모델 확인(Streamlit)
- CI: GitHub Actions smoke + pytest
- 로컬 점검 스크립트: check/ci_check/e2e/smoke_http 등

[Unreleased]: https://github.com/noblesi/BalanceOps/compare/v0.1.0...HEAD
[0.1.0]: https://github.com/noblesi/BalanceOps/releases/tag/v0.1.0
