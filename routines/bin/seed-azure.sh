#!/bin/sh
# sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
# az 인증 상태를 automation별 디렉터리로 시드한다. 이행 작업이고 사람이 돌린다.
# `az login`을 다시 하면 $HOME/.azure가 갱신되므로 이 스크립트를 다시 돌려야 한다.
# 갱신되는 것(profile, 토큰 cache)만 복사한다 — extension은 az가 기본 경로에서 읽는다.
set -eu
R="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$HOME/.azure"
[ -f "$SRC/azureProfile.json" ] || { echo "seed: $SRC/azureProfile.json 이 없다. az login 먼저." >&2; exit 1; }
# 확장은 automation 전체가 공유한다 — 읽기만 하므로 사본 하나로 충분하다.
EXT="$R/state/azure-ext"
[ -d "$SRC/cliextensions/azure-devops" ] || { echo "seed: azure-devops 확장이 $SRC/cliextensions 에 없다. az extension add --name azure-devops 먼저." >&2; exit 1; }
# 마커는 복사가 끝난 뒤에만 쓴다 — 끊긴 사본을 완료로 오인하지 않는다.
# 확장을 갱신했으면 `rm -rf state/azure-ext` 후 다시 돌린다.
if [ ! -f "$EXT/.seeded" ]; then
  rm -rf "$EXT.new"; mkdir -p "$EXT.new"
  cp -R "$SRC/cliextensions/." "$EXT.new/"
  : > "$EXT.new/.seeded"
  rm -rf "$EXT"; mv "$EXT.new" "$EXT"
  echo "seeded: azure-ext (공유)"
fi

for a in pr-review-intake pr-review-resolve pr-review-merged deploy-approve-intake deploy-approve-resolve; do
  D="$R/state/azure/$a"
  mkdir -p "$D"
  cp "$SRC/azureProfile.json" "$D/"
  cp "$SRC/msal_token_cache".* "$D/" 2>/dev/null || true
  chmod 700 "$D"
  # 파일만 600으로 — 디렉터리에 걸면 az가 자기 로그·cache를 쓸 수 없다.
  find "$D" -maxdepth 1 -type f -exec chmod 600 {} + 2>/dev/null || true
  echo "seeded: $a"
done
