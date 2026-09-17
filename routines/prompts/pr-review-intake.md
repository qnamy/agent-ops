<!-- sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다. 원본은 비공개 워크스페이스에서 운영 중. -->
# pr-review-intake

이 프롬프트 본문은 automation 트리거가 이미 줬다. **이 파일을 다시 읽지 않고, 자기 지시를 `rg`·`grep`으로 검색하지 않는다.** 재읽기 한 번과 자기 검색 한 번이 회차 도구 출력의 54%였다(2026-09-16 실측 7,659토큰). **개인 메모리(`~/.codex/memories/`)도 읽지 않는다** — 2026-09-17 07:20 회차가 첫 턴에 그것을 `rg`로 28,337자 올려 11턴 내내 다시 실었다. 무인 회차의 판단은 이 프롬프트와 맥락 파일의 `config`만으로 한다.

이 실행은 Slack의 PR 리뷰 요청을 수집해 Azure DevOps PR을 리뷰하고, 댓글을 남긴 PR만 `state/pr-review-worklist.jsonl`에 등록한다. 신규 스킬을 만들거나 기존 루틴·상태를 변경하지 않는다. 실행에 필요한 회사 좌표와 PR 댓글 면책 문구는 `state/gate/context.pr-review-intake.json`의 `config`에서 읽는다 — precheck가 `ROUTINE-CONFIG.md`를 이미 파싱해 실어 둔다. **`config`가 없을 때만 `~/work/ROUTINE-CONFIG.md`를 직접 읽는다.** 값을 프롬프트에 하드코딩하지 않는다. `~/work/.legacy-routine-state/`와 `~/work/legacy-routines/`는 읽지도 쓰지도 않는다 — 이 워크스페이스의 `state/`만 상태로 쓴다. 크리덴셜 값은 읽거나 출력·기록하지 않는다.

ADO는 Azure DevOps MCP가 아니라 모든 호출을 `bash bin/az pr-review-intake ...`로 한다. 사내 **이 세션은 `git` 명령을 실행하지 않는다.** 코드 판정은 PR별 세션이 하고 이 세션은 그 결과만 쓴다. diff가 이 컨텍스트에 들어오면 회차가 끝날 때까지 매 턴 다시 읽힌다. 조직·채널·사용자·유저그룹 멘션·면책 문구는 맥락 파일의 `config`에서 얻는다 — `adoOrg`·`channels`·`user`·`slackUser`·`botUser`·`mentions`·`prUrlPattern`·`disclaimer`다.

 **쓰기 직전의 lock check는 두 형태다.** 셸 명령인 쓰기(`bin/az`의 POST·PATCH·`set-vote`, 원장·worklist append, `state/deploy-approval-react.sh`, `pr-session.sh close`, `mark.py`)는 `bash bin/guarded.sh pr-review-intake "$TOKEN" run <명령…>` 또는 `bash bin/guarded.sh pr-review-intake "$TOKEN" append <파일> '<한 줄>'`로 실행한다 — 스크립트가 check를 먼저 하고 실패하면 명령을 실행하지 않고 exit 3으로 끝나며, 그때는 소유권을 잃은 것이니 그 자리에서 종료하고 상태 기록·commit·release를 시도하지 않는다. 셸 명령이 아닌 쓰기 — MCP 도구(Slack·Jira·Confluence)와 파일 도구로 덮어쓰는 `state/ask.*.md`·`state/ado-body.*.json` 같은 모든 `state/` 파일 — 는 직전에 `bash bin/lock.sh check pr-review-intake "$TOKEN"`을 따로 한다. **아래 본문의 'lock check 뒤'는 이 규칙대로 읽는다** — 셸 명령이면 guarded 한 번, 그 외면 check 한 번. 실행 수단이 무엇이든 `state/` 쓰기는 이 둘 중 하나다. 그 밖의 자리에서 `lock.sh check`를 부르지 않는다. 소유권 상실 뒤에는 상태 기록, 게이트 commit, release를 시도하지 않는다. 파일 생성·수정은 이 워크스페이스 안에서 한다. `/tmp` 등 워크스페이스 밖 경로에 스크립트나 파일을 만들지 않는다. **파일을 지우지 않는다** — `rm`은 승인 프롬프트를 띄우고 무인 회차에는 답할 사람이 없어 그 자리에서 멈춘다. 재사용하는 파일은 덮어쓴다. **`git worktree`를 만들지 않고 빌드·테스트·패키지 매니저 명령(`mvn`·`gradle`·`npm`·`pytest` 등)을 실행하지 않는다.** 판정은 정적 읽기로만 한다 — 작업 사본을 만들면 정리가 필요해지고 그 정리가 다시 승인 프롬프트를 부른다.

Slack 접근은 codex Slack 플러그인 도구로만 하며 **도구 이름과 인자를 탐색하지 않는다** — `ALL_TOOLS` 필터로 찾으면 그 목록 전체가 컨텍스트에 남아 회차가 끝날 때까지 매 턴 다시 읽힌다. 아래 이름과 인자를 그대로 쓴다.

- 채널 읽기 `mcp__codex_apps__slack_slack_read_channel({channel_id, oldest, latest, limit, response_format:"detailed"})`
- 스레드 읽기 `mcp__codex_apps__slack_slack_read_thread({channel_id, message_ts, oldest, limit, response_format:"detailed"})`
- 반응 확인 `mcp__codex_apps__slack_slack_get_reactions({channel_id, message_ts})`
- 답글·DM `mcp__codex_apps__slack_slack_send_message({channel_id, thread_ts, message})`

**인자 이름은 `channel_id`와 `message_ts`다.** `channel`·`ts`·`thread_id`로 부르면 필수 인자 누락으로 거부되고, 첫 Slack 수집 실패는 회차 중단 사유라 그 회차가 통째로 버려진다. 본문 필드는 `text`가 아니라 `message`다.

Slack Web API를 직접 호출하는 스크립트나 curl 명령을 만들지 않는다. 봇 ✅를 **다는** 것만 예외이며 그것은 `state/deploy-approval-react.sh` 헬퍼가 담당한다.


**도구 이름을 모를 때만 탐색하고, 탐색은 이름만 뽑는다.** `ALL_TOOLS` 필터 결과를 도구 객체째로 출력하면 설명 필드까지 컨텍스트에 박혀 회차가 끝날 때까지 매 턴 다시 읽힌다(2026-09-15 실측: 한 번에 8,920토큰). `x.name`만 출력하고, 같은 회차에서 같은 탐색을 두 번 하지 않는다.

## 도구와 명령 형식

### ADO 호출 규율

`repos`·`devops` 호출에는 `--org <config 조직 URL>`을 포함한다. 인증 확인용 `account show`는 그 인자를 받지 않으므로 붙이지 않는다. 모든 az 호출은 **단일 명령**으로만 실행한다. `cd`·파이프·리다이렉션을 쓰지 않으며, 복합이 필요하면 워크스페이스 안에 `.sh`를 만들고 `bash <파일>`로 실행한다. **조회 다이어트**: `--project` 없는 조직 전체 `pr list`와 `--top 1000`류 전량 덤프를 금지하고, 모든 조회는 `--query`로 필요한 최소 필드만 뽑는다. 대형 JSON 덤프는 컨텍스트를 태워 회차를 상한까지 끌고 간다(2026-08-24 실관측).

- **스레드 목록**: `bash bin/az pr-review-intake devops invoke --area git --resource pullRequestThreads --route-parameters project={project} repositoryId={repo} pullRequestId={PR_ID} --org <config 조직 URL> --api-version 7.1 -o json` → `value[]`(각 `comments[]`·`status`·`threadContext.filePath`·`comments[].author.uniqueName`·`comments[].publishedDate`).
  멱등 판정(내 댓글 존재)만 필요하면 `--query "value[?isDeleted != \`true\` && comments[0].commentType == 'text'].{id:id,status:status,author:comments[0].author.uniqueName}"`로 충분하다. **`commentType`을 반드시 건다** — 착수 투표가 `<내 표시 이름> voted -5`라는 내 이름의 `system` 스레드를 만들고, 그것을 내 루트 댓글로 세면 그 PR은 멱등 스킵되어 영원히 리뷰되지 않는다(2026-09-16 PR {PR} 실관측).
- **새 리뷰 스레드**: 본문 JSON을 `state/ado-body.pr-review-intake.json`에 쓴다 — `{"comments":[{"parentCommentId":0,"content":"...","commentType":"text"}],"status":"active","threadContext":{"filePath":"/{경로}","rightFileStart":{"line":N,"offset":1},"rightFileEnd":{"line":N,"offset":1}}}`를 넣고 `bash bin/az pr-review-intake devops invoke --area git --resource pullRequestThreads --route-parameters project={project} repositoryId={repo} pullRequestId={PR_ID} --org <config 조직 URL> --api-version 7.1 --http-method POST --in-file state/ado-body.pr-review-intake.json`. 매번 덮어쓰고 지우지 않는다.
- **대댓글**: 본문 JSON을 `state/ado-body.pr-review-intake.json`에 쓴다 — `{"content":"...","parentCommentId":{원댓글ID},"commentType":"text"}`를 넣고 `bash bin/az pr-review-intake devops invoke --area git --resource pullRequestThreadComments --route-parameters project={project} repositoryId={repo} pullRequestId={PR_ID} threadId={threadId} --org <config 조직 URL> --api-version 7.1 --http-method POST --in-file state/ado-body.pr-review-intake.json`. 매번 덮어쓰고 지우지 않는다.
- **투표**: `bash bin/az pr-review-intake repos pr set-vote --id {PR_ID} --vote {approve|approve-with-suggestions|wait-for-author|reject|reset} --org <config 조직 URL>`.

## 1. 회차 시작

`bash bin/round.py begin pr-review-intake`를 **한 번** 실행한다. dry-run 판정·락 획득·게이트 스냅샷·인증 확인·맥락 파일 읽기를 스크립트가 한 번에 처리해 JSON 한 줄로 돌려준다. 이것들을 따로 실행하지 않는다 — 각각이 도구 호출 한 턴이었고 할 일 없는 회차조차 그것만으로 8턴을 썼다.

받는 값은 `live`(dry-run 여부)·`token`·`runStartedEpoch`(토큰과 같은 값)·`snapshot`(pending을 snapshot으로 복사했음)·`auth`(`bin/az` 인증 확인 결과)·`context`(맥락 파일 `state/gate/context.pr-review-intake.json` 내용, 없으면 null)다. `token`을 `TOKEN`으로 보관한다.

`error`가 있으면(`lock-busy`·`no-pending`·`auth-failed`) 그 사유로 **대상 특정 전 실패**를 보고하고 종료한다 — 스크립트가 락을 이미 풀었으므로 release를 부르지 않는다.

`live`가 false면 dry-run이다. dry-run은 판단과 조회를 라이브와 같게 수행하지만 외부 쓰기, `state/` 쓰기, 게이트 commit을 하지 않고 수행 예정 목록만 보고한다.

## 2. 수집·판정·리뷰

`config`는 `begin` JSON의 `context.config`다 — 맥락 파일을 다시 읽지 않는다. `context`가 null이거나 `config`가 없을 때만 `~/work/ROUTINE-CONFIG.md`를 읽어 해석한다. 둘 다 실패하면 대상 특정 전 실패로 회차를 중단한다. 인증은 `begin`이 `auth:ok`로 이미 확인했다 — `account show`를 다시 부르지 않는다.

`lastRunTs`는 `begin` JSON의 `context.marks.lastRunTs`다 — **marks 파일을 읽지 않는다.** 그 파일의 `reviewedPrs` 279건(51KB, 12,519토큰)이 숫자 하나 때문에 매 회차 실렸다(2026-09-17 07:20 실측). 값이 없으면(null) **아래 식을 적용하지 않고** `oldest = runStartedEpoch - 1200`으로 둔다. 부트스트랩 값을 `lastRunTs`에 넣으면 식이 600초를 더 빼 창이 30분이 된다. ISO 날짜를 파싱하지 않고 epoch 산술만 쓴다.

Slack에서 `config`의 `channels`에 있는 `#pr-review-requests` 채널을 상세 포맷으로 페이지네이션하여 다음 구간을 끝까지 읽는다.

```
oldest = min(runStartedEpoch - 1200, lastRunTs - 600)
oldest = max(oldest, runStartedEpoch - 345600)
```

메시지 ts는 정수/epoch 비교로 `runStartedEpoch` 이후를 제외한다. 96시간 상한을 적용했으면 보고에 남긴다. 첫 Slack 수집 실패는 대상 특정 전 실패이므로 회차를 중단한다. raw 메시지가 0건이면 0건 가드를 표시하고 watermark를 전진시키지 않는다. raw 메시지가 있었으나 필터 뒤 PR이 0건인 것은 정상 수집이다.

본인·봇 메시지는 제외한다. 메시지의 mrkdwn 원문에 `config`의 `mentions` 리터럴 중 하나가 부분 문자열로 있어야 한다. 의미 추론으로 대체하지 않는다. 통과 메시지에서 `config`의 `prUrlPattern` 형식인 URL을 모두 추출해 project, repository, PR ID, 원 Slack channel·thread ts를 매핑한다.

각 PR은 순차 처리한다.

**completed PR의 source commit을 로컬에서 얻을 수 없으면 `처리 불가`로 분류한다.** 병합 시 `refs/pull/<id>/source`가 삭제되어 재시도로 복구되지 않는다. active PR의 커밋 부재는 `미처리`다. `처리 불가`는 보고에 사유와 함께 남긴다.

- 내 루트 댓글이 이미 있으면 재리뷰·재대댓글하지 않는다. **`commentType`이 `system`인 스레드는 내 이름으로 생성돼도 리뷰가 아니다** — 투표·푸시 알림이 그렇다.
- abandoned는 건너뛴다.
- active와 completed는 모두 리뷰한다.

**투표 전에 코드 판정이 가능한지 먼저 본다.** `begin` JSON의 `context`를 본다(맥락 파일을 다시 읽지 않는다). `context.prs`의 `<project>/<repository>#<pullRequestId>` 항목에 `status`·`srcCommit`·`tgtCommit`·`createdById`가 있으면 `repos pr show`를 다시 부르지 않는다. **항목에 `error`가 있거나 항목 자체가 없으면 그 PR을 `미처리`로 남기고 다음 PR로 간다 — 이 세션이 `repos pr show`를 대신 부르지 않는다.** 사전 조회가 실패한 PR은 다음 회차의 precheck가 다시 조회해 회복한다. 이어 `fetch`의 `<repository>#<pullRequestId>` 값을 본다. **`commit-present`일 때만 코드 판정이 가능하다** — `commit-missing`·`no-source-commit`·`status-unavailable`·`precheck-budget`·`pr-ref-missing`·`missing`·`fetch-failed`이거나 키가 없으면 active는 `미처리`, completed는 `처리 불가`로 분류하고 **투표도 worklist 등록도 하지 않는다.** 브랜치 fetch 성공은 그 커밋의 존재가 아니다 — precheck가 실제로 확인한 값이 `commit-present`다.

**커밋이 확인된 active PR은 코드를 보기 전에 먼저 `wait-for-author`로 투표한다.**

**커밋이 확인된 active PR은 코드를 보기 전에 먼저 `wait-for-author`로 투표한다.** lock check 뒤 즉시 찍는다. 리뷰가 몇 분 걸리는 동안 PR이 완료되는 창을 없애고, 회차가 중간에 실패해도 그 PR이 승인된 것처럼 남지 않는다. **멱등 스킵한 PR(내 루트 댓글이 이미 있음)과 completed PR에는 찍지 않는다** — 뒤 회차가 올려놓은 투표를 되돌리게 된다.

**같은 자리에서 worklist에 `op:"add"`로 등록한다.** 투표만 찍고 등록하지 않으면, 이어지는 코드 판정이 실패했을 때 그 PR은 `wait-for-author`가 걸린 채 어떤 회차도 다시 보지 않는 상태로 남는다. 등록해 두면 `pr-review-resolve`가 미해결 지적 0건으로 보고 `approve`로 올린 뒤 close한다.

**코드 판정은 PR별 세션에서 한다. 이 세션은 `git` 명령을 실행하지 않는다.** diff가 이 컨텍스트에 들어오면 회차가 끝날 때까지 매 턴 다시 읽힌다.

1. `bash bin/pr-session.sh ensure "<project>/<repository>#<pullRequestId>"`로 세션을 얻는다. 실패하면 그 PR을 `미처리`로 남기고 다음 PR로 간다.
2. `state/ask.pr-review-intake.md`에 지시를 쓴다. project·repository·PR id·source commit·target commit과 맥락 `prs` 항목의 `numstat`·`patch` 경로를 함께 담고, 아래를 담는다.
   - `~/work/harnie/skills/pr-review/SKILL.md`와 레포에 적용되는 팀 리뷰 규칙을 읽고 그 기준으로 판단한다. 기준 본문을 복사하지 않는다.
   - **PR 소속 커밋의 변경은 precheck가 이미 파일로 떨궜다.** 워커에게 **`git diff`를 직접 부르지 말라**고 쓴다. 워커는 `numstat`(파일별 추가·삭제 줄 수, 경로가 잘리지 않아 ADO filePath로 그대로 쓴다)을 먼저 읽어 볼 파일을 정하고, **rename된 파일은 옛 경로의 삭제 줄과 새 경로의 추가 줄로 따로 나오니 ADO `filePath`로는 추가 쪽(새) 경로만 쓴다 — 옛 경로는 source에 없다.**  `patch`에서 그 파일의 `diff --git` 구간을 찾아 그 부분만 읽는다 — 워커의 Bash는 `git --no-optional-locks`만 허용되므로(`pr-session.sh`) 셸 `grep`이 아니라 자기 파일 검색 도구로 찾는다. 변경 파일이 몇 개뿐이면 `patch`를 통째로 읽어도 된다. 변경 주변 코드가 더 필요할 때만 `git --no-optional-locks -C ~/work/<repository> show <source commit>:<경로>`를 쓴다. 라인 번호는 실제 source 기준이다. fetch·clone·working tree 접근과 레포 쓰기는 금지한다. **맥락 항목에 `numstat`·`patch`가 없을 때만** 워커가 직접 범위를 잡는다 — target..source 전체 diff가 아니라 PR 커밋 목록 또는 source 첫 커밋 부모부터 source까지다.
   - ADO·Slack에 접근하지 않는다. 댓글·투표는 오케스트레이터가 한다.
   - 결과를 **`{{RESULT_PATH}}`** 경로에 JSON 하나로 쓴다 — **이 문자열을 지시에 반드시 넣는다** — `ask`가 보내는 시점에 실제 경로로 치환한다. 빠뜨리면 세션이 결과를 어디에 쓸지 알 수 없어 그 PR이 timeout된다. 세션이 경로를 스스로 조회하지 않는다. `{"findings":[{"prefix":"issue|discuss|nit","filePath":"/경로","line":N,"content":"지적 본문"}],"summary":"한 줄 요약"}`이고 지적이 없으면 `findings`는 `[]`다. `content`에 프리픽스·멘션·면책을 넣지 않는다.
3. `bash bin/pr-session.sh ask "<key>" state/ask.pr-review-intake.md`를 실행한다. 출력이 `ok <경로>`로 시작하지 않으면 그 PR을 `미처리`로 남기고 다음 PR로 간다 — **이 세션이 대신 판정하지 않는다.**
4. `ask`가 성공 시 출력하는 `ok <경로>`의 그 경로에서 JSON을 읽어 그 내용만 쓴다. 경로를 따로 조회하지 않는다.

지적은 실제 변경 파일의 정확한 filePath·라인에 내가 루트인 새 ADO 스레드로 작성한다. 타인의 active 스레드에는 접두어 없는 보조 의견만 대댓글로 남긴다. 새 지적은 `issue:`·`discuss:`·`nit:` 분류와 PR 작성자 `@<GUID>` 리터럴 멘션을 첫 줄에 쓰고, `config`의 `disclaimer` 두 줄을 마지막에 실제 줄바꿈으로 붙인다. 새 스레드 JSON 작성과 POST 직전, 그리고 각 ADO 쓰기 직전에 lock check를 한다.

착수 투표 직후, 그리고 첫 댓글을 실제로 남긴 직후, 라이브면 lock check 뒤 `state/pr-review-worklist.jsonl`에 다음 한 줄을 append한다. 같은 key의 중복 `add`는 폴드가 흡수하므로 두 시점 모두에서 남긴다. `key`는 `"<project>/<repository>#<pullRequestId>"`, `op`은 `add`, `by`는 `pr-review-intake`이며 title 등 항목 전체를 넣는다. 같은 PR의 재등록은 같은 key의 더 늦은 add로 표현한다. 댓글이 나간 뒤 이 등록이 실패하면 그 PR을 미처리로 남기고 다음 PR로 간다.

각 새 댓글마다 라이브면 lock check 뒤 `state/review-findings.jsonl`에 현행 필드(`date`, `prefix`, `project`, `repository`, `pullRequestId`, `filePath`, `summary`)를 한 줄 append한다. 실패는 그 PR 실패다. dry-run에서는 등록·감사 로그의 예정만 보고한다.

리뷰를 마치면 라이브에서 lock check 뒤 `state/pr-review-summary.jsonl`에 한 줄 append한다. `ts`, `key`, `project`, `repository`, `pullRequestId`, `srcCommit`(판정한 source commit), `prefixes`(이 회차 지적의 프리픽스 목록), `summary`(세션이 준 한 줄), `vote`(아래에서 정한 값)를 담는다. **`deploy-approve-intake`가 이 원장을 먼저 읽어 같은 PR을 다시 리뷰하지 않는다.**

리뷰를 마치면 active PR의 투표를 이 지적 구성으로 정한다. `issue:`·`discuss:`가 하나라도 있으면 **투표를 바꾸지 않는다**(착수 때 찍은 `wait-for-author`가 그대로 남는다). `nit:`만 있으면 `approve-with-suggestions`, 지적이 하나도 없으면 `approve`다. completed PR은 투표하지 않는다. **지적이 하나도 없는 PR은 그 투표가 성공한 뒤에만** 착수 때 등록한 worklist 항목을 닫는다 — lock check 뒤 `op:"close"`, `reason:"no-findings"`, `by:"pr-review-intake"`를 append한다. 등록한 쪽이 닫아야 하지만, 투표가 실패했는데 닫으면 승인되지 않은 PR이 추적에서 빠지고 resolver도 읽지 못한다. 투표가 실패하면 닫지 않고 그 PR을 미처리로 남긴다. **`approve` 또는 `approve-with-suggestions`가 성공한 PR은 worklist에서 닫고 세션도 닫는다.** lock check 뒤 `op:"close"`, `reason`은 각각 `no-findings`·`nit-only`, `by:"pr-review-intake"`를 append한 뒤 lock check 뒤 `bash bin/pr-session.sh close "<key>"`를 실행한다. 승인된 PR은 재검토 대상이 아니다 — `nit:`은 작성자 선택이라 그 스레드가 열려 있다는 이유로 추적을 유지하면 worklist와 세션이 무기한 점유된다. `wait-for-author`가 남은 PR의 세션은 유지한다 — `pr-review-resolve`가 그 세션에 재리뷰를 요청한다.

completed PR을 새로 리뷰했으면 원 Slack thread를 먼저 읽어 같은 취지의 대댓글이 없을 때만 한 메시지에 합쳐 참고용 리뷰 대댓글을 보낸다. 투표·Slack 대댓글 직전에도 각각 lock check를 한다.

PR 하나의 ADO·Slack·로컬 읽기·쓰기·상태 기록 실패는 그 PR만 `미처리`로 남기고 다음 PR을 계속 처리한다. 모든 대상이 성공해야만 회차가 성공이며, **`처리 불가`로 분류한 PR은 이 판정에서 뺀다.**

## 3. 상태 기록

raw 수집이 0건이 아니고 모든 대상이 성공했으며 라이브일 때만 `bash bin/guarded.sh pr-review-intake "$TOKEN" run python3 bin/mark.py pr-review-intake <runStartedEpoch> '<이 회차에 성공적으로 리뷰한 PR의 JSON 배열, 현행 reviewedPrs 항목 형식>'`을 실행한다. 스크립트가 `lastRunTs` 전진(뒤로 가지 않는다)·`reviewedPrs` append·오래된 것부터 500건 트림·원자 교체를 한다 — 이 세션이 marks 파일을 읽거나 쓰지 않는다. raw 0건·PR 실패·상태 기록 실패면 실행하지 않는다. dry-run에서는 기록 예정만 보고한다.

## 4. 회차 종료와 보고

정상 경로에서는 `bash bin/round.py finish pr-review-intake "$TOKEN" [--commit]`를 **한 번** 실행한다. 스크립트가 lock check → 게이트 commit → 락 해제를 한 번에 처리한다. `--commit`은 모든 대상과 상태 기록이 성공했고 라이브일 때만 붙인다. dry-run, raw 0건 가드, PR 하나라도 미처리, 또는 상태 기록 실패에서는 commit하지 않는다. `error`가 `lock-lost`면 소유권을 잃은 것이라 아무것도 하지 않았다는 뜻이다. `lock.sh release`·`precheck.py commit`·`pr-session.sh sweep`을 따로 부르지 않는다.

보고는 한국어로 조회 창·96시간 캡·raw 0건 여부, 감지·제외·미처리 PR과 사유, PR별 댓글/투표/Slack 대댓글, worklist·감사 로그·mark·commit 여부, dry-run 수행 예정 목록을 남긴다. 크리덴셜은 보고하지 않는다.
