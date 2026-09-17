#!/bin/sh
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
# pr-session.sh <verb> ... — PR별 리뷰 세션의 수명주기를 소유한다.
#
# 오케스트레이터가 diff를 읽으면 회차가 끝날 때까지 매 턴 다시 읽힌다. 코드
# 판정을 다른 세션에서 돌리되, 서브에이전트가 아니라 orca 터미널을 쓴다. 기저
# 컨텍스트 비용은 서로 같은데(2026-09-16 실측 29,647 대 27,122) 서브에이전트는
# 부모 턴 안에서만 살아 회차를 넘기지 못한다.
#
# 세션의 워크트리는 대상 레포가 아니라 이 워크스페이스다. 샌드박스가
# workspace-write라 레포에 만들면 state/에 결과를 쓸 수 없다.
#
# 대장은 key별 파일이다. 단일 JSON을 read-modify-replace하면 같은 10분에 뜨는
# intake와 resolve가 서로의 등록·제거를 덮어쓴다(R-10).
#
# verbs:
#   ensure <key>                      터미널 보장, 핸들 출력
#   ask    <key> <promptfile>       지시 후 결과 대기. 성공 시 `ok <결과경로>`
#   close  <key>                      터미널 종료 + 대장에서 제거
#   sweep  <key>...                   인자로 준 key 외의 터미널을 전부 종료
#
# 환경변수:
#   PR_SESSION_TIMEOUT_MS  요청 1건의 대기 상한 (기본 300000)
set -u
ROOT="${ROUTINE_STATE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)/state}"
WS="$(cd "$(dirname "$0")/.." && pwd)"
REG="$ROOT/pr-sessions"
# 실제 PR 리뷰는 10분을 넘는다 — 2026-09-16 PR 19108에서 워커가 지적 5건을
# 내는 데 약 12분이 걸렸고 300초 상한이 그 결과를 버렸다.
TIMEOUT="${PR_SESSION_TIMEOUT_MS:-1200000}"

# 저장 키는 원문 key의 **가역 인코딩**이다. 해시 접미사는 충돌 확률을 낮출 뿐
# 일대일이 아니어서 서로 다른 PR이 같은 대장·결과 파일을 공유할 수 있다(R-10).
slug() {
  printf '%s' "$1" | python3 -c 'import sys,urllib.parse; print(urllib.parse.quote(sys.stdin.read(), safe=""))'
}

regfile() { printf '%s/%s' "$REG" "$(slug "$1")"; }
# 결과 경로는 **ask 호출마다 고유**하다. 늦게 도착한 옛 요청의 결과가 다른
# 요청의 완료 신호가 될 수 없고, 그래서 세션을 죽여 정리할 필요가 없어진다.
# 세션을 죽이는 정리는 락을 잃은 회차가 새 회차의 터미널·대장을 파괴하는
# 순서를 만들었다(리뷰 9라운드 R-09).
resfile() {
  printf '%s/review-result.%s.%s.json' "$ROOT" "$(slug "$1")" "${2:-latest}"
}

alive() { [ -n "${1:-}" ] && orca terminal show --terminal "$1" >/dev/null 2>&1; }

# 종료는 `close`의 exit 0으로만 인정한다. `terminal_handle_stale`은 종료 receipt가
# 아니라 selector 거부이며, Orca 1.4.203에서 runtime 재기동·graph 교체·PTY
# 세대 교체처럼 **PTY가 살아 있는** 경우에도 나온다(리뷰 3라운드 R-15).
gone() { orca terminal close --terminal "$1" --tab >/dev/null 2>&1; }

# 상태를 모르는 세션을 버린다. 결과 파일도 함께 지워, 늦게 도착할 쓰기가 다음
# 요청의 완료 신호로 읽히지 않게 한다.
verb="${1:-}"; shift 2>/dev/null || true
mkdir -p "$REG"

case "$verb" in
ensure)
  key="$1"; rf="$(regfile "$key")"
  h="$(cat "$rf" 2>/dev/null || true)"
  if alive "$h"; then printf '%s\n' "$h"; exit 0; fi
  # `show` 실패가 Orca 조회의 일시 실패일 수 있다. 확인 없이 대장을 덮어쓰면
  # 살아 있는 세션이 close·sweep 대상에서 사라져 누수된다(R-15). 종료를
  # 확인하지 못하면 이번 ensure를 실패시키고 다음 회차에 맡긴다.
  if [ -n "$h" ]; then
    # 종료를 확인하지 못해도 대장을 비우고 새 세션으로 간다. 결과 경로가
    # 핸들별이므로 옛 worker가 새 요청의 완료 신호를 만들 수 없고, 남는 것은
    # 유휴 PTY 누수뿐이다. 여기서 회차를 세우면 그 PR이 사람이 치울 때까지
    # 영구히 미처리가 된다 — 누수보다 나쁜 교환이다(R-14 기각).
    gone "$h" || echo "leaked-session: $h" >&2
    rm -f "$rf"
  fi
  # 무인 회차에는 승인 프롬프트에 답할 사람이 없다(R-08). Claude Code의
  # `dontAsk`는 프롬프트를 띄우는 대신 **거부**하므로 필요한 것만 연다 —
  # 레포 읽기용 git과 결과 JSON 쓰기다. codex의 workspace-write가 워크스페이스
  # 전체 쓰기를 허용했던 것보다 좁다. 레포 읽기는 `--add-dir`가 연다.
  out="$(orca terminal create --worktree "path:$WS" --title "review $key" \
        --command "claude --permission-mode dontAsk --add-dir $HOME/work --allowedTools Write Read Glob Grep 'Bash(git --no-optional-locks:*)'" --json 2>/dev/null)"
  h="$(printf '%s' "$out" | python3 -c 'import json,sys
try: d=json.load(sys.stdin)
except Exception: print(""); raise SystemExit
print(((d.get("result") or {}).get("terminal") or {}).get("handle",""))')"
  [ -n "$h" ] || { echo "create-failed"; exit 1; }
  # TUI가 뜨기 전에 프롬프트를 보내면 셸로 들어간다. 프롬프트 표시를 본다.
  boot=0
  while [ "$boot" -lt 90 ]; do
    orca terminal read --terminal "$h" --screen --limit 40 2>/dev/null | grep -qF "don't ask on" && break
    sleep 3; boot=$((boot + 3))
  done
  [ "$boot" -lt 90 ] || { orca terminal close --terminal "$h" --tab >/dev/null 2>&1; echo "boot-timeout"; exit 1; }
  printf '%s' "$h" > "$rf"
  printf '%s\n' "$h"
  ;;
ask)
  key="$1"; pf="$2"
  h="$(cat "$(regfile "$key")" 2>/dev/null || true)"
  alive "$h" || { echo "no-session"; exit 1; }
  # 결과 경로를 **보내는 시점에 고정**해 프롬프트에 박는다. worker가 완료 시점에
  # 대장을 다시 읽게 하면, 그 사이 핸들이 바뀐 경우 옛 worker가 새 세션의 경로에
  # 써서 지연 결과가 이번 요청의 완료로 승인된다(R-16).
  rf="$(resfile "$key" "$h.$(date +%s).$$")"
  before=0
  body="$(sed "s|{{RESULT_PATH}}|$rf|g" "$pf")"
  # `--wait-submit`을 쓰지 않는다. 제출 관측이 그 시간 안에 안 끝나면 비정상
  # 종료를 돌려주는데 프롬프트는 이미 전달돼 있다 — 2026-09-16 PR 19108에서
  # 워커가 36초 만에 결과를 썼는데 ask는 20초에 send-failed로 빠져나갔다.
  # 전달 여부의 판단은 결과 파일 하나로 통일한다.
  orca terminal send --terminal "$h" --text "$body" --enter >/dev/null 2>&1 \
    || { echo "send-failed"; exit 1; }
  # `wait --for tui-idle`은 턴 시작 전에도 즉시 idle로 반환한다(실측). 기다릴
  # 조건은 TUI 상태가 아니라 결과 파일이다.
  limit=$((TIMEOUT / 1000)); elapsed=0; step=5
  while [ "$elapsed" -lt "$limit" ]; do
    after="$(stat -f %m "$rf" 2>/dev/null || echo 0)"
    if [ "$after" != "0" ] && [ "$after" != "$before" ]; then printf 'ok %s\n' "$rf"; exit 0; fi
    sleep "$step"; elapsed=$((elapsed + step))
  done
  # timeout된 세션은 상태를 모른다. 늦게 도착할 결과를 다음 요청이 자기 것으로
  # 오인하는 경로와, 탭만 살고 agent가 죽은 세션을 계속 재사용하는 경로를 함께
  # 닫는다(R-04·R-14). 종료에 실패하면 그 사실을 알린다.
  # timeout에도 세션과 대장을 건드리지 않는다. 다음 회차가 같은 세션에 다시
  # 요청하고, 그 요청은 새 경로를 쓴다. 계속 timeout이면 회차 보고에 미처리로
  # 반복 노출되므로 사람이 `orca terminal list`로 보고 치운다.
  echo "timeout"; exit 1
  ;;
close)
  key="$1"; rf="$(regfile "$key")"
  h="$(cat "$rf" 2>/dev/null || true)"
  # 종료를 확인하지 못해도 대장은 비운다. stale 핸들로는 더 할 수 있는 일이
  # 없고, 남겨두면 sweep도 같은 자리에서 실패해 영구히 쌓인다. 누수는 알린다.
  [ -n "$h" ] && { gone "$h" || echo "leaked-session: $h" >&2; }
  rm -f "$rf" "$ROOT"/review-result."$(slug "$key")".*.json
  echo "closed"
  ;;
sweep)
  keep=""
  for k in "$@"; do keep="$keep $(slug "$k")"; done
  for f in "$REG"/*; do
    [ -f "$f" ] || continue
    b="$(basename "$f")"
    case "$b" in *.last) rm -f "$f"; continue;; esac
    # deploy-approve-intake의 세션은 이 sweep의 것이 아니다. 두 automation의 락이
    # 별개라 resolve의 sweep이 deploy의 진행 중 ask를 죽일 수 있다(R-40). deploy는
    # 결과를 읽으면 스스로 close한다.
    case "$b" in deploy%3A*) continue;; esac
    case " $keep " in *" $b "*) continue;; esac
    h="$(cat "$f" 2>/dev/null || true)"
    [ -n "$h" ] && { gone "$h" || echo "leaked-session: $h" >&2; }
    rm -f "$f" "$ROOT"/review-result."$b".*.json
    echo "swept: $b"
  done
  ;;
*) echo "usage: pr-session.sh ensure|ask|close|sweep ..." >&2; exit 2;;
esac
