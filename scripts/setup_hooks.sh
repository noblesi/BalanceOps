#!/usr/bin/env sh
set -eu

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

git config core.hooksPath .githooks
echo "[hooks] core.hooksPath set to .githooks"
echo "[hooks] pre-push hook enabled."
echo "[hooks] skip: git push --no-verify  OR  BALANCEOPS_SKIP_PRE_PUSH=1 git push"
