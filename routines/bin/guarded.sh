#!/bin/sh
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
# guarded.sh <automation> <token> run <명령...> | append <파일> <한 줄> | write <파일>
#
# lock check와 그 뒤의 쓰기를 한 턴으로 접는다. 프롬프트는 외부 쓰기·state 쓰기
# 직전마다 check를 요구하는데, 그것이 별도 도구 호출이면 회차마다 6~7턴이다
# (2026-09-16 실측: intake 6.0 · resolve 6.7 · deploy-intake 4.1). check가 실패하면
# 명령을 실행하지 않고 exit 3 — 프롬프트의 "소유권 상실 뒤에는 아무것도 시도하지
# 않는다"와 같다.
#
# write는 표준입력을 같은 디렉터리의 임시 파일에 모두 받은 뒤에만 mv로 교체한다
# — 저장이 끝나지 않은 파일이 본문 자리에 들어가 `az invoke`로 나가는 것을 막는다.
# 덮어쓰기 전용이라 부분 수정에는 쓸 수 없다.
set -u
D="$(cd "$(dirname "$0")" && pwd)"
A="${1:?usage: guarded.sh <automation> <token> run <cmd...> | append <file> <line> | write <file>}"
TOK="${2:?token}"; verb="${3:?run|append|write}"; shift 3
sh "$D/lock.sh" check "$A" "$TOK" || { echo "guarded: lock lost for $A" >&2; exit 3; }
case "$verb" in
  run)    exec "$@" ;;
  write)
    f="${1:?file}"
    tmp="$(mktemp "${f}.guarded.XXXXXX")" || exit 4
    if ! cat > "$tmp"; then
      rm -f "$tmp"
      echo "guarded: write failed for $f" >&2
      exit 4
    fi
    mv "$tmp" "$f" || { rm -f "$tmp"; echo "guarded: replace failed for $f" >&2; exit 4; }
    ;;
  append)
    f="${1:?file}"; line="${2:?line}"
    case "$f" in
      *.jsonl)
        if ! python3 -c 'import json,sys; line=sys.argv[1]; json.loads(line); sys.exit(0 if "\n" not in line and "\r" not in line else 1)' "$line" 2>/dev/null; then
          echo "guarded: .jsonl append requires single-line JSON" >&2
          exit 4
        fi
        ;;
    esac
    printf '%s\n' "$line" >> "$f"
    ;;
  *) echo "guarded: unknown verb $verb" >&2; exit 2 ;;
esac
