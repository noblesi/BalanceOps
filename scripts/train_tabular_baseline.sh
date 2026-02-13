#!/usr/bin/env sh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

# Git Bash/WSL에서도 소스 import 되도록 경로 보강(설치 안 했어도 모듈 탐색 가능)
# (설치가 되어있으면 영향 거의 없음)
export PYTHONPATH="$ROOT:$ROOT/src${PYTHONPATH:+:$PYTHONPATH}"

# 인자가 없으면 데모 CSV 생성 후 실행 (승격은 기본적으로 막음)
if [ "$#" -eq 0 ]; then
  DEMO_DIR="$ROOT/.ci/datasets"
  mkdir -p "$DEMO_DIR"

  DEMO_PATH="$DEMO_DIR/toy_binary.csv"
  cat >"$DEMO_PATH" <<'CSV'
f1,f2,y
1,10,0
2,9,0
3,8,0
4,7,1
5,6,1
6,5,1
CSV

  echo "[train_tabular_baseline] demo csv generated: $DEMO_PATH"
  set -- --csv-path "$DEMO_PATH" --target-col y --no-auto-promote
fi

# ---- 실행기 선택: venv CLI(리눅스/맥) > venv CLI(윈도우) > PATH CLI > venv python > python3/python ----

# 1) venv CLI (unix)
CLI_UNIX="$ROOT/.venv/bin/balanceops-train-tabular-baseline"
if [ -x "$CLI_UNIX" ]; then
  echo "[train_tabular_baseline] using CLI: $CLI_UNIX"
  "$CLI_UNIX" "$@"
  exit $?
fi

# 2) venv CLI (windows)
CLI_WIN_EXE="$ROOT/.venv/Scripts/balanceops-train-tabular-baseline.exe"
CLI_WIN_SHIM="$ROOT/.venv/Scripts/balanceops-train-tabular-baseline"
if [ -f "$CLI_WIN_EXE" ]; then
  echo "[train_tabular_baseline] using CLI: $CLI_WIN_EXE"
  "$CLI_WIN_EXE" "$@"
  exit $?
elif [ -f "$CLI_WIN_SHIM" ]; then
  echo "[train_tabular_baseline] using CLI: $CLI_WIN_SHIM"
  "$CLI_WIN_SHIM" "$@"
  exit $?
fi

# 3) PATH CLI
if command -v balanceops-train-tabular-baseline >/dev/null 2>&1; then
  echo "[train_tabular_baseline] using CLI: balanceops-train-tabular-baseline"
  balanceops-train-tabular-baseline "$@"
  exit $?
fi

# 4) venv python (windows/unix)
PY_WIN="$ROOT/.venv/Scripts/python.exe"
PY_UNIX="$ROOT/.venv/bin/python"
if [ -f "$PY_WIN" ]; then
  echo "[train_tabular_baseline] using python: $PY_WIN"
  "$PY_WIN" -m balanceops.pipeline.train_tabular_baseline "$@"
  exit $?
elif [ -x "$PY_UNIX" ]; then
  echo "[train_tabular_baseline] using python: $PY_UNIX"
  "$PY_UNIX" -m balanceops.pipeline.train_tabular_baseline "$@"
  exit $?
fi

# 5) fallback python
if command -v python >/dev/null 2>&1; then
  echo "[train_tabular_baseline] using python: python"
  python -m balanceops.pipeline.train_tabular_baseline "$@"
  exit $?
elif command -v python3 >/dev/null 2>&1; then
  echo "[train_tabular_baseline] using python: python3"
  python3 -m balanceops.pipeline.train_tabular_baseline "$@"
  exit $?
fi

echo "python/python3 not found" >&2
exit 127
