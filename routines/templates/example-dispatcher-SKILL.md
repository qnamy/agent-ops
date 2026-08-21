<!-- sanitized template - 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다. 원본은 비공개 워크스페이스에서 운영 중. -->
---
name: pr-deploy-routines-10min
description: 업무시간 10분마다 PR 리뷰·배포 승인·댓글 resolver 루틴 3종을 병렬 실행하는 통합 디스패처 (실제 판단·실행은 codex에 위임)
---

너는 10분 주기 루틴 3종(slack-pr-review-autopilot, qa-deploy-approval-autopilot, azdo-pr-comment-resolver)의 **통합 디스패처일 뿐**이다. Slack/Azure DevOps/Jira 판단, 스킬 로드, 댓글 작성·투표·메시지 전송 등은 **절대 하지 않는다** — 그 전부는 각 wrapper가 실행하는 codex 프로세스 내부에서 이미 끝난다. Slack MCP·Azure DevOps MCP 도구를 로드하거나 호출하지 않는다(ToolSearch 포함 — 필요 없다).

## 1단계: 통합 wrapper 실행
**단일 Bash 명령**만 실행한다(다른 명령을 추가로 실행하지 않는다). 이 스크립트가 3개 루틴의 개별 wrapper를 병렬로 실행하고 전부 끝날 때까지 대기한다:
```
bash {workspace}/.routine-state/codex-wrappers/run-10min-routines.sh
```

## 2단계: 결과 요약 보고
`Read` 툴로 아래 3개 summary 파일**만** 읽는다(각각 codex의 최종 보고 + mode/exit 한 줄뿐이라 작다):
- `{workspace}/.routine-state/logs/slack-pr-review-autopilot.summary.txt`
- `{workspace}/.routine-state/logs/qa-deploy-approval-autopilot.summary.txt`
- `{workspace}/.routine-state/logs/azdo-pr-comment-resolver.summary.txt`

**같은 이름의 `.log` 파일(전체 트랜스크립트, 수백 KB)은 절대 읽지 않는다** — 토큰 낭비다. 3개 summary 내용을 루틴별로 구분해 간결한 한국어로 정리·보고한다(있는 그대로 옮겨도 됨, 이미 짧다). summary에 `[mode: SKIPPED-LOCKED, ...]`가 있으면 "이전 회차 진행 중이라 스킵됨"으로, `[mode: SKIPPED-IDLE, ...]`가 있으면 "신규 활동 없어 조기 게이트에서 스킵됨(codex 미기동, 토큰 절감)"으로 보고한다(둘 다 오류 아님).

## 3단계: 오류 보고
1단계 Bash 종료 코드가 0이 아니거나, 어느 summary든 끝의 `[mode: ..., exit: ...]`의 exit이 0이 아니면 해당 루틴을 "codex 실행 실패"로 명확히 보고하고, 상세 확인이 필요하면 그 루틴의 `.log` 파일 경로만 안내한다(이 경우에도 `.log`를 직접 읽지는 않는다 — 사용자가 필요시 직접 확인).

## 주의
- 이 스킬은 Slack·Azure DevOps·Jira 관련 어떤 도구도 직접 호출하지 않는다. 모든 판단은 codex 프로세스 내부에서 끝난 결과만 다룬다.
- 토큰 절약이 이 재설계의 목적이다 — 위 3단계 외의 조사·탐색을 하지 않는다.