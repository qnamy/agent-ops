<!-- sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다. 원본은 비공개 워크스페이스에서 운영 중. -->
# deploy-approve-intake

이 프롬프트 본문은 automation 트리거가 이미 줬다. **이 파일을 다시 읽지 않고, 자기 지시를 `rg`·`grep`으로 검색하지 않는다.** 재읽기 한 번과 자기 검색 한 번이 회차 도구 출력의 54%였다(2026-09-16 실측 7,659토큰). **개인 메모리(`~/.codex/memories/`)도 읽지 않는다** — 2026-09-17 07:20 회차가 첫 턴에 그것을 `rg`로 28,337자 올려 11턴 내내 다시 실었다. 무인 회차의 판단은 이 프롬프트와 `ROUTINE-CONFIG.md`만으로 한다.

이 실행은 `#deploy-approval`의 새 배포 승인 요청을 수집해 PR을 판정하고, 통과한 요청에 봇 ✅를 달며, 보류 요청만 `state/deploy-approve-worklist.jsonl`에 등록한다. `~/work/ROUTINE-CONFIG.md`를 필요 시 읽어 채널, 사용자, ADO 조직, Jira 좌표와 멱등 마커를 얻는다. 회사 좌표·GUID·크리덴셜을 하드코딩하거나 출력·기록하지 않는다. `~/work/.legacy-routine-state/`와 `~/work/legacy-routines/`는 읽지도 쓰지도 않는다 — 이 워크스페이스의 `state/`만 상태로 쓴다.

**봇 토큰과 반응 헬퍼는 이 워크스페이스 안에 있다** — 토큰은 `state/.deploy-approval-bot-token`(600), 헬퍼는 `state/deploy-approval-react.sh`다. `ROUTINE-CONFIG.md`의 `deploy_bot_token_path`·`deploy_bot_react_helper`는 현행 루틴용 경로이므로 쓰지 않는다. 토큰은 `test -s state/.deploy-approval-bot-token`으로만 확인하고 `cat`하지 않으며 값을 출력·기록하지 않는다. ✅는 `sh state/deploy-approval-react.sh <채널> <messageTs>`로만 단다 — 헬퍼가 자기 디렉터리에서 토큰을 읽으므로 토큰 경로를 인자로 넘기지 않는다.

ADO 호출은 모두 `bash bin/az deploy-approve-intake ...`로 한다. **이 세션은 `git` 명령을 실행하지 않는다.** 코드 판정은 PR별 세션이 하고 이 세션은 그 결과만 쓴다. diff가 이 컨텍스트에 들어오면 회차가 끝날 때까지 매 턴 다시 읽힌다(2026-09-16 11:20 회차가 `git diff` 3회로 72,860자를 올렸다). **쓰기 직전의 lock check는 두 형태다.** 셸 명령인 쓰기(`bin/az`의 POST·PATCH·`set-vote`, 원장·worklist append, `state/deploy-approval-react.sh`, `pr-session.sh close`, `mark.py`)는 `bash bin/guarded.sh deploy-approve-intake "$TOKEN" run <명령…>` 또는 `bash bin/guarded.sh deploy-approve-intake "$TOKEN" append <파일> '<한 줄>'`로 실행한다 — 스크립트가 check를 먼저 하고 실패하면 명령을 실행하지 않고 exit 3으로 끝나며, 그때는 소유권을 잃은 것이니 그 자리에서 종료하고 상태 기록·commit·release를 시도하지 않는다. 셸 명령이 아닌 쓰기 — MCP 도구(Slack·Jira·Confluence)와 파일 도구로 덮어쓰는 `state/ask.*.md`·`state/ado-body.*.json` 같은 모든 `state/` 파일 — 는 직전에 `bash bin/lock.sh check deploy-approve-intake "$TOKEN"`을 따로 한다. **아래 본문의 'lock check 뒤'는 이 규칙대로 읽는다** — 셸 명령이면 guarded 한 번, 그 외면 check 한 번. 실행 수단이 무엇이든 `state/` 쓰기는 이 둘 중 하나다. 그 밖의 자리에서 `lock.sh check`를 부르지 않는다. 파일 생성·수정은 이 워크스페이스 안에서 한다. `/tmp` 등 워크스페이스 밖 경로에 스크립트나 파일을 만들지 않는다. **파일을 지우지 않는다** — `rm`은 승인 프롬프트를 띄우고 무인 회차에는 답할 사람이 없어 그 자리에서 멈춘다. 재사용하는 파일은 덮어쓴다. **`git worktree`를 만들지 않고 빌드·테스트·패키지 매니저 명령(`mvn`·`gradle`·`npm`·`pytest` 등)을 실행하지 않는다.** 판정은 정적 읽기로만 한다 — 작업 사본을 만들면 정리가 필요해지고 그 정리가 다시 승인 프롬프트를 부른다.

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

### Jira 전이 형식

Jira 도구도 **이름을 탐색하지 않는다** — 정규화된 이름을 그대로 호출한다. 조회는 `mcp__codex_apps__atlassian_rovo__legacy__atlassian_rovo_legacy_getjiraissue`, 원격 링크는 `mcp__codex_apps__atlassian_rovo__legacy__atlassian_rovo_legacy_getjiraissueremoteissuelinks`, 전이는 `mcp__codex_apps__atlassian_rovo__legacy__atlassian_rovo_legacy_transitionjiraissue`다.

조회(cloudId은 ROUTINE-CONFIG, `fields=["status"]`, `expand=transitions`)로 현재 상태와 가능한 전이를 함께 얻는다. 전이 목록 전용 도구를 따로 부르지 않는다. `to.name`이 목표 상태와 일치(공백 제거 비교)하는 전이가 있을 때만 위 전이 도구로 전환한다.

## 1. 회차 시작

`bash bin/round.py begin deploy-approve-intake`를 **한 번** 실행한다. dry-run 판정·락 획득·게이트 스냅샷·봇 토큰 확인·인증 확인·맥락 파일 읽기·worklist 폴드를 스크립트가 한 번에 처리해 JSON 한 줄로 돌려준다. 이것들을 따로 실행하지 않는다 — 각각이 도구 호출 한 턴이었고 할 일 없는 회차조차 그것만으로 8턴을 썼다.

받는 값은 `live`(dry-run 여부)·`token`·`runStartedEpoch`(토큰과 같은 값)·`snapshot`(pending을 snapshot으로 복사했음)·`botToken`·`auth`(`bin/az` 인증 확인 결과)·`context`(맥락 파일 `state/gate/context.deploy-approve-intake.json` 내용, 없으면 null)·`worklist`(`deploy-approve-worklist.jsonl`의 활성 집합, 폴드 완료)다. `token`을 `TOKEN`으로 보관한다.

`error`가 있으면(`lock-busy`·`no-pending`·`bot-token-missing`·`auth-failed`·`fold-failed`) 그 사유로 **대상 특정 전 실패**를 보고하고 종료한다 — 스크립트가 락을 이미 풀었으므로 release를 부르지 않는다.

`live`가 false면 dry-run이다. 조회·수집·PR 특정·판정은 라이브와 같게 수행하되 Slack 답글·봇 ✅·Jira 전이와 모든 `state/` 쓰기·commit은 수행 예정으로만 보고한다.

## 2. 수집·판정·보류 등록

ROUTINE-CONFIG를 읽어 해석한다(Jira·멱등 마커는 맥락에 없다). 봇 토큰과 인증은 `begin`이 `botToken:ok`·`auth:ok`로 이미 확인했다 — `test -s`도 `account show`도 다시 하지 않고, 토큰 값은 어디에도 출력·로그하지 않는다. ROUTINE-CONFIG 해석, 상태 루트 접근, 최초 Slack 수집 중 하나라도 실패하면 대상 특정 전 실패로 회차를 중단하고 상태를 전진시키지 않는다.

`runStartedEpoch`은 `begin` JSON의 값이다. `lastRunTs`는 `begin` JSON의 `context.marks.lastRunTs`다 — marks 파일을 읽지 않는다. 값이 없으면(null) **아래 식을 적용하지 않고** `oldest = runStartedEpoch - 1200`으로 둔다. 부트스트랩 값을 `lastRunTs`로 다루면 식이 600초를 더 빼 창이 30분이 된다. `lastRunTs`가 있으면 다음처럼 epoch 산술로만 수집 하한을 정한다.

```
oldest = min(runStartedEpoch - 1200, lastRunTs - 600)
oldest = max(oldest, runStartedEpoch - 345600)
```

Slack 읽기는 ROUTINE-CONFIG의 `#deploy-approval` 채널에서 `oldest`를 기준으로 페이지네이션한다. 최신 30개로 자르지 말고, 창 안의 모든 페이지를 읽을 때까지 계속한다. raw 수집이 0건이면 0건 가드로 `lastRunTs`를 전진시키지 않고 보고한다. raw 메시지는 있었지만 필터 후 대상이 0건인 것은 정상 성공이다. 메시지 TS가 창 안이고, 대상 멘션 하나 이상, Jira 티켓 링크 하나 이상, 배포 승인 취지, 본인·봇 이외 작성자를 모두 만족한 메시지만 대상으로 삼는다. 각 메시지에서 모든 Jira KEY와 직접 PR URL이 있으면 그 URL을 보관한다.

활성 보류 집합은 `begin` JSON의 `worklist`다 — 폴드를 다시 하지 않는다. 봇이 이미 ✅를 달았거나 활성 worklist에 같은 `"<channel>/<messageTs>"` key가 있거나 멱등 마커 보류 답글이 있으면 신규 수집 경로에서 제외한다.

각 대상 메시지를 순차 처리한다. PR은 메시지의 직접 URL이 있으면 `bash bin/az deploy-approve-intake repos pr show`로 확정하고, 없으면 Jira를 순서대로 본다 — **먼저** `mcp__codex_apps__atlassian_rovo__legacy__atlassian_rovo_legacy_getjiraissueremoteissuelinks({cloudId, issueIdOrKey})`, 그다음 `mcp__codex_apps__atlassian_rovo__legacy__atlassian_rovo_legacy_getjiraissue({cloudId, issueIdOrKey, fields:["summary","description","project","status","customfield_10000"], expand:"transitions"})`의 본문·개발 패널. **`fields`에 `comment`를 처음부터 넣지 않는다** — 댓글이 응답의 대부분이라 회당 2.8만 자였다(2026-09-16 실측). 둘에서 못 찾았을 때만 `comment`를 넣어 다시 조회한다. 찾은 URL은 같은 `repos pr show`로 확정한다. Jira에서 못 찾은 경우에만 프로젝트·레포를 좁혀 `bash bin/az deploy-approve-intake repos pr list --project <project> [--repository <repo>] --status all --top 50`으로 후보를 찾고 필요한 필드만 query한다. 조직 전체 목록이나 대형 JSON 덤프를 하지 않는다.

PR을 특정했으면 **코드를 보기 전에 `python3 bin/prior-review.py <project> <repository> <pullRequestId>`를 실행한다.** 세 원장(`pr-review-summary.jsonl`·`reviewedPrs`·`review-findings.jsonl`)에서 그 PR 것만 걸러 `summary`·`reviewed`·`findings`로 돌려주므로 **원장 파일을 직접 읽지 않는다** — PR 하나 때문에 88KB와 52KB를 읽었다. `summary`가 그 PR의 가장 늦은 요약 줄이다. **그 줄의 `srcCommit`이 지금 PR의 `lastMergeSourceCommit.commitId`와 같을 때만** 재사용한다 — 다르면 리뷰 이후 새 커밋이 올라온 것이므로 그 줄을 쓰지 않고 직접 판정한다. 재사용할 때는 `prefixes`에 `issue:`나 `discuss:`가 있으면 `review-issue` 보류, 없으면 리뷰 측면 통과로 보고 **코드를 다시 읽지 않는다.** 줄이 없거나 commit이 다르면 이 PR을 직접 판정한다. `pr-review-resolve`가 재투표할 때 이 원장을 갱신하므로, 해소된 지적은 가장 늦은 줄에 남지 않는다.

PR을 특정하지 못하면 라이브에서 lock check 뒤 스레드에 티켓을 명시한 `자동으로 특정하지 못했습니다. 수동 확인 부탁드립니다.` 답글과 ROUTINE-CONFIG의 멱등 마커를 남긴다. 답글 실패와 무관하게 lock check 뒤 worklist에 `op:"add"` 한 줄을 append한다. 이벤트는 `ts`, `op`, `key`, `by:"deploy-approve-intake"`와 기존 hold 스키마 전체(`messageTs`, `channel`, `ticketKeys`, `project`, `repository`, `prId`, `holdType:"pr-not-found"`, `holdReason`, `heldAt`, `lastCheckedTs`)를 가진다. 같은 key의 활성 항목은 중복 등록하지 않는다.

`summary`를 재사용하지 못했으면 같은 출력의 `reviewed`·`findings`를 쓴다. `reviewed`가 있으면 해당 PR의 미해결 `issue:` 스레드를 `bash bin/az deploy-approve-intake devops invoke`로 확인하고, 남아 있으면 `review-issue`로 보류한다. 모두 해소됐으면 `pullRequestCommits`에서 `reviewedAt` 이후 새 커밋을 확인한다. 새 커밋이 없으면 기존 리뷰 기반 통과다. 새 커밋이 있으면 그 새 커밋 변경만, `reviewed`가 없으면 PR 소속 커밋 변경 전체를 아래 방식으로 판정한다.

**코드 판정은 PR별 세션에서 한다.**

1. `bash bin/pr-session.sh ensure "deploy:<project>/<repository>#<pullRequestId>"`로 세션을 얻는다. **key에 `deploy:` 접두어를 붙인다** — `pr-review-resolve`의 sweep이 자기 worklist 밖 세션을 매 회차 닫는데, 두 automation의 락이 별개라 이 세션이 ask 도중에 닫힐 수 있다. 접두어가 붙은 세션은 sweep이 건너뛴다. `pr-review-intake`의 세션을 재사용하지 않는다. 실패하면 그 메시지를 미처리로 남기고 다음 메시지로 간다.
2. `state/ask.deploy-approve-intake.md`에 지시를 쓴다. project·repository·PR id·source commit·target commit과 판정 범위(PR 소속 커밋 전체인지 `reviewedAt` 이후 새 커밋만인지)를 담고, 아래를 담는다.
   - `~/work/harnie/skills/deploy-approval/SKILL.md`를 읽고 그 기준으로 **차단(issue 수준) 문제만** 찾는다. 기준 본문을 복사하지 않는다. `nit:`·스타일은 내지 않는다. 확신이 낮은 것은 `findings`에 넣지 않고 `summary`에 적는다.
   - `git --no-optional-locks -C ~/work/<repository>` 읽기 명령만 쓴다. fetch·clone·working tree 접근과 레포 쓰기는 금지한다. 판정에 필요한 commit이 로컬에 없으면 코드를 보지 말고 `commitPresent:false`로 결과를 쓴다.
   - ADO·Slack·Jira에 접근하지 않는다. 답글·✅·전이는 오케스트레이터가 한다.
   - 결과를 **`{{RESULT_PATH}}`** 경로에 JSON 하나로 쓴다 — **이 문자열을 지시에 반드시 넣는다** — `ask`가 보내는 시점에 실제 경로로 치환한다. 빠뜨리면 세션이 결과를 어디에 쓸지 알 수 없어 timeout된다. `{"commitPresent":true|false,"findings":[{"prefix":"issue","filePath":"/경로","line":N,"content":"지적 본문"}],"summary":"한 줄 요약"}`이고 차단 문제가 없으면 `findings`는 `[]`다.
3. `bash bin/pr-session.sh ask "deploy:<project>/<repository>#<pullRequestId>" state/ask.deploy-approve-intake.md`를 실행한다. 출력이 `ok <경로>`로 시작하지 않으면 그 메시지를 미처리로 남긴다 — **이 세션이 대신 판정하지 않는다.**
4. 그 경로의 JSON만 쓴다. `commitPresent`가 false면 아래 fetch-queue 규칙으로 간다. `findings`가 하나라도 있으면 `review-issue` 보류, 비어 있으면 리뷰 측면 통과다. 확신이 낮다는 `summary`는 보류 사유로 쓴다.
5. 결과를 읽었으면 lock check 뒤 `bash bin/pr-session.sh close "deploy:<project>/<repository>#<pullRequestId>"`로 세션을 닫는다. 배포 판정은 1회성이라 재사용할 일이 없고, 남겨 두면 유휴 터미널이 쌓인다.

`review-issue` 보류에서는 라이브의 lock check 뒤 지적 요약과 멱등 마커를 스레드에 한 번 남기고, 답글 성공 여부와 무관하게 같은 형식의 worklist `add`를 append한다. PR별 답글·ADO 조회·로컬 읽기·worklist 기록 실패는 해당 메시지만 미처리로 남기고 다음 메시지를 계속 처리한다.

판정 통과 메시지에는 라이브에서 lock check 뒤 `sh state/deploy-approval-react.sh <deploy_approval_channel> <messageTs>`를 실행한다. `slack_add_reaction`을 사용하지 않는다. `already_reacted`는 멱등 성공이며 토큰과 응답의 민감한 값을 보고하지 않는다. 채널을 다시 조회해 ✅ 총수를 센다. N이 2 미만이면 추적·답글 없이 끝낸다.

N이 2 이상이면 연결된 모든 Jira 티켓의 상태와 가능한 전이를 조회한다. 상태명과 전이명은 공백을 제거해 목표 상태 `배포승인`과 비교한다. 이미 목표 상태 또는 그 이후·완료이면 멱등 성공이다. 목표 상태로 가는 전이가 있으면 lock check 뒤 전이한다. 전이가 없거나 일부 티켓 전이에 실패하면 우회하지 않고 `jira-transition`으로 보류한다. 라이브에서 lock check 뒤 사유와 멱등 마커를 스레드에 남기고, 답글 실패와 무관하게 hold 스키마 전체를 가진 worklist `add`를 append한다. 모든 연결 티켓이 목표 상태에 도달하면 댓글 없이 성공으로 끝낸다.

워커가 `commitPresent:false`를 돌려주면 뒤처진 commit으로 판정하지 않는다. 라이브에서 lock check 뒤 `state/fetch-queue`에 그 레포 이름 한 줄을 append하고 해당 메시지를 미처리로 남긴 뒤 다음 메시지를 계속 처리한다. fetch·clone은 하지 않는다.

모든 대상이 성공해야 회차가 성공이다. 대상 하나의 실패는 그 대상만 미처리로 남기며, raw 0건도 성공 회차가 아니다.

## 3. 상태 기록

raw 수집이 0건이 아니고 모든 대상이 성공했으며 라이브일 때만 `bash bin/guarded.sh deploy-approve-intake "$TOKEN" run python3 bin/mark.py deploy-approve-intake <runStartedEpoch>`을 실행한다. 스크립트가 `lastRunTs`를 전진시킨다(뒤로 가지 않는다) — 이 세션이 marks 파일을 읽거나 쓰지 않는다. 대상 하나라도 미처리이거나 상태 기록 실패면 전진시키지 않는다. dry-run에서는 기록 예정만 보고한다.

## 4. 회차 종료와 보고

정상 경로에서는 `bash bin/round.py finish deploy-approve-intake "$TOKEN" [--commit]`를 **한 번** 실행한다. 스크립트가 lock check → 게이트 commit → 락 해제를 한 번에 처리한다. `--commit`은 모든 대상과 상태 기록이 성공했고 라이브일 때만 붙인다. dry-run, raw 0건 가드, 미처리 대상, 또는 상태 기록 실패에서는 commit하지 않는다. `error`가 `lock-lost`면 소유권을 잃은 것이라 아무것도 하지 않았다는 뜻이다. `lock.sh release`·`precheck.py commit`·`pr-session.sh sweep`을 따로 부르지 않는다.

한국어 보고에는 조회 창·96시간 캡·페이지 수·raw 0건 여부, 감지·제외·미처리 메시지와 사유, PR 특정·기존 리뷰 스킵·새 커밋 검토·보류 유형, 봇 ✅·반응 수·Jira 전이·worklist·fetch queue·mark·commit 여부와 dry-run 수행 예정 목록을 남긴다. 크리덴셜은 보고하지 않는다.

## 보류 등록의 고정 규칙

대댓글 게시가 실패해도 **보류 등록은 반드시 한다**(현행 `deploy-approval-approval-autopilot.md:59`). 그때 `lastCheckedTs`는 **현재 epoch 초**를 문자열로 넣는다 — 비우거나 null로 두면 resolve의 precheck가 0으로 취급해 그 스레드의 기존 댓글 전부를 새 답글로 보고 같은 보류를 매 회차 다시 처리한다. 게시 실패 사실은 보고에 남긴다.
