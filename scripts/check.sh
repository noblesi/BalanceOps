#!/usr/bin/env sh
set -eu

SKIP_E2E=0
PORT=8010

# args
while [ $# -gt 0 ]; do
  case "$1" in
    --skip-e2e) SKIP_E2E=1; shift ;;
    --port) PORT="$2"; shift 2 ;;
    *) echo "unknown arg: $1" >&2; exit 2 ;;
  esac
done

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# .ci sandbox env (set if not already set)
: "${BALANCEOPS_DB:=$ROOT/.ci/balanceops.db}"
: "${BALANCEOPS_ARTIFACTS:=$ROOT/.ci/artifacts}"
: "${BALANCEOPS_CURRENT_MODEL:=$ROOT/.ci/artifacts/models/current.joblib}"
: "${PYTHONUNBUFFERED:=1}"

export BALANCEOPS_DB BALANCEOPS_ARTIFACTS BALANCEOPS_CURRENT_MODEL PYTHONUNBUFFERED

echo "[check] repo_root: $ROOT"

if command -v balanceops-ci-check >/dev/null 2>&1; then
  echo "[check] using console script: balanceops-ci-check"
  if [ "$SKIP_E2E" -eq 1 ]; then
    balanceops-ci-check --skip-e2e
  else
    balanceops-ci-check --port "$PORT"
  fi
  exit $?
fi

PY="python"
if [ -x "$ROOT/.venv/bin/python" ]; then
  PY="$ROOT/.venv/bin/python"
fi

echo "[check] using python: $PY"
if [ "$SKIP_E2E" -eq 1 ]; then
  "$PY" -m balanceops.tools.ci_check --skip-e2e
else
  "$PY" -m balanceops.tools.ci_check --port "$PORT"
fi
