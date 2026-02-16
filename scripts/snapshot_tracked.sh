#!/usr/bin/env bash
set -euo pipefail

NAME="${NAME:-BalanceOps-tracked}"
OUTDIR="${OUTDIR:-.ci/snapshots}"
NO_UNTRACKED="${NO_UNTRACKED:-0}"
NO_LATEST="${NO_LATEST:-0}"

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

ts="$(date +%Y%m%d_%H%M%S)"
sha="$(git rev-parse --short=7 HEAD)"

mkdir -p "$OUTDIR"
zip_path="$OUTDIR/${NAME}_${ts}_${sha}.zip"
latest_path="$OUTDIR/${NAME}_latest.zip"

rm -f "$zip_path"

python - "$zip_path" "$NO_UNTRACKED" <<'PY'
import os
import subprocess
import sys
import zipfile

zip_path = sys.argv[1]
no_untracked = sys.argv[2] == "1"
repo_root = os.getcwd()

def git_lines(*args: str) -> list[str]:
    p = subprocess.run(["git", *args], check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    return [line for line in p.stdout.splitlines() if line.strip()]

paths = git_lines("ls-files")
if not no_untracked:
    paths += git_lines("ls-files", "--others", "--exclude-standard")

paths = sorted(set(paths))

with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
    for rel in paths:
        src = os.path.join(repo_root, rel)
        if not os.path.isfile(src):
            continue
        zf.write(src, arcname=rel.replace("\\", "/"))

print(f"[snapshot] repo: {repo_root}")
print(f"[snapshot] out:  {zip_path}")
PY

if [[ "$NO_LATEST" != "1" ]]; then
  cp -f "$zip_path" "$latest_path"
  echo "[snapshot] latest: $latest_path"
fi
