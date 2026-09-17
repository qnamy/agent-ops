#!/bin/sh
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
# automation의 --precheck 진입점.
# precheck.py의 종료 코드 10만 SKIP(exit 1)으로 넘기고 나머지 전부를 0(RUN)으로 바꾼다.
# 이유: precheck.py의 구문 오류·import 실패·interpreter 부재·signal 종료는
# 파이썬 내부 catch-all에 들어오지 않는다. orca는 0이 아닌 코드를 SKIP으로
# 기록하므로, 그대로 두면 그 automation이 배포 시점부터 영구히 안 돈다.
# (현행 run-10min-routines.sh:18-27이 같은 변환을 한다)
D="$(cd "$(dirname "$0")" && pwd)"
python3 "$D/precheck.py" "$@"
rc=$?
# 10만 SKIP이다. 1을 SKIP으로 두면 파이썬 자신의 실패(구문 오류·import
# 실패·인터프리터 부재는 전부 1이다)가 SKIP으로 넘어가 automation이 영구히
# 안 돈다 — 2026-09-10 실측으로 확인했다.
[ "$rc" = 10 ] && exit 1
exit 0
