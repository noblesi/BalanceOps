#!/usr/bin/env sh
set -eu

SKIP_E2E=0
INCLUDE_TABULAR_BASELINE=0
PORT=8010

# args
while [ $# -gt 0 ]; do
  case "$1" in
    --skip-e2e) SKIP_E2E=1; shift ;;
    --include-tabular-baseline) INCLUDE_TABULAR_BASELINE=1; shift ;;
    --port) PORT="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# import 안정화(설치 안 했어도 -m 실행 가능)
export PYTHONPATH="$ROOT:$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

# .ci sandbox env (set if not already set)
: "${BALANCEOPS_DB:=$ROOT/.ci/balanceops.db}"
: "${BALANCEOPS_ARTIFACTS:=$ROOT/.ci/artifacts}"
: "${BALANCEOPS_CURRENT_MODEL:=$ROOT/.ci/artifacts/models/current.joblib}"
: "${PYTHONUNBUFFERED:=1}"

export BALANCEOPS_DB BALANCEOPS_ARTIFACTS BALANCEOPS_CURRENT_MODEL PYTHONUNBUFFERED

echo "[check] repo_root: $ROOT"

ARGS=""
if [ "$SKIP_E2E" -eq 1 ]; then ARGS="$ARGS --skip-e2e"; else ARGS="$ARGS --port $PORT"; fi
if [ "$INCLUDE_TABULAR_BASELINE" -eq 1 ]; then ARGS="$ARGS --include-tabular-baseline"; fi

CI_UNIX="$ROOT/.venv/bin/balanceops-ci-check"
CI_WIN="$ROOT/.venv/Scripts/balanceops-ci-check.exe"
if [ -x "$CI_UNIX" ]; then
  echo "[check] using console script: $CI_UNIX"
  # shellcheck disable=SC2086
  "$CI_UNIX" $ARGS
  exit $?
elif [ -f "$CI_WIN" ]; then
  echo "[check] using console script: $CI_WIN"
  # shellcheck disable=SC2086
  "$CI_WIN" $ARGS
  exit $?
elif command -v balanceops-ci-check >/dev/null 2>&1; then
  echo "[check] using console script: balanceops-ci-check"
  # shellcheck disable=SC2086
  balanceops-ci-check $ARGS
  exit $?
fi

PY="python"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
elif [ -f "$ROOT/.venv/Scripts/python.exe" ]; then
  PY="$ROOT/.venv/Scripts/python.exe"
fi

echo "[check] using python: $PY"
# shellcheck disable=SC2086
"$PY" -m balanceops.tools.ci_check $ARGS
