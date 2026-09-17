# ROUTINE-CONFIG.md (예시 스켈레톤)

> 루틴 지시서는 회사·개인 식별값을 하드코딩하지 않고 이 문서에서 주입받는다. 실제 파일은 비공개로 `~/work/ROUTINE-CONFIG.md`에 두고, 여기에는 필드 구조만 공개한다.
>
> **줄 모양을 바꾸지 않는다.** `bin/precheck.py`가 회차 전에 이 파일을 파싱해 해석값을 맥락 파일에 싣는다(`config_ado_org`·`config_channel`·`config_user`·`config_slack_user`·`config_bot_user`·`config_mentions`·`config_pr_url_pattern`·`config_disclaimer`). 파싱에 실패하면 그 항목이 빠지고 세션이 이 원문을 직접 읽는 폴백으로 내려간다.
>
> ⚠️ **크리덴셜 값은 여기 두지 않는다** — 경로만 참조하고 값은 `state/`(600)에 둔다.

## 신원
- 사용자: `me@example.com` · Slack user `U000USER000`
- 봇(✅ 반응 전용): Slack App · Slack user `U000BOT0000` · bot_id `B000BOT0000`
  - 봇 토큰(값 아님, 경로): `~/work/orca-automations/state/.deploy-approval-bot-token` (xoxb-, chmod 600, scopes `reactions:write`·`chat:write`)
  - 봇 반응 헬퍼: `sh ~/work/orca-automations/state/deploy-approval-react.sh <CHANNEL_ID> <MSG_TS>`

## Slack
- 채널 `#pr-review-requests` = `C000REVIEW0` (PR 리뷰요청)
- 채널 `#deploy-approval` = `C000DEPLOY0` (배포 승인요청)
- 대상 유저그룹 멘션(하나 이상 포함해야 처리): `@dev_be`=`<!subteam^S000BE00000>` · `@dev`=`<!subteam^S000DEV0000>`
- 처리 제외 예: FE 그룹 `@dev_fe`=`<!subteam^S000FE00000>`, 본인(`U000USER000`) 작성, 봇(`U000BOT0000`) 작성

## Azure DevOps
- 조직: `ExampleOrg`
- PR URL 패턴: `https://dev.azure.com/ExampleOrg/{project}/_git/{repo}/pullrequest/{PR_ID}`
- 로컬 레포 경로 규칙: `~/work/{repo}`

## Jira
- cloudId: `example.atlassian.net`
- 티켓 링크: `https://example.atlassian.net/browse/{KEY}` (KEY = 대문자프로젝트-숫자)
- 배포 승인 목표 상태명: `배포승인` (상태명·전이명 비교는 항상 **공백 제거 후** 수행)

## 문구·마커
- PR 댓글 면책 문구(모든 리뷰/대댓글 마지막 2줄):
  ```
  ⚠️ AI를 활용한 댓글 작성 테스트 중입니다. 댓글이 이상한 경우 신고해주세요.
  by Claude Code
  ```
- 배포 승인 루틴 답글 멱등 마커(보류 사유·미해소 사유·해소 확인 답글 마지막 줄): `_by deploy-approval-autopilot 🤖_`

## 타이밍
- 폴링 스케줄(업무시간): 평일 07~20시 10분마다 (`*/10 7-20 * * 1-5`)
- 시간 윈도우(경계 누락 방지): PR 리뷰 최근 **20분**, 배포 승인 최근 **25분**
