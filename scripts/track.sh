#!/usr/bin/env bash
set -euo pipefail

REMOTE="${REMOTE:-origin}"
BRANCH="${BRANCH:-main}"
LOCAL_ONLY="${LOCAL_ONLY:-0}"
WRITE_REPORT="${WRITE_REPORT:-1}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ts="$(date +%Y%m%d_%H%M%S)"
report="$ROOT/.ci/track/track_${ts}.md"

emit() { echo "$*"; }
emit_report() {
  if [[ "$WRITE_REPORT" == "1" ]]; then
    mkdir -p "$(dirname "$report")"
    cat >> "$report"
  fi
}

section() {
  emit ""
  emit "================================================================================"
  emit "$1"
  emit "================================================================================"
}

run_git() {
  local title="$1"; shift
  emit ""
  emit "## $title"
  emit '```'
  if git "$@" 2>&1; then :; else echo "[exit=$?]"; fi
  emit '```'
}

section "BalanceOps Track"
emit "repo: $ROOT"
emit "time: $(date -Is)"

section "Local status"
run_git "git status -sb" status -sb
run_git "untracked files (??)" status --porcelain

if [[ "$LOCAL_ONLY" == "1" ]]; then
  emit ""
  emit "(LOCAL_ONLY=1: 원격 fetch 생략)"
else
  section "Remote fetch"
  if git fetch "$REMOTE" >/dev/null 2>&1; then
    emit "fetch ok: $REMOTE"
    upstream="${REMOTE}/${BRANCH}"

    if git rev-parse --verify "$upstream" >/dev/null 2>&1; then
      section "Upstream diff"
      run_git "ahead/behind (HEAD...$upstream)" rev-list --left-right --count "HEAD...${upstream}"
      run_git "incoming commits (HEAD..$upstream)" log --oneline --decorate --max-count 30 "HEAD..${upstream}"
      run_git "changed files (name-status)" diff --name-status "HEAD..${upstream}"
      run_git "added files only (A)" diff --name-status --diff-filter=A "HEAD..${upstream}"
    else
      emit "upstream ref가 없습니다: $upstream"
    fi
  else
    emit "원격 fetch 실패: $REMOTE"
    emit "=> fallback: 로컬에서 staged/unstaged/추가 파일만 추적합니다."
  fi
fi

if [[ "$WRITE_REPORT" == "1" ]]; then
  {
    section "BalanceOps Track"
    emit "repo: $ROOT"
    emit "time: $(date -Is)"
    section "Local status"
    run_git "git status -sb" status -sb
    run_git "untracked files (??)" status --porcelain
  } | emit_report
  emit ""
  emit "[track] report saved: $report"
fi
