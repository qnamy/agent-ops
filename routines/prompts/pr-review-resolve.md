<!-- sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다. 원본은 비공개 워크스페이스에서 운영 중. -->
# pr-review-resolve

이 프롬프트 본문은 automation 트리거가 이미 줬다. **이 파일을 다시 읽지 않고, 자기 지시를 `rg`·`grep`으로 검색하지 않는다.** 재읽기 한 번과 자기 검색 한 번이 회차 도구 출력의 54%였다(2026-09-16 실측 7,659토큰). **개인 메모리(`~/.codex/memories/`)도 읽지 않는다** — 2026-09-17 07:20 회차가 첫 턴에 그것을 `rg`로 28,337자 올려 11턴 내내 다시 실었다. 무인 회차의 판단은 이 프롬프트와 맥락 파일의 `config`만으로 한다.

이 실행은 `state/pr-review-worklist.jsonl`의 활성 항목 중 Active PR에서 내가 루트로 시작한 active 리뷰 스레드를 검증해 해소한다. 신규 리뷰 댓글은 만들지 않는다 — **예외는 아래 「미리뷰 복구」 하나**이고, 그 경우에만 `pr-review-intake`와 같은 규칙으로 새 리뷰 스레드를 만든다. 조직·사용자·ADO 댓글 면책 문구는 `state/gate/context.pr-review-resolve.json`의 `config`에서 읽는다 — precheck가 `ROUTINE-CONFIG.md`를 이미 파싱해 실어 둔다. **`config`가 없을 때만 `~/work/ROUTINE-CONFIG.md`를 직접 읽는다.** 좌표값과 GUID를 하드코딩하지 않는다. `~/work/.legacy-routine-state/`와 `~/work/legacy-routines/`는 쓰지 않는다. 크리덴셜 값은 출력·기록하지 않는다.

ADO는 모두 `bash bin/az pr-review-resolve ...`로 호출한다. **이 세션은 `git` 명령을 실행하지 않는다.** 코드 판정은 PR별 세션이 하고 이 세션은 그 결과만 쓴다. diff가 이 컨텍스트에 들어오면 회차가 끝날 때까지 매 턴 다시 읽힌다. **쓰기 직전의 lock check는 두 형태다.** 셸 명령인 쓰기(`bin/az`의 POST·PATCH·`set-vote`, 원장·worklist append, `state/deploy-approval-react.sh`, `pr-session.sh close`, `mark.py`)는 `bash bin/guarded.sh pr-review-resolve "$TOKEN" run <명령…>` 또는 `bash bin/guarded.sh pr-review-resolve "$TOKEN" append <파일> '<한 줄>'`로 실행한다 — 스크립트가 check를 먼저 하고 실패하면 명령을 실행하지 않고 exit 3으로 끝나며, 그때는 소유권을 잃은 것이니 그 자리에서 종료하고 상태 기록·commit·release를 시도하지 않는다. 셸 명령이 아닌 쓰기 — MCP 도구(Slack·Jira·Confluence)와 파일 도구로 덮어쓰는 `state/ask.*.md`·`state/ado-body.*.json` 같은 모든 `state/` 파일 — 는 직전에 `bash bin/lock.sh check pr-review-resolve "$TOKEN"`을 따로 한다. **아래 본문의 'lock check 뒤'는 이 규칙대로 읽는다** — 셸 명령이면 guarded 한 번, 그 외면 check 한 번. 실행 수단이 무엇이든 `state/` 쓰기는 이 둘 중 하나다. **영속 셸에 보내는 명령은 판정까지 한 줄에 쓴다.** 영속 셸은 결과에 종료코드를 싣지 않는다. 다음 턴을 통째로 써서 `$?`를 읽으면 쓰기 하나가 4턴이 된다 — 2026-09-17 08:50 회차는 48호출 중 16(33%)이 종료코드 전용 턴이었다. `if bash bin/guarded.sh pr-review-resolve "$TOKEN" run <명령…>; then print -r -- OK; else print -r -- FAIL; fi`처럼 **분기와 표식 출력을 같은 줄에** 넣는다. 전역 지침의 "`; echo $?`를 붙이지 마라"는 종료코드가 도구 결과에 그대로 실리는 단발 실행을 가리키며, 영속 셸에는 해당하지 않는다 — 여기서는 한 줄 안의 분기가 그 자리를 대신한다. 그 밖의 자리에서 `lock.sh check`를 부르지 않는다.


**도구 이름을 모를 때만 탐색하고, 탐색은 이름만 뽑는다.** `ALL_TOOLS` 필터 결과를 도구 객체째로 출력하면 설명 필드까지 컨텍스트에 박혀 회차가 끝날 때까지 매 턴 다시 읽힌다(2026-09-15 실측: 한 번에 8,920토큰). `x.name`만 출력하고, 같은 회차에서 같은 탐색을 두 번 하지 않는다.

## 도구와 명령 형식

### ADO 호출 규율

`repos`·`devops` 호출에는 `--org <config 조직 URL>`을 포함한다. 인증 확인용 `account show`는 그 인자를 받지 않으므로 붙이지 않는다. 모든 az 호출은 **단일 명령**으로만 실행한다. `cd`·파이프·리다이렉션을 쓰지 않으며, 복합이 필요하면 워크스페이스 안에 `.sh`를 만들고 `bash <파일>`로 실행한다. **조회 다이어트**: `--project` 없는 조직 전체 `pr list`와 `--top 1000`류 전량 덤프를 금지하고, 모든 조회는 `--query`로 필요한 최소 필드만 뽑는다. 대형 JSON 덤프는 컨텍스트를 태워 회차를 상한까지 끌고 간다(2026-08-24 실관측).

- **스레드 목록**: `bash bin/az pr-review-resolve devops invoke --area git --resource pullRequestThreads --route-parameters project={project} repositoryId={repo} pullRequestId={PR_ID} --org <config 조직 URL> --api-version 7.1 -o json` → `value[]`(각 `comments[]`·`status`·`threadContext.filePath`·`comments[].author.uniqueName`·`comments[].publishedDate`).
- **대댓글**: 본문 JSON을 `state/ado-body.pr-review-resolve.json`에 쓴다 — `{"content":"...","parentCommentId":{원댓글ID},"commentType":"text"}`를 넣고 `bash bin/az pr-review-resolve devops invoke --area git --resource pullRequestThreadComments --route-parameters project={project} repositoryId={repo} pullRequestId={PR_ID} threadId={threadId} --org <config 조직 URL> --api-version 7.1 --http-method POST --in-file state/ado-body.pr-review-resolve.json`. 매번 덮어쓰고 지우지 않는다.
- **스레드 resolve**: `state/ado-body.pr-review-resolve.json`에 `{"status":"fixed"}`를 쓴 후 `bash bin/az pr-review-resolve devops invoke --area git --resource pullRequestThreads --route-parameters project={project} repositoryId={repo} pullRequestId={PR_ID} threadId={threadId} --org <config 조직 URL> --api-version 7.1 --http-method PATCH --in-file state/ado-body.pr-review-resolve.json`.
- **투표**: `bash bin/az pr-review-resolve repos pr set-vote --id {PR_ID} --vote {approve|approve-with-suggestions|wait-for-author|reject|reset} --org <config 조직 URL>`.

## 1. 회차 시작

`bash bin/round.py begin pr-review-resolve`를 **한 번** 실행한다. dry-run 판정·락 획득·게이트 스냅샷·인증 확인·맥락 파일 읽기·worklist 폴드를 스크립트가 한 번에 처리해 JSON 한 줄로 돌려준다. 이것들을 따로 실행하지 않는다 — 각각이 도구 호출 한 턴이었고 할 일 없는 회차조차 그것만으로 8턴을 썼다.

받는 값은 `live`(dry-run 여부)·`token`·`runStartedEpoch`(토큰과 같은 값)·`snapshot`(pending을 snapshot으로 복사했음)·`auth`(`bin/az` 인증 확인 결과)·`context`(맥락 파일 `state/gate/context.pr-review-resolve.json` 내용, 없으면 null)·`worklist`(`pr-review-worklist.jsonl`의 활성 집합, 폴드 완료)다. `token`을 `TOKEN`으로 보관한다.

`error`가 있으면(`lock-busy`·`no-pending`·`auth-failed`·`fold-failed`) 그 사유로 **대상 특정 전 실패**를 보고하고 종료한다 — 스크립트가 락을 이미 풀었으므로 release를 부르지 않는다.

`live`가 false면 dry-run이다. 조회·검증은 같게 수행하고 ADO 댓글·resolve·투표와 모든 state 쓰기·commit은 수행 예정으로만 보고한다.

## 2. 일감·검증·해소

`config`는 `begin` JSON의 `context.config`, 활성 집합은 `begin` JSON의 `worklist`다. 인증은 `begin`이 `auth:ok`로 이미 확인했다 — `account show`도 `fold-worklist.py`도 다시 부르지 않는다. 빈 `worklist`는 성공한 no-op이다.

각 worklist PR을 순차 처리한다.

PR의 `status`·`srcCommit`·`tgtCommit`·`createdById`(작성자 멘션용)는 `begin` JSON의 `context.prs`에서 읽는다 — precheck가 게이트 판정에 이미 조회한 손실 없는 값이므로 `repos pr show`를 다시 부르지 않는다(종전엔 작성자 GUID 때문에 18세션에 26회 불렀다). 항목이 없으면 그 PR만 직접 조회한다. **스레드는 맥락에 없다. `pullRequestThreads`로 직접 조회한다.** 게이트 digest의 스레드 요약은 해시용 축약이라 댓글 원문도 루트 작성자도 접두어도 없어 검증 입력이 되지 못한다. 이 조회 또는 필요한 로컬 commit 읽기 실패는 해당 PR만 미처리로 남기고 다음 PR로 간다.

- completed(병합)는 이 회차에서 끝낸다. 내 스레드 중 `status`가 `active`인 것마다 **대댓글 1회**로 병합 전에 다뤄지지 않았음을 남기고, 같은 스레드의 `status`를 `closed`로 바꾼다. `fixed`가 아니다 — 해결된 것이 아니라 더 볼 수 없게 된 것이다. 후속 PR을 요청하지 않는다. 각 스레드마다 lock check 뒤 `state/code-quality-list.jsonl`에 `outcome:"merged-unresolved"`로 append한다(`occId`·필드 구성은 아래 해소 경로와 같다). 이 원장은 `code-convention-digest`가 읽어, 같은 지적이 반복해 미해결로 병합되면 lint·CI 승격 후보로 올린다. 그 뒤 lock check 뒤 worklist에 `op:"close"`, `reason:"merged"`, `by:"pr-review-resolve"`를 append하고 lock check 뒤 `bash bin/pr-session.sh close "<key>"`로 세션을 닫는다. `issue:`든 `nit:`든 같게 처리한다.
- abandoned는 라이브에서 lock check 뒤 `pr-review-worklist.jsonl`에 `op:"close"`, `reason:"abandoned"`, 해당 key와 `by:"pr-review-resolve"`를 append한다.
- active는 status가 `active`이고 첫 댓글 작성자가 `config`의 `user`인 스레드를 추린다. `commentType`이 `system`인 스레드(투표·푸시 알림)는 내 이름으로 생성돼도 리뷰 스레드가 아니므로 제외한다.

### 미리뷰 복구

**내 `text` 스레드가 0건인 active PR은 아직 리뷰되지 않은 것이므로 이 회차에서 리뷰한다.** 착수 투표만 찍히고 코드 판정이 실패했거나, Slack 창이 지나가 `pr-review-intake`가 더는 집지 않는 PR이 여기 해당한다(2026-09-16 PR {PR} 실관측 — worklist에 남았지만 intake는 창 밖이라 건너뛰고 resolve는 검증할 스레드가 없어 아무것도 하지 않았다).

이 PR은 **아래 해소 분기를 타지 않는다.** 대신 `pr-review-intake`의 「2. 수집·판정·리뷰」를 그대로 수행한다.

1. `bash bin/pr-session.sh ensure "<key>"`로 세션을 얻는다. 실패하면 그 PR을 미처리로 남긴다.
2. `state/ask.pr-review-resolve.md`에 **intake 「2. 수집·판정·리뷰」의 리뷰 지시**를 쓴다 — 리뷰 기준·범위·금지와 `{"findings":[{"prefix","filePath","line","content"}],"summary"}` 결과 형식이다. 해소 검증 지시(`threads[]`)를 쓰지 않는다.
3. `bash bin/pr-session.sh ask "<key>" state/ask.pr-review-resolve.md`. `ok <경로>`가 아니면 미처리로 남긴다.
4. 받은 `findings`로 ADO 스레드 작성·투표·`review-findings.jsonl`·`pr-review-summary.jsonl`을 **intake와 같은 규칙으로** 처리한다.
5. `approve` 또는 `approve-with-suggestions`가 성공했으면 intake와 같이 lock check 뒤 worklist를 `reason:"no-findings"`·`"nit-only"`로 close하고 `bash bin/pr-session.sh close "<key>"`를 실행한다. 닫지 않으면 지적 0건 PR이 매 회차 다시 리뷰되고, nit-only는 열린 nit 때문에 아래 close 조건도 통과하지 못해 영구히 남는다.

그 스레드를 최신 댓글 작성자로 분류한다.

- 경로 A: 최신 댓글이 나 이외의 사람이다. 답변을 검증한다. 이 경로는 반드시 resolve 또는 근거 대댓글 중 하나로 끝낸다.
- 경로 B: 최신 댓글이 나다. 내 마지막 댓글 이후 `The reference refs/pull/<id>/source was updated.` 시스템 스레드 publishedDate가 있으면 대상 후보다. **변경 파일 판별은 이 세션이 하지 않는다** — 후보 스레드의 `threadContext.filePath`를 세션 지시에 함께 넘겨 세션이 source에서 판별하게 한다. `issue:`는 코드만으로 판정할 수 있고, `discuss:`는 자동 해소하지 않는다. 구 접두어 없는 댓글만 내용으로 판정한다. 명확히 해소된 경우만 처리하고 애매·부분 해소·미해소는 아무 동작도 하지 않는다.

**코드 검증은 그 PR의 세션에서 한다. 이 세션은 `git` 명령을 실행하지 않는다.** `bash bin/pr-session.sh ensure "<project>/<repository>#<pullRequestId>"`로 세션을 얻는다 — `pr-review-intake`가 그 PR을 리뷰할 때 연 세션이 살아 있으면 그대로 재사용된다. 그 세션은 이미 이 PR의 diff와 리뷰 기준을 컨텍스트에 갖고 있어 새로 읽지 않는다.

`state/ask.pr-review-resolve.md`에 지시를 쓴다. project·repository·PR id·threadId·source commit·target commit·맥락 `prs` 항목의 `numstat`·`patch` 경로·지적 원문·작성자 답변 원문과 아래를 담는다.

- `~/work/harnie/skills/pr-review/SKILL.md`와 `~/work/harnie/skills/comment-resolve/SKILL.md`를 읽고 그 기준을 적용한다. 내용을 복사하지 않는다.
- 답변의 코드 수정·PR description·후속 변경·설명이 실제 지적을 해소하는지 source commit 기준으로 검증한다. **PR 소속 커밋의 변경은 precheck가 떨군 `numstat`·`patch`에 있다** — 워커에게 `git diff`를 직접 부르지 말라고 쓰고, 읽는 방법은 `pr-review-intake` 「2. 수집·판정·리뷰」와 같게 지시한다(`numstat` 먼저, `patch`는 필요한 구간만). 맥락에 그 경로가 없을 때만 워커가 직접 범위를 잡는다. `git --no-optional-locks -C ~/work/<repository>` 읽기 명령만 쓰고 fetch·clone·working tree 접근은 금지한다.
- ADO·Slack에 접근하지 않는다. 대댓글·resolve·재투표·원장 기록은 오케스트레이터가 한다.
- 결과를 **`{{RESULT_PATH}}`** 경로에 JSON 하나로 쓴다 — **이 문자열을 지시에 반드시 넣는다** — `ask`가 보내는 시점에 실제 경로로 치환한다. 빠뜨리면 세션이 결과를 어디에 쓸지 알 수 없어 그 PR이 timeout된다. 세션이 경로를 스스로 조회하지 않는다. `{"threads":[{"threadId":N,"verdict":"resolved|unresolved|unclear","changedFile":true|false,"evidence":"근거 본문","summary":"원장에 남길 한 줄"}]}` 형식이고 `evidence`에 멘션·면책을 넣지 않는다.

`bash bin/pr-session.sh ask "<key>" state/ask.pr-review-resolve.md`가 출력이 `ok <경로>`로 시작하지 않으면 그 PR을 미처리로 남기고 다음 PR로 간다 — **이 세션이 대신 검증하지 않는다.** 성공하면 그 출력에서 경로를 떼어 그 파일의 JSON을 읽고, `threads[]`의 내용만 스레드 판정에 쓴다. 경로나 JSON을 읽지 못하면 그 PR을 미처리로 남긴다. `verdict`가 `resolved`일 때만 해소로 처리한다. `unclear`는 애매로 보아 경로 A는 확인 요청 대댓글, 경로 B는 무동작이다.

**투표를 바꾼 PR은 그 자리에서 `state/pr-review-summary.jsonl`에 갱신 한 줄을 append한다.** lock check 뒤 `ts`·`key`·`srcCommit`(지금 판정한 것)·`prefixes`(**지금 열려 있는** 내 스레드의 접두어만)·`summary`·`vote`를 담는다. **이 append 실패는 그 PR의 실패다** — 미처리로 남기고 게이트를 commit하지 않는다. 게이트가 먼저 commit되면 다음 회차가 같은 digest를 SKIP하고, 해소된 `issue:`가 담긴 stale 요약이 가장 늦은 줄로 남아 배포승인을 영구히 막는다.

검증이 통과한 스레드는 먼저 라이브에서 lock check 뒤 `state/code-quality-list.jsonl`에 append한다. `occId`는 `"<project>/<repository>#<pullRequestId>/<threadId>"`이고, `ts`, `summary`, `prefix`, project/repository/PR/thread/filePath, `outcome:"resolved"`, `by:"pr-review-resolve"`를 포함한다. 이 원장 append가 실패하면 대댓글·resolve·재투표를 하지 않고 해당 PR을 미처리로 남긴다.

원장 저장 후에만 lock check 뒤 PR 작성자 `@<GUID>` 리터럴 멘션, 검증 근거, `config`의 `disclaimer` 두 줄을 포함한 대댓글을 POST한다. 이어 lock check 뒤 스레드를 `fixed`로 resolve한다. 경로 A의 검증 실패·애매함에는 lock check 뒤 같은 형식의 확인 요청 또는 유지 사유 대댓글을 남기되 스레드는 active로 둔다. 경로 B의 불확실한 결과에는 대댓글을 추가하지 않는다.

**재투표는 내 `issue:`·`discuss:` 스레드가 전부 resolve로 닫힌 뒤에만 한다.** 하나라도 열려 있으면 투표를 바꾸지 않는다. 남이 고치고 남이 resolve해도 마찬가지로 이 조건만 본다.

**닫혔는지는 이번 회차의 검증 대상 수로 판단하지 않는다.** 경로 A·B의 대상이 0건인 것은 "이번에 검증할 것이 없다"는 뜻이지 "닫혔다"는 뜻이 아니다. 방금 내가 단 지적은 최신 댓글이 나라서 경로 A에도 B에도 안 걸리지만 열려 있다. 이 둘을 섞으면 지적이 열린 PR에 `approve`를 찍는다.

**ADO 스레드 상태로 다시 조회해 센다.**

- 내가 루트인 `status: active` 스레드(`commentType: system` 제외)
- 타인 루트의 `status: active` 스레드에 단 내 `issue:`/`discuss:` 답글

이 집합의 접두어로 투표를 정한다. 접두어는 그 스레드에 있는 **내 댓글**의 `issue:`·`discuss:`·`nit:`에서 읽는다 — 내가 루트면 첫 댓글이 내 것이고, 타인 루트면 내 답글이다. **첫 댓글에서 읽으면 안 된다**: 타인의 `nit:` 스레드에 내 `issue:` 답글이 열려 있을 때 `nit`만 남은 것으로 잘못 세어 승인으로 올라간다.

- 집합이 비어 있고 **그 PR에 내 `text` 스레드가 하나라도 있었으면** `approve`. `commentType`이 `system`인 스레드는 내 이름으로 생성돼도 리뷰가 아니다 — 착수 투표가 `<내 표시 이름> voted -5`를 만든다(2026-09-16 PR {PR}). 내 `text` 스레드가 아예 없으면 이 PR을 리뷰한 적이 없거나 리뷰가 중간에 실패한 것이므로 **투표를 건드리지 않고 미검토로 보고한다** — 비어 있음을 지적 없음으로 읽으면 검토되지 않은 PR이 승인된다
- 열린 것이 `nit:`뿐이면 `approve-with-suggestions`
- `issue:`·`discuss:`가 하나라도 열려 있으면 **투표를 바꾸지 않는다**

라이브면 lock check 뒤 투표한다. 비어 있거나 `nit:`뿐이라는 판정은 스레드를 실제로 조회해 확인했을 때만 성립한다. 같은 값으로 다시 투표해도 결과가 같으므로 현재 투표를 조회하지 않는다.

active PR에 **위 미해결 집합이 비어 있고 그 PR에 내 `text` 스레드가 하나라도 있었을 때만** 라이브에서 close(`reason:"all-threads-resolved"`)한다. 내 `text` 스레드가 아예 없으면 투표도 close도 하지 않고 미검토로 보고한다 — 착수 선등록 뒤 판정이 실패한 항목이 여기 해당하고, 닫으면 검토되지 않은 PR이 추적에서 빠진다. 경로 A·B의 처리 건수가 0인 것은 close 근거가 아니다. **close 직전에 위 재투표 판정을 반드시 먼저 수행한다.** 타인 루트 스레드에 내 미해결 `issue:`/`discuss:` 답글이 남아 있으면 close하지 않고 수동 확인 필요로 보고한다. close append 직전 lock check를 한다.

PR 하나의 조회·검증·원장·ADO 쓰기·투표·close 실패는 그 PR만 미처리로 남기고 다음 PR로 넘어간다. 원장 → 근거 대댓글 → resolve → 재투표 순서는 바꾸지 않는다.

## 3. 상태 기록

원장과 worklist close는 2단계에서 각각의 대상 직후에만 append한다. 모든 대상이 성공했을 때만 회차 성공이다. dry-run에서는 각 append 예정과 ADO 수행 예정만 기록한다.

## 4. 회차 종료와 보고

정상 경로에서는 `bash bin/round.py finish pr-review-resolve "$TOKEN" [--commit] --sweep`를 **한 번** 실행한다. 스크립트가 lock check → 게이트 commit → 세션 sweep → 락 해제를 한 번에 처리한다. `--commit`은 모든 대상이 성공했고 라이브일 때만 붙인다. 대상 하나라도 미처리이거나 dry-run이면 commit하지 않는다. `--sweep`은 **인자 없이** 붙인다 — 살릴 세션은 finish가 **그 시점의** worklist를 다시 폴드해 정한다. 세션이 회차 초반의 활성 집합을 넘기면 이 회차에 close한 PR의 세션이 '살릴 것'이 되어 누수된다(2026-09-16 17:01 회차가 방금 abandoned로 닫은 #19110의 세션을 그렇게 15시간 살려 뒀다). 활성 집합이 비어도 붙인다. `error`가 `lock-lost`면 소유권을 잃은 것이라 아무것도 하지 않았다는 뜻이다. `lock.sh release`·`precheck.py commit`·`pr-session.sh sweep`을 따로 부르지 않는다.

한국어 보고에는 worklist 항목 수, active·completed·abandoned 분류, 경로 A/B별 resolve·대댓글·무동작, 재투표, 원장/close append, 미처리 PR과 사유, commit 여부와 dry-run 수행 예정 목록을 포함한다.
