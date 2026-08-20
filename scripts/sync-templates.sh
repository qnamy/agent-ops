#!/bin/bash
# 라이브 루틴 문서 → 게시 템플릿 로컬 동기화 (푸시는 하지 않는다 — 공개 관문은 사람이 확인)
# 사용: bash sync-templates.sh   (PostToolUse 훅 hook-routine-sync.py가 호출)
set -u

REPO="$HOME/workspace/agent-ops"
LOG="$REPO/.sync-templates.log"

{
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] sync start"

  if ! python3 "$REPO/scripts/sanitize.py"; then
    echo "sanitize/leak-check 실패 — 커밋하지 않음"
    exit 1
  fi

  cd "$REPO" || exit 1
  git add routines/templates

  if git diff --cached --quiet; then
    echo "변경 없음"
    exit 0
  fi

  git commit -m "chore: 루틴 템플릿 자동 동기화 (라이브 지시서 변경 반영)" --no-verify
  echo "커밋 완료 (푸시는 수동): $(git rev-parse --short HEAD)"
} >> "$LOG" 2>&1
