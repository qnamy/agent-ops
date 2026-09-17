#!/bin/sh
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
# guarded.sh <automation> <token> run <명령...> | append <파일> <한 줄>
#
# lock check와 그 뒤의 쓰기를 한 턴으로 접는다. 프롬프트는 외부 쓰기·state 쓰기
# 직전마다 check를 요구하는데, 그것이 별도 도구 호출이면 회차마다 6~7턴이다
# (2026-09-16 실측: intake 6.0 · resolve 6.7 · deploy-intake 4.1). check가 실패하면
# 명령을 실행하지 않고 exit 3 — 프롬프트의 "소유권 상실 뒤에는 아무것도 시도하지
# 않는다"와 같다.
set -u
D="$(cd "$(dirname "$0")" && pwd)"
A="${1:?usage: guarded.sh <automation> <token> run <cmd...> | append <file> <line>}"
TOK="${2:?token}"; verb="${3:?run|append}"; shift 3
sh "$D/lock.sh" check "$A" "$TOK" || { echo "guarded: lock lost for $A" >&2; exit 3; }
case "$verb" in
  run)    exec "$@" ;;
  append) f="${1:?file}"; line="${2:?line}"; printf '%s\n' "$line" >> "$f" ;;
  *) echo "guarded: unknown verb $verb" >&2; exit 2 ;;
esac
