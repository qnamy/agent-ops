#!/bin/sh
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
# lock.sh acquire|check|release <automation> [token]
# 락 = state/locks/<automation>.lock/ 디렉터리, 안의 owner 파일에 획득 epoch.
# mkdir의 원자성이 승자를 하나로 정한다. 30분을 넘긴 락은 좀비로 회수한다.
set -u
STALE=1800
ROOT="${ROUTINE_STATE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)/state}"
CMD="${1:-}"; A="${2:-}"; TOK="${3:-}"
[ -n "$CMD" ] && [ -n "$A" ] || { echo "usage: lock.sh acquire|check|release <automation> [token]" >&2; exit 2; }
L="$ROOT/locks/$A.lock"
O="$L/owner"
mkdir -p "$ROOT/locks" 2>/dev/null || { echo "lock: state root not writable" >&2; exit 2; }

now=$(date +%s)

case "$CMD" in
  acquire)
    if mkdir "$L" 2>/dev/null; then
      printf '%s\n' "$now" > "$O"
      printf '%s\n' "$now"
      exit 0
    fi
    # 이미 있다 — 나이를 본다
    owned=$(cat "$O" 2>/dev/null || echo 0)
    case "$owned" in ''|*[!0-9]*) owned=0 ;; esac
    if [ "$owned" -gt 0 ] && [ $((now - owned)) -le "$STALE" ]; then
      exit 1                      # 살아 있는 소유자
    fi
    # 좀비 회수는 mv로 한다 — rm 후 mkdir는 두 단계라, stale을 함께 본 두
    # contender가 각자 삭제·생성해 둘 다 성공할 수 있다. mv는 원자적이므로
    # 성공한 하나만 회수 권한을 갖는다.
    # 회수는 락 디렉터리를 옮기지 않는다 — 옮기는 동안 경로가 비어 일반
    # 획득자가 그 틈에 새 락을 만들 수 있다. 대신 회수 권한 자체를 mkdir로
    # 원자적으로 하나에게 주고, 소유권은 owner 파일 교체로 이전한다.
    mkdir "$L.reclaim" 2>/dev/null || exit 1
    again=$(cat "$O" 2>/dev/null || echo 0)
    case "$again" in ''|*[!0-9]*) again=0 ;; esac
    if [ "$again" = "$owned" ] && { [ "$again" -eq 0 ] || [ $((now - again)) -gt "$STALE" ]; }; then
      printf '%s\n' "$now" > "$O"
      rmdir "$L.reclaim" 2>/dev/null
      printf '%s\n' "$now"
      exit 0
    fi
    rmdir "$L.reclaim" 2>/dev/null
    exit 1                        # 회수 경쟁에서 졌다
    ;;
  check)
    [ -n "$TOK" ] || exit 2
    [ "$(cat "$O" 2>/dev/null)" = "$TOK" ] || exit 1
    exit 0
    ;;
  release)
    [ -n "$TOK" ] || exit 2
    [ "$(cat "$O" 2>/dev/null)" = "$TOK" ] || exit 1
    rm -rf "$L"
    exit 0
    ;;
  *) echo "lock: unknown command $CMD" >&2; exit 2 ;;
esac
