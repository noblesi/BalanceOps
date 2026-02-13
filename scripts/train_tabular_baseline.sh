#!/usr/bin/env sh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

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

# 실행기 선택: venv CLI > PATH CLI > venv python -m > python3/python
CLI_VENV="$ROOT/.venv/bin/balanceops-train-tabular-baseline"
if [ -x "$CLI_VENV" ]; then
  echo "[train_tabular_baseline] using CLI: $CLI_VENV"
  "$CLI_VENV" "$@"
  exit $?
fi

if command -v balanceops-train-tabular-baseline >/dev/null 2>&1; then
  echo "[train_tabular_baseline] using CLI: balanceops-train-tabular-baseline"
  balanceops-train-tabular-baseline "$@"
  exit $?
fi

PY="$ROOT/.venv/bin/python"
if [ ! -x "$PY" ]; then
  if command -v python >/dev/null 2>&1; then
    PY="python"
  elif command -v python3 >/dev/null 2>&1; then
    PY="python3"
  else
    echo "python/python3 not found" >&2
    exit 127
  fi
fi

echo "[train_tabular_baseline] using python: $PY"
"$PY" -m balanceops.pipeline.train_tabular_baseline "$@"
