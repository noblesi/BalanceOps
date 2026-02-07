#!/usr/bin/env bash
set -euo pipefail

GLOBAL="${GLOBAL:-0}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

TEMPLATE="$ROOT/.gitmessage.txt"
if [[ ! -f "$TEMPLATE" ]]; then
  echo "Commit template not found: $TEMPLATE" >&2
  exit 1
fi

SCOPE="--local"
if [[ "$GLOBAL" == "1" ]]; then
  SCOPE="--global"
fi

git config $SCOPE commit.template "$TEMPLATE"
git config $SCOPE commit.cleanup strip >/dev/null 2>&1 || true

echo "[commit-template] configured ($SCOPE)"
echo "  template: $TEMPLATE"
echo ""
echo "Usage:"
echo "  git commit   # template will appear in your editor"
