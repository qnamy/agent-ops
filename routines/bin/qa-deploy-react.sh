#!/bin/sh
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
# deploy-approval 배포 승인 봇 ✅(white_check_mark) 반응 추가 헬퍼.
# 사용법: sh bin/deploy-approval-react.sh <channel> <message_ts>
#
# 봇 토큰은 상태 루트의 .deploy-approval-bot-token 에서 읽는다(명령행/로그에 노출 안 함).
# 토큰은 `.gitignore` 안의 state/에 남고 이 스크립트만 저장소에 있다 — state/에
# 두면 새 워크트리에 없어 그 회차의 ✅가 통째로 실패한다.
# 응답 JSON을 stdout 으로 그대로 출력한다: {"ok":true} 성공 / {"ok":false,"error":"already_reacted"} 멱등.
ROOT="${ROUTINE_STATE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)/state}"
TOKEN_FILE="$ROOT/.deploy-approval-bot-token"
if [ ! -s "$TOKEN_FILE" ]; then
  echo '{"ok":false,"error":"missing_bot_token_file"}'
  exit 1
fi
TOKEN=$(cat "$TOKEN_FILE")
curl -s -H "Authorization: Bearer $TOKEN" \
  -d "channel=$1" \
  -d "timestamp=$2" \
  -d "name=white_check_mark" \
  https://slack.com/api/reactions.add
