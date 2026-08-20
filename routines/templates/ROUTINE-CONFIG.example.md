# ROUTINE-CONFIG.md (예시 스켈레톤)

> 루틴 지시서들은 회사·개인 식별값을 하드코딩하지 않고, 실행 시작 시 이 문서를 읽어 값을 주입받는다.
> 실제 파일은 비공개 워크스페이스(`{workspace}/ROUTINE-CONFIG.md`)에 두고, 여기에는 필드 구조만 공개한다.

## 계정
- 사용자: `{user_email}` · Slack user `{user_slack_id}`
- 봇(✅ 반응 전용): Slack App user_id `{qa_bot_slack_id}` · bot_id `{qa_bot_id}`
  - 봇 토큰(값 아님, 경로): `{qa_bot_token_path}` (xoxb-, chmod 600, scopes `reactions:write`·`chat:write`)
  - 봇 반응 헬퍼: `sh {qa_bot_react_helper} <CHANNEL_ID> <MSG_TS>`

## Slack
- 채널 `{review_channel_name}` = `{review_channel}` (PR 리뷰요청)
- 채널 `{qa_deploy_channel_name}` = `{qa_deploy_channel}` (배포 승인요청)
- 리뷰 대상 판정 멘션: `{dev_be_mention}` / `{dev_mention}` (`<!subteam^…>` 그룹 멘션 리터럴)
- 처리 제외: 본인(`{user_slack_id}`) 작성, 봇(`{qa_bot_slack_id}`) 작성

## Azure DevOps
- 조직: `{ado_org}` (`--org https://dev.azure.com/{ado_org}/`)
- PR URL 패턴: `https://dev.azure.com/{ado_org}/{project}/{repo}/pullrequest/{id}`

## Jira
- 사이트: `{jira-site}.atlassian.net`
- 배포 승인 목표 상태명: `{approved_status}` (상태명·전이명 비교는 항상 공백 제거 후 수행)

## 상태 파일 (routine-state)
- 상태 루트: `{workspace}/.routine-state/`
- PR 댓글 워크리스트: `pr-comment-worklist.json`
- watermark·리뷰 상태: `slack-pr-review-autopilot.state.json` (`lastRunAt` + `reviewedPrs[]`, 오버랩 스캔 10분)
- 리뷰 지적 누적 로그: `review-findings.jsonl` (quality-digest 입력)
- 배포 승인 보류 추적: `qa-deploy-pending-holds.json` (7일 만료)
- 다이제스트 후보 상태: `digest-candidates.json` (3회 노출·무응답 시 만료)

## 스케줄
- 통합 디스패처: 평일 07~20시 10분마다 (`*/10 7-20 * * 1-5`)
- completed-comment-resolver: 평일 17시 1회
- quality-digest: 매주 금 08:00
