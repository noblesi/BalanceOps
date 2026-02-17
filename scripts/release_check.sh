#!/usr/bin/env sh
set -eu

TAG="${1:-}"
REMOTE="${REMOTE:-origin}"
BRANCH="${BRANCH:-main}"
LOCAL_ONLY="${LOCAL_ONLY:-0}"
ALLOW_DIRTY="${ALLOW_DIRTY:-0}"

if [ -z "$TAG" ]; then
  echo "usage: ./scripts/release_check.sh vX.Y.Z"
  exit 2
fi

ROOT="$(git rev-parse --show-toplevel)"
cd "$ROOT"

fail() {
  echo ""
  echo "[release_check] ERROR: $1"
  exit 1
}

echo "[release_check] repo: $ROOT"
echo "[release_check] tag:  $TAG"
echo "[release_check] remote/branch: $REMOTE/$BRANCH"
echo "[release_check] local_only: $LOCAL_ONLY"

# 1) clean working tree
PORCELAIN="$(git status --porcelain || true)"
if [ "$ALLOW_DIRTY" != "1" ] && [ -n "$PORCELAIN" ]; then
  echo ""
  echo "$PORCELAIN"
  fail "워킹트리에 변경이 있습니다. 커밋/스태시 후 다시 시도하세요. (ALLOW_DIRTY=1로 우회 가능)"
fi

HEAD_SHA="$(git rev-parse HEAD)"
echo "[release_check] HEAD: $HEAD_SHA"

# 2) fetch + ahead/behind
if [ "$LOCAL_ONLY" != "1" ]; then
  if git fetch "$REMOTE" --tags >/dev/null 2>&1; then
    if git rev-parse --verify "$REMOTE/$BRANCH" >/dev/null 2>&1; then
      AB="$(git rev-list --left-right --count "HEAD...$REMOTE/$BRANCH")"
      AHEAD="$(echo "$AB" | awk '{print $1}')"
      BEHIND="$(echo "$AB" | awk '{print $2}')"
      echo "[release_check] ahead/behind vs $REMOTE/$BRANCH: $AHEAD/$BEHIND"
      if [ "$BEHIND" -gt 0 ]; then
        fail "로컬이 원격보다 뒤쳐져 있습니다(behind=$BEHIND). pull/rebase 후 태그를 찍으세요."
      fi
    fi
  else
    echo "[release_check] WARN: fetch 실패 -> 로컬 기준으로만 검사합니다."
  fi
fi

# 3) local tag check
if git rev-parse -q --verify "refs/tags/$TAG" >/dev/null 2>&1; then
  TAG_SHA="$(git rev-list -n 1 "$TAG")"
  echo "[release_check] local tag exists: $TAG -> $TAG_SHA"
  if [ "$TAG_SHA" != "$HEAD_SHA" ]; then
    echo ""
    echo "태그가 HEAD에 찍혀있지 않습니다."
    echo "  tag:  $TAG_SHA"
    echo "  HEAD: $HEAD_SHA"
    echo ""
    echo "해결 옵션:"
    echo "  (A) 태그를 HEAD로 다시 찍기(릴리스 전/팀 합의 필요):"
    echo "      git tag -d $TAG"
    echo "      git tag -a $TAG -m \"$TAG\""
    echo "      git push -f $REMOTE $TAG"
    echo "  (B) 다음 버전으로 새 태그 만들기(보수적)"
    fail "태그/HEAD 불일치"
  fi
else
  echo "[release_check] local tag not found: $TAG (OK: 태그 생성 전 검사)"
fi

# 4) remote tag check (optional)
if [ "$LOCAL_ONLY" != "1" ]; then
  RT="$(git ls-remote --tags "$REMOTE" "refs/tags/$TAG" || true)"
  if [ -n "$RT" ]; then
    # annotated tag deref(^{} ) 우선
    SHA="$(echo "$RT" | awk '{print $1}' | tail -n 1)"
    echo "[release_check] remote tag exists: $TAG -> $SHA"
    if [ "$SHA" != "$HEAD_SHA" ] && ! git rev-parse -q --verify "refs/tags/$TAG" >/dev/null 2>&1; then
      fail "원격에 이미 $TAG 태그가 있고(sha=$SHA), 현재 HEAD와 다릅니다. 새 버전 태그를 사용하세요."
    fi
  fi
fi

echo ""
echo "[release_check] OK"
echo "next:"
echo "  git tag -a $TAG -m \"$TAG\""
echo "  git push $REMOTE $BRANCH"
echo "  git push $REMOTE $TAG"
