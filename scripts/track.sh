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

iso_time() {
  date +"%Y-%m-%dT%H:%M:%S%z" | sed -E 's/([+-][0-9]{2})([0-9]{2})$/\1:\2/'
}

emit() { echo "$*"; }

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

if [[ "$WRITE_REPORT" == "1" ]]; then
  mkdir -p "$(dirname "$report")"
  : > "$report"
  exec > >(tee -a "$report") 2>&1
fi

section "BalanceOps Track"
emit "repo: $ROOT"
emit "time: $(iso_time)"
emit "remote: $REMOTE"
emit "branch: $BRANCH"
emit "local_only: $LOCAL_ONLY"
emit "write_report: $WRITE_REPORT"

section "Local status"
run_git "git status -sb" status -sb
run_git "status porcelain (all changes)" status --porcelain
run_git "staged diff (name-status)" diff --cached --name-status
run_git "unstaged diff (name-status)" diff --name-status
run_git "added files staged only (A)" diff --cached --name-status --diff-filter=A
run_git "untracked files only" ls-files --others --exclude-standard
run_git "recent commits (-n 10)" log --oneline --decorate -n 10

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
    emit "=> fallback: 로컬 변경/추가 파일 중심으로 추적합니다."
  fi
fi

if [[ "$WRITE_REPORT" == "1" ]]; then
  emit ""
  emit "[track] report saved: $report"
fi
