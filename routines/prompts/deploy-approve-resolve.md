<!-- sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다. 원본은 비공개 워크스페이스에서 운영 중. -->
# deploy-approve-resolve

이 파일을 지금 읽은 것이 정상이다 — 트리거는 경로만 준다. **이 파일은 한 번만 읽고 다시 읽지 않고, 자기 지시를 `rg`·`grep`으로 검색하지 않는다.** 재읽기 한 번과 자기 검색 한 번이 회차 도구 출력의 54%였다(2026-09-16 실측 7,659토큰). **개인 메모리(`~/.devin/`·`~/.codex/memories/`)도 읽지 않는다** — 2026-09-17 07:20 회차가 첫 턴에 그것을 `rg`로 28,337자 올려 11턴 내내 다시 실었다. 무인 회차의 판단은 이 프롬프트와 `ROUTINE-CONFIG.md`만으로 한다.

이 실행은 `state/deploy-approve-worklist.jsonl`의 활성 보류 항목만 재확인한다. 신규 배포 승인 요청은 수집하지 않는다. `~/work/ROUTINE-CONFIG.md`를 필요 시 읽어 회사 좌표, Jira 좌표와 멱등 마커를 얻고, 크리덴셜·회사 식별자를 하드코딩하거나 출력·기록하지 않는다. `~/work/.legacy-routine-state/`와 `~/work/legacy-routines/`에는 쓰지 않는다.

**봇 토큰과 반응 헬퍼는 이 워크스페이스 안에 있다** — 토큰은 `state/.deploy-approval-bot-token`(600), 헬퍼는 `bin/deploy-approval-react.sh`다. `ROUTINE-CONFIG.md`의 `deploy_bot_token_path`·`deploy_bot_react_helper`는 현행 루틴용 경로이므로 쓰지 않는다. 토큰은 `test -s state/.deploy-approval-bot-token`으로만 확인하고 `cat`하지 않으며 값을 출력·기록하지 않는다. ✅는 `sh bin/deploy-approval-react.sh <채널> <messageTs>`로만 단다 — 헬퍼가 자기 디렉터리에서 토큰을 읽으므로 토큰 경로를 인자로 넘기지 않는다.

ADO 호출은 모두 `bash bin/az deploy-approve-resolve ...`로 한다. 사내 레포는 `git --no-optional-locks -C ~/work/<repository> ...` 읽기 명령만 사용하며 fetch·clone·working tree 쓰기를 하지 않는다. **쓰기 직전의 lock check는 세 형태다.**
셸 명령인 쓰기(`bin/az`의 POST·PATCH·`set-vote`, 원장·worklist append, `bin/deploy-approval-react.sh`, `mark.py`)는 `bash bin/guarded.sh deploy-approve-resolve "$TOKEN" run <명령…>` 또는 `bash bin/guarded.sh deploy-approve-resolve "$TOKEN" append <파일> '<한 줄>'`로 실행한다 — 스크립트가 check를 먼저 하고 실패하면 명령을 실행하지 않고 exit 3으로 끝나며, 그때는 소유권을 잃은 것이니 그 자리에서 종료하고 상태 기록·commit·release를 시도하지 않는다.
매번 전체를 다시 쓰는 `state/` 파일은 `bash bin/guarded.sh deploy-approve-resolve "$TOKEN" write <파일> <<'__BODY__'`에 이어 JSON 한 벌과 `__BODY__`를 넘기는 한 호출로 쓴다 — check가 그 안에 들어 있으므로 직전 check를 따로 하지 않고, 그 파일을 이 호출 바깥에서 리다이렉션이나 파일 도구로 먼저 열지도 않는다.
그 외 셸 명령이 아닌 쓰기 — MCP 도구(Slack·Jira·Confluence) 호출과 파일 도구의 부분 수정 — 는 직전에 `bash bin/lock.sh check deploy-approve-resolve "$TOKEN"`을 따로 한다.
**아래 본문의 'lock check 뒤'는 이 규칙대로 읽는다** — 셸 명령이면 guarded 한 번, 전체 재작성 파일이면 write 한 번, 그 외면 check 한 번.
실행 수단이 무엇이든 `state/` 쓰기는 이 셋 중 하나다.
**영속 셸에 보내는 명령은 판정까지 한 줄에 쓴다.**
영속 셸은 결과에 종료코드를 싣지 않는다.
다음 턴을 통째로 써서 `$?`를 읽으면 쓰기 하나가 4턴이 된다 — 2026-09-17 08:50 회차는 48호출 중 16(33%)이 종료코드 전용 턴이었다.
`if bash bin/guarded.sh deploy-approve-resolve "$TOKEN" run <명령…>; then echo OK; else echo FAIL; fi`처럼 **분기와 표식 출력을 같은 줄에** 넣는다.
전역 지침의 "`; echo $?`를 붙이지 마라"는 종료코드가 도구 결과에 그대로 실리는 단발 실행을 가리키며, 영속 셸에는 해당하지 않는다 — 여기서는 한 줄 안의 분기가 그 자리를 대신한다.
그 밖의 자리에서 `lock.sh check`를 부르지 않는다.
파일 생성·수정은 이 워크스페이스 안에서 한다.
`/tmp` 등 워크스페이스 밖 경로에 스크립트나 파일을 만들지 않는다.
**파일을 지우지 않는다** — `rm`은 승인 프롬프트를 띄우고 무인 회차에는 답할 사람이 없어 그 자리에서 멈춘다.
재사용하는 파일은 덮어쓴다.
**`git worktree`를 만들지 않고 빌드·테스트·패키지 매니저 명령(`mvn`·`gradle`·`npm`·`pytest` 등)을 실행하지 않는다.**
판정은 정적 읽기로만 한다 — 작업 사본을 만들면 정리가 필요해지고 그 정리가 다시 승인 프롬프트를 부른다.

Slack 접근은 Slack MCP 서버의 아래 도구만 쓰며 **도구 이름과 인자를 탐색하지 않는다** — 키워드로 찾으면 그 목록 전체가 컨텍스트에 남아 회차가 끝날 때까지 매 턴 다시 읽힌다. 호출 형식은 실행 프로바이더로 갈린다 — devin: `mcp_call_tool({server_name:"slack", tool_name:"<도구명>", arguments:{…}})`; claude.ai 커넥터: `mcp__claude_ai_Slack__<도구명>({…})`(커넥터 목록에 도구가 없으면 `ToolSearch("select:mcp__claude_ai_Slack__slack_read_channel,mcp__claude_ai_Slack__slack_read_thread,mcp__claude_ai_Slack__slack_send_message")`를 **한 번만** 부른다). 그 외 프로바이더에서는 그 환경의 MCP 호출 수단을 한 번 확인한 뒤 아래 이름과 인자를 그대로 쓴다.

- 채널 읽기 `slack_read_channel({channel_id, oldest, latest, limit, response_format:"detailed"})`
- 스레드 읽기 `slack_read_thread({channel_id, message_ts, oldest, limit, response_format:"detailed"})`
- 반응 확인 — 전용 도구가 없다. 위 두 읽기의 `response_format:"detailed"` 응답에 반응이 실리므로 그것으로 센다.
- 답글·DM `slack_send_message({channel_id, thread_ts, message})`

**인자 이름은 `channel_id`와 `message_ts`다.** `channel`·`ts`·`thread_id`로 부르면 필수 인자 누락으로 거부되고, 첫 Slack 수집 실패는 회차 중단 사유라 그 회차가 통째로 버려진다. 본문 필드는 `text`가 아니라 `message`다.

Slack Web API를 직접 호출하는 스크립트나 curl 명령을 만들지 않는다. 봇 ✅를 **다는** 것만 예외이며 그것은 `bin/deploy-approval-react.sh` 헬퍼가 담당한다.


**도구 이름을 모를 때만 탐색하고, 탐색은 이름만 뽑는다.** `ALL_TOOLS` 필터 결과를 도구 객체째로 출력하면 설명 필드까지 컨텍스트에 박혀 회차가 끝날 때까지 매 턴 다시 읽힌다(2026-09-15 실측: 한 번에 8,920토큰). `x.name`만 출력하고, 같은 회차에서 같은 탐색을 두 번 하지 않는다.

## 도구와 명령 형식

### ADO 호출 규율

`repos`·`devops` 호출에는 `--org <config 조직 URL>`을 포함한다. 인증 확인용 `account show`는 그 인자를 받지 않으므로 붙이지 않는다. 모든 az 호출은 **단일 명령**으로만 실행한다. `cd`·파이프·리다이렉션을 쓰지 않으며, 복합이 필요하면 워크스페이스 안에 `.sh`를 만들고 `bash <파일>`로 실행한다. **조회 다이어트**: `--project` 없는 조직 전체 `pr list`와 `--top 1000`류 전량 덤프를 금지하고, 모든 조회는 `--query`로 필요한 최소 필드만 뽑는다. 대형 JSON 덤프는 컨텍스트를 태워 회차를 상한까지 끌고 간다(2026-08-24 실관측).

### Jira 전이 형식

Jira 접근은 Atlassian MCP 서버의 아래 도구만 쓰며 **이름을 탐색하지 않는다** — 위 Slack 절의 프로바이더별 호출 형식을 그대로 쓰되 서버명은 `atlassian`, 커넥터 접두어는 `mcp__claude_ai_Atlassian__`다(커넥터 목록에 도구가 없으면 `ToolSearch("select:mcp__claude_ai_Atlassian__getJiraIssue,mcp__claude_ai_Atlassian__getJiraIssueRemoteIssueLinks,mcp__claude_ai_Atlassian__transitionJiraIssue")`를 한 번만 부른다). 조회는 `getJiraIssue`, 원격 링크는 `getJiraIssueRemoteIssueLinks`, 전이는 `transitionJiraIssue`다. Codex(`codex_apps`)에서는 회차 시작 시 `ALL_TOOLS`를 대소문자 무시 정규식 `/(?:^|_)(getjiraissue|getjiraissueremoteissuelinks|transitionjiraissue)$/i`로 한 번만 걸러 세 도구의 실제 이름을 얻고 그 이름으로 부른다. 실측 노출 이름은 `mcp__codex_apps__atlassian_rovo__legacy__atlassian_rovo_legacy_getjiraissue`처럼 소문자다(2026-10). 대소문자를 구분하는 이름 확인이나 `typeof` 단건 확인으로 부재를 결론 내리지 않는다 — camelCase만 찾던 회차들이 도구가 있는데도 OP-1447을 27회 연속 미처리로 넘겼다(2026-10-22).

Codex의 위 세 Jira 도구 결과는 원본 객체째 출력하지 않는다. `structuredContent`가 있으면 필드 전체를 `JSON.stringify`한 compact JSON 하나만, 없으면 `content`의 text만 출력한다. 단 `transitionJiraIssue`는 `isError===false`이고 응답에 이슈 key가 있을 때 성공으로 판정해 `{ok:true,key,status}`만 compact JSON으로 출력한다(`structuredContent`에서는 `issues.nodes[0]`, 없으면 content text의 반환 이슈에서 key와 `fields.status.name`을 읽는다). 오류·성공 불명은 위 전체 출력 규칙을 따른다.

조회(cloudId은 ROUTINE-CONFIG, `fields=["status"]`, `expand=transitions`)로 현재 상태와 가능한 전이를 함께 얻는다. 전이 목록 전용 도구를 따로 부르지 않는다. `to.name`이 목표 상태와 일치(공백 제거 비교)하는 전이가 있을 때만 위 전이 도구로 전환한다.

## 1. 회차 시작

`python3 bin/round.py begin deploy-approve-resolve`를 **한 번** 실행한다. dry-run 판정·락 획득·봇 토큰 확인·인증 확인·맥락 파일 읽기·worklist 폴드를 스크립트가 한 번에 처리해 JSON 한 줄로 돌려준다. 이것들을 따로 실행하지 않는다 — 각각이 도구 호출 한 턴이었고 할 일 없는 회차조차 그것만으로 8턴을 썼다.

받는 값은 `live`(dry-run 여부)·`token`·`runStartedEpoch`(토큰과 같은 값)·`botToken`·`auth`(`bin/az` 인증 확인 결과)·`context`(맥락 파일 `state/gate/context.deploy-approve-resolve.json` 내용, 없으면 null)·`worklist`(`deploy-approve-worklist.jsonl`의 활성 집합, 폴드 완료)다. `token` 값을 이 세션이 기억한다. **셸 변수에 담지 않는다** — Bash 호출끼리 셸 변수를 물려주지 않아 `$TOKEN`은 빈 값으로 전개되고, 그러면 `guarded.sh`가 exit 3으로 끝나 이 회차의 쓰기가 전부 막힌다. 아래 본문의 `"$TOKEN"`은 그 자리에 **토큰 값을 그대로 박으라는** 표기다.

`error`가 있으면(`lock-busy`·`bot-token-missing`·`auth-failed`·`fold-failed`) 그 사유로 **대상 특정 전 실패**를 보고하고 종료한다 — 스크립트가 락을 이미 풀었으므로 release를 부르지 않는다.

`live`가 false면 dry-run이다. 조회·분류·해소 검증은 라이브와 같게 수행하되 Slack 답글·봇 ✅·Jira 전이와 모든 worklist 쓰기는 수행 예정으로만 보고한다.

## 2. worklist 재확인·해소

ROUTINE-CONFIG를 읽어 해석한다(Jira·멱등 마커는 맥락에 없다). 봇 토큰·인증·worklist 폴드는 `begin`이 `botToken:ok`·`auth:ok`·`worklist`로 이미 마쳤다 — `test -s`·`account show`·`fold-worklist.py`를 다시 하지 않고, 토큰 값은 어디에도 출력·로그하지 않는다. ROUTINE-CONFIG 해석과 상태 루트 접근 실패는 `python3 bin/round.py finish deploy-approve-resolve "$TOKEN"`를 **`--commit` 없이 한 번 실행한 뒤** 대상 특정 전 실패로 회차를 중단한다.

활성 집합은 `begin` JSON의 `worklist`다. 빈 집합은 성공한 no-op이며 `python3 bin/round.py finish deploy-approve-resolve "$TOKEN"`를 **`--commit` 없이 한 번 실행하고 종료한다**. 각 항목을 순차 처리한다. `heldAt`이 7일을 초과하면 라이브에서 lock check 뒤 `ts`, `op:"close"`, `key`, `by:"deploy-approve-resolve"`, `reason:"expired"`를 append한다. 스레드 답글은 남기지 않는다.

보류 3종(`review-issue`, `pr-not-found`, `jira-transition`)은 Slack 스레드를 읽어 `lastCheckedTs` 이후 새 답글을 확인한다. 내 멱등 마커 답글과 봇 메시지는 해소 근거에서 제외한다. 첫 Slack 읽기 실패는 회차 중단 사유다 — `python3 bin/round.py finish deploy-approve-resolve "$TOKEN"`를 **`--commit` 없이 한 번 실행한 뒤** 중단하고, 보고에는 이미 처리한 항목과 실패한 항목을 나눠 적는다. 새 답글이 없어도, 라이브에서는 lock check 뒤 가장 최신 답글 TS까지 `op:"update"` 이벤트로 `lastCheckedTs`를 전진시킨다. 내 답글이 최신이어도 그 TS를 쓴다. 항목은 활성으로 유지한다.

새 답글이 있어 검증 대상이 처음 확정되면 `~/work/harnie/skills/comment-resolve/SKILL.md`를 읽고 해소 검증 기준으로 적용한다. 승인 재판정이 필요한 시점에는 `~/work/harnie/skills/deploy-approval/SKILL.md`도 읽고 그 시점의 기준을 적용한다. 두 문서의 본문은 복사하지 않는다.

- `pr-not-found`는 원 요청과 답글의 PR URL·번호, 모든 Jira KEY를 대상으로 intake와 같은 PR 수집·PR별 판정·PR 간 상충 판정을 한다. 직접 URL이 있어도 모든 KEY의 원격 링크·본문·개발 패널 PR을 합치고, 0건일 때만 comment 재조회·ADO 후보 검색 순으로 간다. 각 PR을 확정해 abandoned 제외·중복 제거한다. 아래 공통 규칙을 적용하며 PR 0건이거나 차단이 남으면 미해소다.
- `review-issue`는 `prs`가 있으면 그 PR 전부, 없으면 기존 `project`·`repository`·`prId`를 재확인한다. 수정 주장을 그대로 믿지 않고 `bash bin/az deploy-approve-resolve`와 필요한 읽기 전용 로컬 commit으로 지적 파일·문제가 신규 커밋에서 실제로 다뤄졌는지 확인한다. 해명은 comment-resolve 기준으로 판정한다. PR별 판정을 모두 통과하면 PR 간 상충도 다시 보며, 상충 보류는 상충한 PR들의 새 커밋에서 기존 상충이 해소됐는지를 같은 기준으로 확인한다. 확신이 낮으면 미해소다.
- `jira-transition`은 Jira 상태와 가능한 전이를 다시 조회한다. 연결 티켓 전부가 목표 상태 또는 그 이후이면 해소다. 전이가 가능해졌으면 전이를 시도해 해소 여부를 판정한다.

위 두 PR 재판정은 `prompts/deploy-approve-intake.md` §2를 한 번 읽어 수집·`prior-review.py` 요약 재사용·미해결 `issue:`·새 커밋·직접 판정·PR 간 상충·hold 필드 규칙을 그대로 따른다(회차 시작·종료는 실행하지 않고 ADO 호출은 `deploy-approve-resolve`로 한다). PR 간 판정은 2개 이상 모두 통과했을 때만 하며, 요약 재사용 PR도 다른 서버가 소비하는 부분의 PR 전체 diff와 상대 PR 소스 commit의 소비 지점을 읽는다. 단, 순서 의존 (c) 보류는 새 커밋이나 원 메시지 수정 없이도 `lastCheckedTs` 이후 본인·봇 외 스레드 답글이 배포 순서를 명시하고 그 순서가 같은 기준으로 안전하면 해소한다. 없거나 위험하면 안전한 순서를 답글에 적고 `review-issue`로 유지한다. commit 부재는 같은 fetch-queue 규칙으로 해당 항목을 미처리로 남기며 ✅를 달지 않는다. 재판정에 따른 hold update에도 수집 PR 전부의 `prs`와 기존 단수 필드를 보존·갱신하고, 상충 PR 쌍·내용을 `holdReason`과 답글에 적는다.

해소된 항목은 라이브에서 lock check 뒤 `sh bin/deploy-approval-react.sh <deploy_approval_channel> <messageTs>`로 봇 ✅를 단다. `slack_add_reaction`은 사용하지 않는다. 채널을 재조회해 ✅ 총수를 센다. N이 2 미만이면 멱등 마커를 포함한 사유 답글을 한 번 남긴 뒤 `reason:"reaction-quorum-not-met"`으로 close한다.

N이 2 이상이면 모든 연결 Jira 티켓을 목표 상태 `배포승인`과 비교한다. 상태명·전이명 비교는 공백을 제거한다. 이미 목표 상태 또는 그 이후·완료인 티켓은 성공이고, 목표 전이가 있으면 lock check 뒤 전이한다. 전이가 없거나 일부 전이가 실패하면 close하지 않는다. lock check 뒤 `op:"update"`로 `holdType:"jira-transition"`, 갱신한 `holdReason`, `lastCheckedTs`를 append해 다음 회차 대상에 남긴다. 모든 연결 티켓이 목표 상태에 도달했을 때만 lock check 뒤 해소 근거 한 줄과 멱등 마커를 스레드에 남기고 `reason:"approved"`으로 close한다.

미해소면 라이브에서 lock check 뒤 사유와 멱등 마커를 스레드에 한 번 남긴다. 이어 lock check 뒤 `op:"update"`로 새 `holdReason`과 이번에 확인한 최신 답글 TS의 `lastCheckedTs`를 append하고 항목을 유지한다. 답글·ADO 조회·로컬 읽기·Jira 전이·worklist 기록 실패는 해당 항목만 미처리로 남기고 다음 항목을 계속 처리한다.

## 3. 상태 기록

close와 update 이벤트는 각 항목 처리 직후에만 append한다. 모든 항목이 성공했을 때만 회차 성공이다. dry-run에서는 close·update·외부 효과 예정만 보고한다.

## 4. 회차 종료와 보고

정상 경로에서는 `python3 bin/round.py finish deploy-approve-resolve "$TOKEN"`를 **한 번** 실행한다. 스크립트가 lock check → 락 해제를 한 번에 처리한다. `error`가 `lock-lost`면 소유권을 잃은 것이라 아무것도 하지 않았다는 뜻이다. `lock.sh release`·`precheck.py commit`을 따로 부르지 않는다.

한국어 보고에는 활성 항목 수, `begin`이 `worklistSkipped`를 돌려줬으면 건너뛴 깨진 줄 수, 만료 close, 새 답글 없음과 `lastCheckedTs` 전진, holdType별 해소·미해소, 봇 ✅·반응 수·Jira 전이, update·close 사유, 미처리 항목과 사유, dry-run 수행 예정 목록을 포함한다. 크리덴셜은 보고하지 않는다.
