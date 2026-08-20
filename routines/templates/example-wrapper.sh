#!/bin/bash
# sanitized template - 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다.
# codex 이관본 실행 래퍼 (Claude 트리거 + GPT 실행 아키텍처용).
# 기본은 dry-run(안전)이며, 아래 마커 파일이 있을 때만 라이브로 실행된다.
#   라이브 전환: touch "$HOME/{org}/.routine-state/codex-live/slack-pr-review-autopilot.enabled"
#   다시 dry-run으로: 그 파일을 삭제
# 전체 트랜스크립트는 .log(디버깅용, Claude가 읽지 않음)에, codex의 최종 보고만 .summary.txt(Claude 디스패처가 읽는 파일)에 남긴다.
set -uo pipefail

ROUTINE_NAME="slack-pr-review-autopilot"
INSTR_FILE="$HOME/{org}/routines-codex/${ROUTINE_NAME}.md"
LIVE_MARKER="$HOME/{org}/.routine-state/codex-live/${ROUTINE_NAME}.enabled"
LOG_DIR="$HOME/{org}/.routine-state/logs"
RUN_TS="$(date '+%Y%m%d-%H%M%S')"
LOG_FILE="${LOG_DIR}/${ROUTINE_NAME}.${RUN_TS}.log"
SUMMARY_FILE="${LOG_DIR}/${ROUTINE_NAME}.summary.txt"
MODEL="gpt-5.6-sol"

export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:$HOME/.local/bin"

# az CLI 캐시/설정 경로 고정: codex 샌드박스(workspace-write)가 ~/.azure 쓰기를 막아
# 매 회차 PermissionError(az.sess) → ~/.azure 전체(토큰 포함)를 /tmp로 복사해 우회하던 패턴 제거.
# 최초 1회만 ~/.azure에서 시드하고 이후엔 az가 이 경로에서 토큰을 자체 갱신한다.
# 인증이 깨지면(예: 계정 재로그인) 이 디렉터리를 삭제하면 다음 회차에 재시드된다.
export AZURE_CONFIG_DIR="$HOME/{org}/.routine-state/azure-config/${ROUTINE_NAME}"
export AZURE_EXTENSION_DIR="$HOME/.azure/cliextensions"  # 확장(azure-devops)은 원본을 읽기 전용 공유(회차별 재설치 방지)
export AZURE_DEVOPS_CACHE_DIR="${AZURE_CONFIG_DIR}/devops-cache"
mkdir -p "$AZURE_DEVOPS_CACHE_DIR"  # 병렬 az 호출이 생성 경쟁([Errno 17] File exists)하지 않도록 선생성
if [ ! -f "$AZURE_CONFIG_DIR/azureProfile.json" ]; then
  mkdir -p "$AZURE_CONFIG_DIR"
  chmod 700 "$HOME/{org}/.routine-state/azure-config" "$AZURE_CONFIG_DIR"
  cp -R "$HOME/.azure/." "$AZURE_CONFIG_DIR"
  rm -rf "$AZURE_CONFIG_DIR/cliextensions" "$AZURE_CONFIG_DIR/logs" "$AZURE_CONFIG_DIR/telemetry" "$AZURE_CONFIG_DIR/commands"
fi

# 중복 실행 방지 락: 이전 회차가 아직 진행 중이면 이번 회차는 스킵한다.
# (macOS엔 flock이 없어 mkdir 원자성 + PID 생존 확인 방식. 프로세스가 비정상 종료해 락이 남으면 다음 회차가 회수한다.)
LOCK_DIR="$HOME/{org}/.routine-state/locks/${ROUTINE_NAME}.lock"
mkdir -p "$HOME/{org}/.routine-state/locks"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  LOCK_PID="$(cat "$LOCK_DIR/pid" 2>/dev/null)"
  if [ -n "$LOCK_PID" ] && kill -0 "$LOCK_PID" 2>/dev/null; then
    {
      echo "이전 실행(pid ${LOCK_PID})이 아직 진행 중이어서 이번 회차를 스킵했습니다."
      echo ""
      echo "[mode: SKIPPED-LOCKED, exit: 0]"
    } > "$SUMMARY_FILE"
    exit 0
  fi
  # stale 락 회수 (락 보유 프로세스가 이미 죽음)
  rm -rf "$LOCK_DIR"
  if ! mkdir "$LOCK_DIR" 2>/dev/null; then
    {
      echo "락 회수 경합으로 이번 회차를 스킵했습니다."
      echo ""
      echo "[mode: SKIPPED-LOCKED, exit: 0]"
    } > "$SUMMARY_FILE"
    exit 0
  fi
fi
echo $$ > "$LOCK_DIR/pid"
trap 'rm -rf "$LOCK_DIR"' EXIT

if [ -f "$LIVE_MARKER" ]; then
  unset ROUTINE_DRY_RUN
  MODE_LABEL="LIVE"
else
  export ROUTINE_DRY_RUN=1
  MODE_LABEL="DRY-RUN"
fi

rm -f "$SUMMARY_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] ${MODE_LABEL} 모드로 실행 (model=${MODEL})" > "$LOG_FILE"
codex exec -m "$MODEL" -s workspace-write --skip-git-repo-check -C "$HOME/{org}" -o "$SUMMARY_FILE" - < "$INSTR_FILE" >> "$LOG_FILE" 2>&1
CODEX_EXIT=$?
echo "[$(date '+%Y-%m-%d %H:%M:%S')] 종료 코드: ${CODEX_EXIT}" >> "$LOG_FILE"

if [ ! -s "$SUMMARY_FILE" ]; then
  echo "(codex가 최종 메시지를 남기지 않았습니다 — 종료 코드 ${CODEX_EXIT}. 전체 로그: ${LOG_FILE})" > "$SUMMARY_FILE"
fi
{
  echo ""
  echo "[mode: ${MODE_LABEL}, exit: ${CODEX_EXIT}]"
} >> "$SUMMARY_FILE"

# 회차별 로그는 최근 10개만 보존(오래된 것 정리). summary.txt 계약(경로·형식)은 그대로.
ls -t "${LOG_DIR}/${ROUTINE_NAME}."*.log 2>/dev/null | tail -n +11 | xargs rm -f

exit "$CODEX_EXIT"
