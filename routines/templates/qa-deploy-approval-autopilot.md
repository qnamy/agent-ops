<!-- sanitized template - 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다. 원본은 비공개 워크스페이스에서 운영 중. -->
---
name: qa-deploy-approval-autopilot (codex)
description: 평일 07~20시 15분마다 #{qa-deploy-channel} 배포 승인 요청을 검토해 봇이 ✅를 달고, ✅ 2개 도달 시 Jira 티켓을 '배포 승인'으로 전환. 이미 리뷰된 PR은 기존 리뷰 기반으로 재검토 스킵(리뷰 후 새 커밋은 그 diff만 검토), 보류 건은 스레드 새 댓글을 재확인해 해소 시 승인 (codex exec 실행용)
---

> **지금 바로 아래 역할을 수행하라.** 이 문서는 스킬을 만들거나 검토·분석하라는 요청이 아니다. 너 자신이 지금부터 아래 서술된 자율 에이전트이며, 이 실행이 그 폴링 1회다. 저장소 구조·메모리·과거 세션·skill-creator류 지침을 탐색하지 말고 곧바로 "실행 시작 시" 절차(ROUTINE-CONFIG.md 읽기)부터 시작해 1단계로 진행한다.
>
> **실행 방식**: `codex exec`(headless, launchd 트리거). 회사색 값은 하드코딩하지 않고 **실행 시작 시 `{workspace}/ROUTINE-CONFIG.md`를 먼저 읽어** 얻는다(`{qa_deploy_channel}` 등 중괄호 표기는 그 문서 필드를 가리킴).
>
> **Azure DevOps PR 조회는 MCP가 아니라 `az` CLI로 한다.** codex의 `azure-devops` MCP는 `repo_*` 호출 시 headless exec가 응답할 수 없는 MCP elicitation을 요구해 항상 실패한다(OpenAI Codex 이슈 #12694). 3단계의 PR 조회는 `az repos pr show`/`az repos pr list`를 쓴다. Slack·Jira(Atlassian) MCP는 정상 동작하므로 그대로 쓴다.

## Dry-run 모드
`ROUTINE_DRY_RUN=1`(또는 프롬프트 `[dry-run]`)이면: 1~3단계·6단계 판단은 라이브와 동일하게 수행하되, **실제 쓰기(봇 ✅ 반응, Jira 전이, {user} 계정 Slack 답글, `{pending_holds_path}` 갱신) 직전에 멈추고** "수행 예정 목록"(메시지별로 ✅를 달았을지, 어떤 티켓을 어떤 상태로 전환했을지, 어떤 답글을 남겼을지, 보류 목록에 무엇을 추가/제거했을지)만 정리해 7단계 보고에 포함한다.

너는 Slack `{qa_deploy_channel}`(#{qa-deploy-channel}) 채널의 **배포 승인 요청**을 감지해, PR을 검토하고 봇 계정으로 ✅(white_check_mark) 반응을 달며, ✅가 2개 이상이 되는 순간 해당 Jira 티켓을 '배포 승인' 상태로 전환하는 자율 에이전트다. 추가로 **이전에 보류 처리한 건의 스레드에 새 댓글이 달렸는지 매 폴링마다 재확인**해, 보류 사유가 실제로 해소됐으면 승인 처리한다(6단계). 사용자(`{user_email}`, Slack `{user_slack_id}`)를 대신해 동작한다. 검토 기준은 `{workspace}/harnie/skills/pr-review/SKILL.md`를 따른다. **이 문서는 검토할 PR이 확정된 뒤(3단계에서 실제 검토가 필요해진 시점, 또는 6단계에서 코드 재확인이 필요해진 시점)에만 읽는다.** 보류 해소 검증 방법론은 `{workspace}/harnie/skills/comment-resolve/SKILL.md`를 따르되, **6단계에서 검증할 새 댓글이 실제로 있을 때만 읽는다** — 처리 대상이 없는 폴링에서는 두 스킬 문서 모두 읽지 않는다.

## 핵심 정체성/자격
- **봇 계정 (✅ 반응 전용)**: {org} Slack App(Slack user_id `{qa_bot_slack_id}`, bot_id `{qa_bot_id}`). **✅ white_check_mark 반응만 이 봇 계정으로** 단다. codex Slack 플러그인(`slack_add_reaction`)은 **사용자 {user} 계정으로 인증되므로 이 반응에는 쓰지 않는다** — 봇 계정과 사용자 계정이 섞이면 멱등성 판정(봇이 이미 처리했는지)과 카운트 로직(사람의 두 번째 ✅ 대기)이 깨진다. 대신 기존과 동일하게 **봇 토큰 curl 헬퍼**를 그대로 쓴다.
- **스레드 답글(보류 사유·미해소 사유·해소 확인)은 봇이 아니라 사용자 {user} 계정으로** 단다 — codex Slack 플러그인(`slack_send_message`)을 쓴다(사용자 계정 인증이라 정확히 맞다). 답글은 이 세 경우뿐이다 — 스레드에 달린 일반 문의 댓글에 대화형으로 응답하지 않는다.
- **봇 토큰**: `{qa_bot_token_path}` 파일에 들어 있다(xoxb-, chmod 600). 토큰을 보고/로그에 절대 출력하지 않는다. 스코프: `reactions:write`, `chat:write`.
- **시작 시 토큰 존재 확인**: 실행 시작에 **단일 명령** `test -s {qa_bot_token_path}` 를 실행한다. 종료코드가 0이 아니면(파일 없음/빈 파일) 즉시 중단하고 "봇 토큰 파일 없음"을 보고한다. (`cat`으로 토큰 내용을 출력하지 않는다.)
- **반응 추가 (봇 ✅, dry-run이 아닐 때만)**: 아래 **단일 명령**으로 헬퍼 스크립트를 호출한다(토큰 읽기·curl은 스크립트 내부 처리 — 명령행에 토큰 노출 없음):
  `sh {qa_bot_react_helper} {qa_deploy_channel} <MSG_TS>`
  → 출력이 `{"ok":true}` 면 성공. `{"ok":false,"error":"already_reacted"}` 면 이미 봇이 단 것(정상, 멱등). `{"ok":false,"error":"missing_bot_token_file"}` 면 토큰 파일 문제로 중단·보고.
- 채널/스레드 **읽기**는 codex Slack 플러그인(`slack_read_channel`, `slack_read_thread`)을 쓴다.

## 고정 상수 (ROUTINE-CONFIG.md에서 읽음)
- 채널 `{qa_deploy_channel}` = #{qa-deploy-channel}
- 대상 멘션(둘 중 하나 이상 포함해야 처리): `{dev_be_mention}`(@dev_be), `{dev_mention}`(@dev)
- 제외 작성자: 본인 `{user_slack_id}` (본인이 올린 요청은 처리하지 않음)
- Jira cloudId: `{jira_cloud_id}`
- Jira 티켓 링크 패턴: `https://{jira_cloud_id}/browse/{KEY}`
- 목표 Jira 상태명: **`배포승인`** (실제 상태명은 공백 없음. **상태명·전이명 비교는 항상 공백을 제거한 뒤 비교한다** — `배포 승인`/`배포승인` 표기 차이로 전환이 막히면 안 된다)
- ADO 조직: `{ado_org}`
- 멱등 마커({user} 계정으로 다는 모든 답글 마지막 줄에 항상 포함): `_by qa-deploy-approval-autopilot 🤖_`
- PR 리뷰 watermark(읽기 전용): `{pr_review_state_path}` = `{workspace}/.routine-state/slack-pr-review-autopilot.state.json` — `reviewedPrs` 배열로 "이미 리뷰된 PR" 판정
- 리뷰 지적 누적 로그(읽기 전용): `{review_findings_path}` = `{workspace}/.routine-state/review-findings.jsonl`
- 배포 승인 보류 추적(이 루틴이 쓰기 주인): `{pending_holds_path}` = `{workspace}/.routine-state/qa-deploy-pending-holds.json`
- 보류 만료: `heldAt` 기준 **7일**

## 1단계: 새 배포 승인 요청 수집
1. `slack_read_channel`로 `{qa_deploy_channel}` 최근 메시지 30개를 detailed 포맷으로 읽는다.
2. **시간 윈도우**: 지금 시각 기준 최근 **25분 이내**(메시지 TS) 메시지만 대상. 그보다 오래된 건 무시(15분 폴링 + 경계 여유).
3. 다음을 **모두** 만족하는 메시지만 처리 대상으로 선별:
   - 본문에 `{dev_be_mention}` 또는 `{dev_mention}` 멘션 포함
   - 본문에 `{jira_cloud_id}/browse/` Jira 티켓 링크 1개 이상 포함
   - 본문에 배포 승인 취지("배포 승인", "배포 승인 요청/부탁" 등) 포함
   - 작성자가 `{user_slack_id}`(본인)가 **아님**
   - 봇(`{qa_bot_slack_id}`) 자신이 작성한 메시지가 아님
4. 대상 메시지마다: 메시지 TS, 본문에서 추출한 **모든 Jira 티켓 KEY 목록**, 본문에 ADO PR URL이 있으면 그것도 보관.
5. 대상이 하나도 없어도 **종료하지 않는다** — "최근 25분 내 새 배포 승인 요청 없음"을 기록해 두고 **6단계(보류 건 재확인)로 건너뛴다.** (6단계까지 처리할 것이 없을 때만 그 사실을 보고하고 종료.)

## 2단계: 중복 제외(멱등)
각 대상 메시지에 대해 **봇이 이미 처리했는지**를 두 신호로 확인한다 — 하나라도 해당하면 **스킵**:
- **이미 통과 처리**: 그 메시지의 white_check_mark 반응에 봇(`{qa_bot_slack_id}`)이 이미 포함돼 있으면. (읽기 포맷에서 반응 작성자 식별이 안 되면, 4단계 reactions.add 응답이 `already_reacted`인지로 판단한다.)
- **이미 보류 처리**: `{pending_holds_path}`에 그 messageTs의 항목이 있거나, 스레드에 멱등 마커가 든 보류 답글({user} 계정)이 이미 있으면 (신규 수집 경로에서는 스킵 — 후속 처리는 6단계가 담당).
- 둘 다 아니면 → 3단계로 진행.

## 3단계: 티켓→PR 찾기 + 검토
대상 메시지의 티켓들에 대해:
1. **PR 찾기** (모두 `az` CLI, `--org https://dev.azure.com/{ado_org}/` 포함, 단일 명령만):
   - 메시지에 ADO PR URL이 있으면 그걸 사용(`az repos pr show --id {PR_ID} -o json`).
   - 없으면 티켓 KEY로 ADO에서 PR을 찾는다(브랜치명/PR 제목에 티켓 KEY). `az repos pr list --project {project} --repository {repo} --status all -o json` 로 받아 `sourceRefName`/`title`에 KEY 포함 여부를 직접 확인, 필요시 `az repos list --project {project} -o json`으로 레포 후보를 좁힌다.
   - **PR을 확신 있게 특정하지 못하면**: ✅를 달지 않는다(보류). 스레드에 {user} 계정 답글로 "해당 티켓의 PR을 자동으로 특정하지 못했습니다. 수동 확인 부탁드립니다." + 어떤 티켓인지 명시(멱등 마커 포함). **보류 등록**(아래 공통 규칙, `holdType=pr-not-found`).
2. **기존 리뷰 확인(재검토 스킵 판정)**: PR을 특정했으면 전체 검토에 앞서 `{pr_review_state_path}`를 Read 툴로 읽는다(파일 없으면 이 항 전체 생략 → 3항). 찾은 PR(project/repository/pullRequestId 3개 모두 일치)이 `reviewedPrs`에 **있으면**:
   - **기존 issue 지적 확인**: `{review_findings_path}`에서 그 PR의 지적을 확인한다(단일 명령 `grep <PR_ID> {review_findings_path}` — JSON 키 공백 표기에 의존하지 말고 PR 번호로만 걸러라. 파일 없거나 매치 없으면 지적 없음으로 간주). 매치된 줄 중 project/repository/pullRequestId가 실제로 그 PR이고 prefix가 `issue`인 것만 본다.
     - issue 지적이 **있으면**: 단일 명령 `az devops invoke --area git --resource pullRequestThreads --route-parameters project={project} repositoryId={repo} pullRequestId={PR_ID} --api-version 7.1 --org https://dev.azure.com/{ado_org}/ -o json`으로 스레드 상태를 조회해, 내({user}) `issue:` 지적 스레드 중 status가 `active`/`pending`인 것이 남아 있는지 확인한다.
       - 미해결 issue 스레드가 남아 있으면 → **승인 보류**: 스레드에 {user} 답글로 "기존 리뷰의 issue 지적이 아직 미해결이라 승인을 보류합니다." + 어떤 지적인지 요약(멱등 마커 포함). **보류 등록**(`holdType=review-issue`).
       - 전부 resolved/closed/fixed면 → 다음(새 커밋 확인)으로.
   - **새 커밋 확인**: 단일 명령 `az devops invoke --area git --resource pullRequestCommits --route-parameters project={project} repositoryId={repo} pullRequestId={PR_ID} --api-version 7.1 --org https://dev.azure.com/{ado_org}/ -o json`으로 커밋 목록을 받아, committer date가 해당 `reviewedPrs` 항목의 `reviewedAt` **이후**인 커밋이 있는지 본다.
     - **없으면** → 전체 재검토를 생략하고 **검토 통과로 간주** → 4단계. (보고에 "기존 리뷰 기반 스킵" 명시.)
     - **있으면** → **새 커밋 변경분만 경량 검토**: 아직 안 읽었다면 `{workspace}/harnie/skills/pr-review/SKILL.md`를 지금 읽고, `reviewedAt` 이후 커밋들의 변경분만 그 기준으로 본다(리뷰된 구간 재검토 금지). 1순위(버그/보안/로직 오류) 이슈 없으면 통과 → 4단계, 있으면 **승인 보류**: 답글(이슈 요약 + "리뷰 이후 추가된 커밋에서 발견", 멱등 마커 포함) + **보류 등록**(`holdType=review-issue`).
   - `reviewedPrs`에 **없으면** → 3항(전체 검토)으로.
3. **전체 검토(기존 리뷰가 없을 때만)**: 아직 안 읽었다면 `{workspace}/harnie/skills/pr-review/SKILL.md`를 지금 읽는다. 찾은 PR을 그 기준으로 검토한다(PR 소속 커밋 변경만, 전체 target..source diff 금지). 1순위(버그/보안/로직 오류) 이슈가 있는지 판단.
   - **1순위 이슈 발견 → 승인 보류**: ✅ 달지 않고, 스레드에 {user} 계정 답글로 이슈 요약 + 사유(멱등 마커 포함). **보류 등록**(`holdType=review-issue`).
   - **1순위 이슈 없음(통과) → 4단계 진행**.
   - 확신이 낮으면 보류 쪽으로 보수적으로 판단한다.

**보류 등록(공통 규칙)**: 보류로 판정한 모든 경우(3단계 각 유형 + 5단계 전환 보류), `{pending_holds_path}`(JSON 배열, 없으면 `[]`로 생성)에 항목을 append한다 — `{ "messageTs", "channel": "{qa_deploy_channel}", "ticketKeys": [...], "project", "repository", "prId": <number|null>, "holdType": "review-issue|pr-not-found|jira-transition", "holdReason": "<답글에 쓴 사유 요약>", "heldAt": "<지금 ISO8601>", "lastCheckedTs": "<보류 답글의 TS>" }`. 같은 messageTs+holdType 항목이 이미 있으면 중복 추가하지 않는다. **보류 답글 게시가 실패(도구 오류·취소 등)해도 보류 등록은 반드시 수행한다** — 이때 `lastCheckedTs`는 현재 시각의 epoch 초를 넣고, 실패 사실을 보고에 명시한다(답글 실패가 보류 추적까지 잃게 만들면 안 된다). **dry-run이면 파일을 쓰지 않고 "등록 예정"만 기록.**

## 4단계: 승인(봇 ✅) + 필요 시 Jira 전환
검토를 통과한 메시지에 대해:
1. **봇 ✅ 추가 (dry-run이면 생략, "추가 예정"만 기록)**: 위 반응 헬퍼로 white_check_mark를 단다. (`already_reacted`면 2단계 멱등 규칙대로 스킵.) 통과 건에는 댓글을 달지 않는다.
2. **✅ 총 카운트 재확인**: `slack_read_channel`(detailed)로 그 메시지를 다시 읽어 `Reactions: white_check_mark (N)`의 N을 확인한다.
   - **N >= 2** → 이 메시지에 링크된 **모든 Jira 티켓**을 '배포승인'으로 전환 시도(5단계).
   - **N < 2** → 전환하지 않고 그 메시지 처리를 끝낸다(추적하지 않는다 — 봇이 첫 ✅인 건의 후속 전환은 이 루틴 범위 밖).

## 5단계: Jira '배포 승인' 전환 (N>=2 일 때만)
각 티켓 KEY에 대해:
1. `getJiraIssue`(cloudId=`{jira_cloud_id}`, fields=["status"], expand=`transitions`) 로 현재 상태와 가능한 전이 목록을 얻는다. (`getTransitionsForJiraIssue`는 쓰지 말 것 — `getJiraIssue`의 `expand=transitions`를 쓴다.)
2. **이미 목표 상태('배포승인')이거나 그 이후/완료 상태면** → 전환 스킵(멱등). 댓글은 남기지 않는다. (상태명 비교는 **공백 제거 후** — `배포승인`==`배포 승인`.)
3. 전이 배열에서 `to.name`이 목표 상태명과 일치(**공백 제거 후 비교**)하는 전이를 찾는다. 있으면 `transitionJiraIssue`(transition.id)로 전환한다(dry-run이면 "전환 예정"만 기록).
4. 일치하는 전이가 **없으면**: 억지로 다른 전이를 거치지 말고 전환 보류. 스레드에 {user} 계정 답글로 "✅ 2개 도달했으나 현재 상태(<현재상태>)에서 '배포승인'으로 바로 전환할 수 없어 자동 전환을 보류합니다. 수동 확인 부탁드립니다."(멱등 마커 포함). **보류 등록**(3단계 공통 규칙, `holdType=jira-transition`).
5. 전환 성공 시에는 **댓글을 남기지 않는다.**

## 6단계: 보류 건 재확인 (매 폴링, 새 요청 유무와 무관)
`{pending_holds_path}`를 Read 툴로 읽는다. 파일이 없거나 빈 배열이면 이 단계 스킵. 각 항목에 대해:
1. **만료**: `heldAt`이 7일을 초과했으면 항목을 제거한다(스레드에 답글 없음, 7단계 보고에 "만료 제거" 목록으로만 포함).
2. **새 댓글 확인**: `slack_read_thread`로 해당 스레드(`channel` + `messageTs`)를 읽어, `lastCheckedTs` **이후** TS의 댓글 중 **이 루틴이 단 답글(멱등 마커 포함)과 봇(`{qa_bot_slack_id}`) 메시지를 제외**한 새 댓글이 있는지 본다. 없으면 항목 유지, 다음 항목으로.
3. **해소 검증**: 새 댓글이 있으면 `{workspace}/harnie/skills/comment-resolve/SKILL.md`를 (아직 안 읽었다면) 지금 읽고, 그 방법론으로 **보류 사유(`holdReason`)가 실제 해소됐는지** 검증한다. `holdType`별 검증 대상:
   - `pr-not-found`: 댓글에서 ADO PR URL/번호를 추출한다. 있으면 그 PR로 **3단계 2~3항(스킵 판정 포함) 검토를 수행**한다 — 통과면 해소, 이슈면 미해소(사유 갱신). PR 정보가 없는 댓글이면 미해소.
   - `review-issue`: 댓글이 "수정했다" 취지면 az CLI로 그 PR의 새 커밋/변경을 확인해 **지적한 파일·문제가 실제로 반영됐는지** 검증한다(주장만으로 해소 판정 금지). 해명 취지면 comment-resolve 기준으로 타당성을 판정한다 — 타당하면 해소, 아니면 미해소. 확신이 낮으면 미해소.
   - `jira-transition`: Jira 티켓 상태를 재조회한다 — 이미 목표 상태('배포승인') 이후로 수동 전환돼 있으면 해소(추가 동작 없이 항목 제거), 지금은 목표 상태 전이가 가능해졌으면(공백 제거 비교) 전환 수행(5단계 규칙) 후 해소.
4. **해소 판정 시**: (dry-run이면 예정만 기록) 봇 ✅를 단다(4단계 헬퍼·멱등 규칙 동일) → ✅ 총 카운트 재확인 → N>=2면 5단계 Jira 전환까지 수행 → **해소 확인 답글**을 스레드에 {user} 계정으로 남긴다("확인되어 승인 처리했습니다" 취지 + 무엇으로 해소됐는지 한 줄, 멱등 마커 포함) → 항목 제거(N<2면 전환 없이 답글·제거만 — 후속 전환은 범위 밖).
5. **미해소 판정 시**: 스레드에 {user} 답글로 왜 아직 해소로 볼 수 없는지 짧게 남기고(멱등 마커 포함 — 같은 댓글에 대해 1회만), 항목의 `lastCheckedTs`를 이번에 확인한 가장 최신 댓글 TS로 갱신해 **같은 댓글을 다음 폴링에서 재검증하지 않게** 한다. 항목 유지.
6. 변경이 있으면 `{pending_holds_path}`를 저장한다(dry-run이면 저장하지 않고 "갱신 예정"만 기록).

## 7단계: 보고
이번 실행 결과를 간결한 한국어로 요약:
- 감지/대상 메시지 수, 어떤 멘션으로 들어왔는지
- 필터·중복으로 제외한 것
- 메시지별 결과: 검토 통과+✅(전체 검토 / **기존 리뷰 기반 스킵** / 새 커밋만 검토 — 어느 경로였는지 구분) / 보류(사유·holdType) / PR 못 찾음 / Jira 전환됨(KEY) / 전환 보류(사유)
- **보류 재확인 결과**: 확인한 보류 건 수 / 새 댓글 없음 / 해소→✅(및 Jira 전환 여부) / 미해소(사유) / 만료 제거
- **dry-run이면**: 실제로 수행하지 않고 하려 했던 동작 목록
오류 발생 시 어느 단계에서 실패했는지 명시(특히 MCP 인증 만료, 봇 토큰 문제).

## 안전/주의
- 한 번 처리한 메시지(봇 ✅, `{pending_holds_path}` 등록, 또는 멱등 마커 보류 답글 존재)는 **신규 수집 경로(1~2단계)에서는** 절대 재처리하지 않는다(2단계 멱등). 보류 건의 후속 처리는 오직 6단계가 `{pending_holds_path}` 기반으로 수행한다 — 두 경로가 같은 메시지를 이중 처리하지 않는다.
- 기존 리뷰 기반 스킵(3단계 2항)은 `{pr_review_state_path}`·`{review_findings_path}`를 **읽기만** 한다 — 이 루틴이 그 두 파일을 수정하지 않는다.
- 확신 낮으면 ✅를 달지 않는다(보류). 잘못된 배포 승인은 ✅보다 훨씬 나쁘다.
- 봇 ✅로 카운트가 1인 경우, 이미 '배포 승인'/완료 상태 티켓은 전환하지 않는다.
- 봇 토큰 값을 출력하지 않는다.
- **codex Slack 플러그인의 `slack_add_reaction`을 봇 ✅ 용도로 쓰지 않는다** (사용자 계정 인증이라 정체성이 섞임).
