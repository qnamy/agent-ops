#!/bin/sh
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
# orca automation 6개를 --disabled로 만든다. 1회 이행 작업이므로 upsert 분기를
# 두지 않는다 — 같은 이름이 이미 있으면 orca가 거부하고 사람이 확인한다.
set -eu
R="$(cd "$(dirname "$0")/.." && pwd)"
WS="path:$R"

mk() {  # mk <name> <cron> <precheck-timeout|-|none>
  name="$1"; cron="$2"; pt="$3"
  set -- orca automations create \
    --name "$name" \
    --trigger "$cron" \
    --prompt "$R/prompts/$name.md 를 읽고 그 지시를 지금 그대로 수행하라." \
    --provider codex \
    --workspace "$WS" --workspace-mode existing \
    --timezone Asia/Seoul \
    --fresh-session --disabled
  # 설계 DEC-001에서 precheck가 없는 automation은 붙이지 않는다 — 게이트가
  # 막을 회차가 없는데 실행 경로만 하나 늘고, precheck 자체의 실패로 그 회차가
  # 안 돌 수 있다.
  if [ "$pt" != "none" ]; then
    set -- "$@" --precheck "bash $R/bin/precheck.sh $name"
    [ "$pt" = "-" ] || set -- "$@" --precheck-timeout "$pt"
  fi
  echo "== $name"
  "$@"
}

# ADO·Slack 조회와 fetch가 붙는 다섯은 precheck 예산을 180초로 준다.
mk pr-review-intake        '*/10 7-20 * * 1-5' 180
mk pr-review-resolve       '*/10 7-20 * * 1-5' 180
mk pr-review-merged        '0 17 * * 1-5'      180
mk deploy-approve-intake   '*/10 7-20 * * 1-5' 180
mk deploy-approve-resolve  '*/10 7-20 * * 1-5' 180
# 파일만 보는 하나는 precheck를 붙이지 않는다.
mk code-convention-digest  '0 8 * * 5'         none
