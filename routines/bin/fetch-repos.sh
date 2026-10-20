#!/bin/sh
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
# fetch-repos.sh <repo>|<repo>#<prId>#<정본URL> ...
# 샌드박스 밖(precheck)에서만 돈다 — 세션은 사내 레포에 쓸 수 없다.
# state/fetch-queue에 쌓인 대상도 함께 fetch하고 파일을 비운다.
#
# PR의 sourceRefName은 refs/heads/*인 경우와 refs/pull/<id>/source인 경우가
# 모두 있다. 후자는 origin의 기본 refspec(+refs/heads/*)으로 오지 않아 그 커밋이
# 로컬에 없고, 세션은 fetch가 금지돼 있어 회차 전체가 미처리로 끝난다. 그래서
# id를 아는 대상은 pull ref를 함께 가져온다. id가 없는 대상은 브랜치만 가져온다.
# 완료된 PR의 pull ref는 ADO가 지우므로 pr-ref-missing이 정상 결과다.
#
# pull ref는 origin이 아니라 PR의 정본 URL에서 가져온다. 로컬 클론이 개인
# fork를 가리키는 경우가 있고(2026-09-14 실측: <레포 A>의 origin이
# 개인 계정 fork였다) 그 fork에는 정본 레포의 PR ref가 없다.
set -u
ROOT="${ROUTINE_STATE_ROOT:-$(cd "$(dirname "$0")/.." && pwd)/state}"
BASE="$HOME/work"
Q="$ROOT/fetch-queue"

targets="$*"
if [ -s "$Q" ]; then
  targets="$targets $(tr '\n' ' ' < "$Q")"
  : > "$Q"
fi

for t in $targets; do
  [ -n "$t" ] || continue
  r="${t%%#*}"
  rest="${t#*#}"
  if [ "$rest" = "$t" ]; then id=""; url=""; else id="${rest%%#*}"; url="${rest#*#}"; fi
  # 레포 이름의 공백은 %20으로 와 있다(단어 분리 방지). 로컬 경로용으로 되돌린다.
  r=$(printf '%s' "$r" | sed 's/%20/ /g')
  if [ ! -d "$BASE/$r/.git" ]; then
    if [ -z "$url" ]; then
      echo "missing: $r"
      continue
    fi
    # 로컬 clone이 없으면 pull ref를 가져올 곳 자체가 없어 그 repo의 PR이 매
    # 회차 commit-missing으로 미처리된다 — 2026-09-22 실측: azp-agent·
    # <레포 G> 부재로 11개 PR이 intake 게이트 commit을 영구 차단했다.
    # 정본 URL로만 clone한다 — clone의 origin이 정본이어야 위
    # <레포 A> 같은 개인 fork 가리킴 사고가 재발하지 않는다.
    # 반만 받은 clone을
    # $BASE/$r에 두지 않도록 같은 파일시스템의 임시 디렉터리에 받아 rename한다.
    # clone 직후라 origin fetch는 건너뛰고 아래 pull ref fetch로 간다.
    if tmp=$(mktemp -d "$BASE/.fetch-clone.XXXXXX") &&
       git clone --quiet "$url" "$tmp" 2>/dev/null &&
       [ ! -e "$BASE/$r" ] && mv "$tmp" "$BASE/$r"; then
      echo "cloned: $r"
    else
      rm -rf "$tmp"
      echo "missing: $r"
      continue
    fi
  elif git -C "$BASE/$r" fetch --quiet origin 2>/dev/null; then
    echo "fetched: $r"
  else
    # origin이 실패해도 멈추지 않는다. PR 커밋을 실제로 공급하는 것은 아래
    # 정본 URL fetch이고, 그것은 origin과 다른 인증 경로다 — 2026-09-18에
    # origin URL이 쓰는 크리덴셜만 사라졌을 때 이 continue가 성공했을 정본
    # fetch까지 막아 `#{PR}`이 iteration 2로 리뷰됐다.
    echo "fetch-failed: $r"
  fi
  [ -n "$id" ] && [ -n "$url" ] || continue
  if git -C "$BASE/$r" fetch --quiet "$url" \
      "+refs/pull/$id/source:refs/remotes/origin/pull/$id/source" 2>/dev/null; then
    echo "fetched-pr: $r#$id"
    continue
  fi
  # refs/pull/<id>/source가 없는 PR이 있다 — 2026-09-16 실측: <프로젝트 A>의
  # <레포 D>#19097은 /merge만 있고 source는 일반 브랜치
  # refs/heads/feature/{TICKET}-drop-bl-no다. origin이 개인 fork를 가리키면
  # 그 브랜치도 오지 않아 커밋이 로컬에 없다. 정본에서 브랜치 전부를 별도
  # 네임스페이스로 가져와 어느 쪽이든 커밋이 있게 한다.
  if git -C "$BASE/$r" fetch --quiet "$url" \
      "+refs/heads/*:refs/remotes/canonical/*" 2>/dev/null; then
    echo "fetched-canonical: $r#$id"
  else
    echo "pr-ref-missing: $r#$id"
  fi
done
