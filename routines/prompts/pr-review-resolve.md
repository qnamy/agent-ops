<!-- sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다. 원본은 비공개 워크스페이스에서 운영 중. -->
# pr-review-resolve

이 파일을 지금 읽은 것이 정상이다 — 트리거는 경로만 준다. **이 파일은 한 번만 읽고 다시 읽지 않고, 자기 지시를 `rg`·`grep`으로 검색하지 않는다.** 재읽기 한 번과 자기 검색 한 번이 회차 도구 출력의 54%였다(2026-09-16 실측 7,659토큰). **개인 메모리(`~/.devin/`·`~/.codex/memories/`)도 읽지 않는다** — 2026-09-17 07:20 회차가 첫 턴에 그것을 `rg`로 28,337자 올려 11턴 내내 다시 실었다. 무인 회차의 판단은 이 프롬프트와 맥락 파일의 `config`만으로 한다.

이 실행은 `state/pr-review-worklist.jsonl`의 활성 항목 중 Active PR에서 내 열린 지적(내가 루트인 열린 리뷰 스레드와 타인 루트 스레드의 내 `issue:`·`discuss:` 답글)을 검증해 해소한다. 신규 리뷰 댓글은 만들지 않는다 — **예외는 아래 「미리뷰 복구」 하나**이고, 그 경우에만 `pr-review-intake`와 같은 규칙으로 새 리뷰 스레드를 만든다. 조직·사용자·ADO 댓글 면책 문구는 `state/gate/context.pr-review-resolve.json`의 `config`에서 읽는다 — precheck가 `ROUTINE-CONFIG.md`를 이미 파싱해 실어 둔다. **`config`가 없을 때만 `~/work/ROUTINE-CONFIG.md`를 직접 읽는다.** 좌표값과 GUID를 하드코딩하지 않는다. `~/work/.legacy-routine-state/`와 `~/work/legacy-routines/`는 쓰지 않는다. 크리덴셜 값은 출력·기록하지 않는다.

ADO는 모두 `bash bin/az pr-review-resolve ...`로 호출한다. 레포 접근은 `git --no-optional-locks -C ~/work/<repository>` 읽기 명령으로 제한하고 fetch·clone·working tree 접근을 하지 않는다. **쓰기 직전의 lock check는 세 형태다.**
셸 명령인 쓰기(`bin/az`의 POST·PATCH·`set-vote`, 원장·worklist append, `bin/deploy-approval-react.sh`, `mark.py`)는 `bash bin/guarded.sh pr-review-resolve "$TOKEN" run <명령…>` 또는 `bash bin/guarded.sh pr-review-resolve "$TOKEN" append <파일> '<한 줄>'`로 실행한다 — 스크립트가 check를 먼저 하고 실패하면 명령을 실행하지 않고 exit 3으로 끝나며, 그때는 소유권을 잃은 것이니 그 자리에서 종료하고 상태 기록·commit·release를 시도하지 않는다.
매번 전체를 다시 쓰는 `state/` 파일(`state/ado-body.*.json`)은 `bash bin/guarded.sh pr-review-resolve "$TOKEN" write <파일> <<'__BODY__'`에 이어 JSON 한 벌과 `__BODY__`를 넘기는 한 호출로 쓴다 — check가 그 안에 들어 있으므로 직전 check를 따로 하지 않고, 그 파일을 이 호출 바깥에서 리다이렉션이나 파일 도구로 먼저 열지도 않는다.
그 외 셸 명령이 아닌 쓰기 — MCP 도구(Slack·Jira·Confluence) 호출과 파일 도구의 부분 수정 — 는 직전에 `bash bin/lock.sh check pr-review-resolve "$TOKEN"`을 따로 한다.
**아래 본문의 'lock check 뒤'는 이 규칙대로 읽는다** — 셸 명령이면 guarded 한 번, 전체 재작성 파일이면 write 한 번, 그 외면 check 한 번.
실행 수단이 무엇이든 `state/` 쓰기는 이 셋 중 하나다.
**영속 셸에 보내는 명령은 판정까지 한 줄에 쓴다.**
영속 셸은 결과에 종료코드를 싣지 않는다.
다음 턴을 통째로 써서 `$?`를 읽으면 쓰기 하나가 4턴이 된다 — 2026-09-17 08:50 회차는 48호출 중 16(33%)이 종료코드 전용 턴이었다.
`if bash bin/guarded.sh pr-review-resolve "$TOKEN" run <명령…>; then echo OK; else echo FAIL; fi`처럼 **분기와 표식 출력을 같은 줄에** 넣는다.
전역 지침의 "`; echo $?`를 붙이지 마라"는 종료코드가 도구 결과에 그대로 실리는 단발 실행을 가리키며, 영속 셸에는 해당하지 않는다 — 여기서는 한 줄 안의 분기가 그 자리를 대신한다.
그 밖의 자리에서 `lock.sh check`를 부르지 않는다.


**도구 이름을 모를 때만 탐색하고, 탐색은 이름만 뽑는다.** `ALL_TOOLS` 필터 결과를 도구 객체째로 출력하면 설명 필드까지 컨텍스트에 박혀 회차가 끝날 때까지 매 턴 다시 읽힌다(2026-09-15 실측: 한 번에 8,920토큰). `x.name`만 출력하고, 같은 회차에서 같은 탐색을 두 번 하지 않는다.

## 도구와 명령 형식

### ADO 호출 규율

`repos`·`devops` 호출에는 `--org <config 조직 URL>`을 포함한다. 인증 확인용 `account show`는 그 인자를 받지 않으므로 붙이지 않는다. 모든 az 호출은 **단일 명령**으로만 실행한다. `cd`·파이프·리다이렉션을 쓰지 않으며, 복합이 필요하면 워크스페이스 안에 `.sh`를 만들고 `bash <파일>`로 실행한다. **조회 다이어트**: `--project` 없는 조직 전체 `pr list`와 `--top 1000`류 전량 덤프를 금지하고, 모든 조회는 `--query`로 필요한 최소 필드만 뽑는다. 대형 JSON 덤프는 컨텍스트를 태워 회차를 상한까지 끌고 간다(2026-08-24 실관측).

- **스레드 목록**: `bash bin/az pr-review-resolve devops invoke --area git --resource pullRequestThreads --route-parameters project={project} repositoryId={repo} pullRequestId={PR_ID} --org <config 조직 URL> --api-version 7.1 --query "value[].{id:id,status:status,isDeleted:isDeleted,threadContext:{filePath:threadContext.filePath},comments:comments[].{id:id,parentCommentId:parentCommentId,commentType:commentType,content:content,publishedDate:publishedDate,isDeleted:isDeleted,author:{uniqueName:author.uniqueName}}}" -o json` — 프로젝션은 삭제·system 스레드를 버리지 않는다(미리뷰 복구와 경로 분류가 그것들을 본다).
- **대댓글**: 본문 JSON은 `bash bin/guarded.sh pr-review-resolve "$TOKEN" write state/ado-body.pr-review-resolve.json <<'__BODY__'`에 이어 JSON과 `__BODY__`를 넘기는 한 호출로 쓴다 — check가 그 안에 들어 있으므로 직전 check와 파일 도구 쓰기를 하지 않는다. 넣는 내용은 `{"content":"...","parentCommentId":{원댓글ID},"commentType":"text"}`이고, 이어 `bash bin/az pr-review-resolve devops invoke --area git --resource pullRequestThreadComments --route-parameters project={project} repositoryId={repo} pullRequestId={PR_ID} threadId={threadId} --org <config 조직 URL> --api-version 7.1 --http-method POST --in-file state/ado-body.pr-review-resolve.json`. 매번 덮어쓰고 지우지 않는다.
- **스레드 상태 PATCH**: 본문은 매번 같아 `state/`에 쓰지 않는다 — `{"status":"fixed"}`는 `--in-file bin/body/thread-fixed.json`, `{"status":"closed"}`는 `--in-file bin/body/thread-closed.json`, `{"status":"active"}`는 `--in-file bin/body/thread-active.json`을 가리킨다. `bash bin/az pr-review-resolve devops invoke --area git --resource pullRequestThreads --route-parameters project={project} repositoryId={repo} pullRequestId={PR_ID} threadId={threadId} --org <config 조직 URL> --api-version 7.1 --http-method PATCH --in-file <본문 파일>`. 아래 본문의 `fixed`·`closed`·`active` PATCH는 모두 이 형식이다.
- **투표**: `bash bin/az pr-review-resolve repos pr set-vote --id {PR_ID} --vote {approve|approve-with-suggestions|wait-for-author|reject|reset} --org <config 조직 URL>`.

## 1. 회차 시작

`python3 bin/round.py begin pr-review-resolve`를 **한 번** 실행한다. dry-run 판정·락 획득·게이트 스냅샷·인증 확인·맥락 파일 읽기·worklist 폴드를 스크립트가 한 번에 처리해 JSON 한 줄로 돌려준다. 이것들을 따로 실행하지 않는다 — 각각이 도구 호출 한 턴이었고 할 일 없는 회차조차 그것만으로 8턴을 썼다.

받는 값은 `live`(dry-run 여부)·`token`·`runStartedEpoch`(토큰과 같은 값)·`snapshot`(pending을 snapshot으로 복사했음)·`auth`(`bin/az` 인증 확인 결과)·`context`(맥락 파일 `state/gate/context.pr-review-resolve.json` 내용, 없으면 null)·`worklist`(`pr-review-worklist.jsonl`의 활성 집합, 폴드 완료)다. `token` 값을 이 세션이 기억한다. **셸 변수에 담지 않는다** — Bash 호출끼리 셸 변수를 물려주지 않아 `$TOKEN`은 빈 값으로 전개되고, 그러면 `guarded.sh`가 exit 3으로 끝나 이 회차의 쓰기가 전부 막힌다. 아래 본문의 `"$TOKEN"`은 그 자리에 **토큰 값을 그대로 박으라는** 표기다. worklist 항목에 `inFlight`가 붙어 있으면 그 automation의 회차가 **지금 돌고 있고 그 항목을 등록한 것이 그 회차다** — `begin`이 그 automation의 락 소유 epoch과 항목의 등록 ts를 비교해 붙인다.

`error`가 있으면(`lock-busy`·`no-pending`·`auth-failed`·`fold-failed`) 그 사유로 **대상 특정 전 실패**를 보고하고 종료한다 — 스크립트가 락을 이미 풀었으므로 release를 부르지 않는다.

`live`가 false면 dry-run이다. 조회·검증은 같게 수행하고 ADO 댓글·resolve·투표와 모든 state 쓰기·commit은 수행 예정으로만 보고한다.

## 2. 일감·검증·해소

`config`는 `begin` JSON의 `context.config`, 활성 집합은 `begin` JSON의 `worklist`다. 인증은 `begin`이 `auth:ok`로 이미 확인했다 — `account show`도 `fold-worklist.py`도 다시 부르지 않는다. 빈 `worklist`는 성공한 no-op이다.

각 worklist PR을 순차 처리한다 — 분류·조회·판정·효과를 그 PR 안에서 끝내고 다음 PR로 넘어간다.

**`inFlight`가 붙은 PR은 이번 회차에서 손대지 않는다.** 조회·검증·대댓글·resolve·재투표·close·미리뷰 복구를 모두 건너뛰고 `미처리`로 남기며, 사유는 `<automation> 회차 진행 중`이다. `pr-review-intake`는 09-16 고아 PR 사고 뒤 **리뷰 전에** worklist에 등록하고, 이 프롬프트는 「내 `text` 스레드 0건」을 리뷰 실패의 복구 신호로 쓴다. 리뷰가 도는 몇 분은 두 판정이 함께 성립하는 창이고, 락은 automation별이라 intake와 resolve를 직렬화하지 않는다. 2026-09-17 11:01 intake와 11:10 resolve가 그 창에서 `Lingo/tx-lingo-api#{PR}`에 같은 지적을 두 벌 달았고(스레드 91421·91425, 91422·91426, 본문이 사실상 같고 멘션 위치만 다르다) 작성자가 네 스레드에 모두 답글을 썼다. 스레드 집합이 아직 채워지는 중이라 재투표와 close 판정도 이 PR에는 성립하지 않는다 — `nit:`만 올라온 시점에 `approve-with-suggestions`를 찍으면 뒤이어 올라올 `issue:`를 덮는다. 그 회차가 끝나면 `inFlight`가 사라지고 다음 회차가 평소대로 처리한다.

PR의 `status`·`srcCommit`·`tgtCommit`·`createdById`(작성자 멘션용)는 `begin` JSON의 `context.prs`에서 읽는다 — precheck가 게이트 판정에 이미 조회한 손실 없는 값이므로 `repos pr show`를 다시 부르지 않는다(종전엔 작성자 GUID 때문에 18세션에 26회 불렀다). 항목이 없으면 그 PR만 직접 조회한다. **스레드는 맥락에 없다. `pullRequestThreads`로 직접 조회한다.** 게이트 digest의 스레드 요약은 해시용 축약이라 댓글 원문도 루트 작성자도 접두어도 없어 검증 입력이 되지 못한다. 이 조회 또는 필요한 로컬 commit 읽기 실패는 해당 PR만 미처리로 남기고 다음 PR로 간다.

**재조회의 유일한 예외는 첫 외부 효과 직전의 재확인이다.** active PR의 첫 외부 효과(대댓글·`closed`·재투표·원장·worklist `close`·미리뷰 복구의 리뷰 댓글)를 내기 직전에 두 조회를 그 PR에 한 번씩 실행한다.

- `bash bin/az pr-review-resolve repos pr show --id {PR_ID} --org <config 조직 URL> --query "{source:lastMergeSourceCommit.commitId}"` — 돌아온 `source`가 맥락의 `srcCommit`과 다르면 미처리다.
- 위 스레드 목록 명령(같은 프로젝션) — 이번 회차에서 효과를 낼 각 스레드의 `status`와 **댓글 목록 전체**(`id`·`content`·`publishedDate`·`isDeleted`, 배열 순서)가 판정에 쓴 조회 결과와 같은지 비교한다. 마지막 댓글만으로는 앞 댓글의 편집·삭제나 같은 내용의 새 댓글을 구분하지 못한다. 스레드에 차이가 보이면 그 스레드만 다시 판정한다 — 댓글 목록이 바뀌었으면 경로 A로, status가 바뀌었으면 미검증 재검증 기준으로. 재판정 결과에 따라 close·재투표 판정도 다시 하고, 근거가 사라진 효과는 내지 않는다.

조회가 실패하거나 `srcCommit`이 달라졌으면 그 PR에는 효과를 하나도 내지 않고 `미처리`로 남긴다 — 다음 tick의 precheck가 최신 커밋으로 맥락과 diff를 다시 떨군다.
- completed(병합)는 이 루틴이 다루지 않는다. 스레드 조회·대댓글·상태 PATCH·원장·worklist close를 모두 하지 않고 worklist에 그대로 둔다. **병합된 PR의 스레드 정리는 `pr-review-merged`가 소유한다.** merged는 병합 후 7일 동안 작성자 답변을 검증하고, 7일이 지나면 남은 열린 스레드를 `merged-unresolved`로 기록해 닫는다. 이 루틴이 병합 직후 스레드를 닫고 worklist를 close하면 merged가 그 PR을 다시 보지 못해 병합 후 답변 검증이 돌지 않는다(2026-10-06 PR {PR}: 병합 후 resolve가 열린 스레드를 모두 `merged-unresolved`로 닫아 merged의 검증 대상이 0건이었다).
- abandoned는 라이브에서 lock check 뒤 `pr-review-worklist.jsonl`에 `op:"close"`, `reason:"abandoned"`, 해당 key와 `by:"pr-review-resolve"`를 append한다.
- active는 두 가지를 추린다. 접두어 비교는 이 프롬프트 전체에서 대소문자를 구분하지 않는다(`Nit:`·`nit:` 동일).
  - (1) status가 `active`·`pending`이고 첫 댓글 작성자가 `config`의 `user`인 스레드. `commentType`이 `system`인 스레드(투표·푸시 알림)는 내 이름으로 생성돼도 리뷰 스레드가 아니므로 제외한다.
  - (2) 타인이 루트이고 status가 `active`·`pending`인 스레드에 단 내 `issue:`·`discuss:` 답글. 접두어 없는 의견 답글은 세지 않는다. 그 답글 뒤에 첫 줄이 `resolved:`로 시작하는 내 대댓글이 있고 그 대댓글 뒤로 작성자나 스레드 소유자의 댓글이 없으면 해소 기록이 있는 것이므로 추리지 않는다.
  - 닫힌 스레드는 아래 「미검증 재검증」이 다룬다.

### 미리뷰 복구

**내 `text` 스레드가 0건인 active PR은 아직 리뷰되지 않은 것이므로 이 회차에서 리뷰한다.** 착수 투표만 찍히고 코드 판정이 실패했거나, Slack 창이 지나가 `pr-review-intake`가 더는 집지 않는 PR이 여기 해당한다(2026-09-16 PR {PR} 실관측 — worklist에 남았지만 intake는 창 밖이라 건너뛰고 resolve는 검증할 스레드가 없어 아무것도 하지 않았다).

이 PR은 **아래 해소 분기를 타지 않는다.** 대신 `pr-review-intake`의 「2. 수집·판정·리뷰」의 리뷰 절차를 이 세션에서 인라인으로 수행한다 — `numstat`·`patch` 읽기(없으면 `git --no-optional-locks` 읽기), `~/work/harnie/skills/pr-review/SKILL.md`와 그 레포의 팀 리뷰 규칙 적용, `issue:`·`discuss:`·`nit:` 접두어와 filePath·라인·본문의 `findings` 산출. 그 결과로 ADO 스레드 작성·투표·`review-findings.jsonl`·`pr-review-summary.jsonl`을 **intake와 같은 규칙으로** 처리한다. **`by`는 빌려오지 않는다** — 원장과 worklist의 `by`는 그 줄을 실제로 쓴 automation이므로 이 경로에서도 `pr-review-resolve`다. intake의 줄 형식을 그대로 흉내 내다 `by:"pr-review-intake"`를 복사하면 resolve가 한 리뷰가 intake의 것으로 집계되고, 「진단 순서」와 automation별 회계가 전부 어긋난다(2026-09-17 `Collect/<레포 F>#{PR}`·`<공백 있는 프로젝트>/tx-scraper-vessel-schedule#{PR}`의 ts `1789618273` 등록 세 건이 resolve 토큰인데 `by`는 intake로 적혔다). `approve`(지적 0건)가 성공했으면 intake와 같이 lock check 뒤 worklist를 `reason:"no-findings"`로 close한다 — 닫지 않으면 지적 0건 PR이 매 회차 다시 리뷰된다. `approve-with-suggestions`(nit만)는 close하지 않고 남긴다 — 열린 nit은 아래 미해결 집합에 들어가 close를 막고, 작성자가 nit에 답하면 다음 회차가 검증한다. nit까지 전부 해소되면 `approve` 재투표와 `all-threads-resolved` close가 아래 분기로 작동한다.

복구로 만든 지적의 `review-findings.jsonl` 줄에는 `ts`(epoch)·`threadId`(스레드 POST 응답의 id)·`by:"pr-review-resolve"`를 함께 적는다 — 게이트 commit이 이 필드로 신규 스레드를 귀속해 재생한다.

### 해소 분기

스레드를 최신 댓글 작성자로 분류한다.

- 경로 A: 최신 댓글이 나 이외의 사람이다. 답변을 검증한다. 이 경로는 반드시 resolve 또는 근거 대댓글 중 하나로 끝낸다.
- 경로 B: 최신 댓글이 나다. 내 마지막 댓글 이후 `The reference refs/pull/<id>/source was updated.` 시스템 스레드 publishedDate가 있으면 대상 후보다. 후보 스레드의 `threadContext.filePath`를 `patch`·`git --no-optional-locks` 읽기로 source에서 판별해 갱신이 그 지적에 닿는지 확인한다. `issue:`는 코드만으로 판정할 수 있고, `discuss:`는 자동 해소하지 않는다. 구 접두어 없는 댓글만 내용으로 판정한다. 명확히 해소된 경우만 처리하고 애매·부분 해소·미해소는 아무 동작도 하지 않는다.
- (2)의 타인 루트 답글은 스레드 전체가 아니라 내 마지막 `issue:`·`discuss:` 답글 이후의 댓글로 경로를 정한다. 그 뒤에 작성자나 스레드 소유자의 댓글이 있으면 경로 A, 없으면 경로 B다.

**검증은 이 세션이 스레드 원문과 diff로 내린다.** `~/work/harnie/skills/pr-review/SKILL.md`와 `~/work/harnie/skills/comment-resolve/SKILL.md`를 검증 대상이 생긴 시점에 읽고 그 기준을 적용한다 — 내용을 복사하지 않는다.

답변의 코드 수정·PR description·후속 변경·설명이 실제 지적을 해소하는지 source commit 기준으로 검증한다. **PR 소속 커밋의 변경은 precheck가 떨군 `numstat`·`patch`에 있다** — `numstat`을 먼저 읽어 볼 파일을 정하고 `patch`는 필요한 구간만 읽는다. 읽을 구간이 둘 이상 정해졌으면 `sed -n 'a,bp;c,dp' <patch>` 한 호출에 범위를 나열하고, 그 출력이 표시 상한을 넘길 정도로 길면 나누어 읽는다. 맥락에 그 경로가 없을 때만 `git --no-optional-locks -C ~/work/<repository>` 읽기 명령으로 범위를 직접 잡는다 — fetch·clone·working tree 접근은 금지한다.

판정 분기는 `resolved`·`unresolved`·`unclear`·철회 넷이다. **`resolved`일 때만 해소로 처리한다. `unclear`는 애매로 보아 경로 A는 확인 요청 대댓글, 경로 B는 무동작이다.** 판정 자체가 실패하면 그 PR을 미처리로 남긴다.

### 오지적 철회

**작성자 반박이 그 지적이 사실과 다름을 분명히 보일 때만 철회한다** — 확신이 서지 않으면 `unresolved`로 둔다. 철회로 판정한 스레드는 대댓글을 달지 않는다. lock check 뒤 `state/code-quality-list.jsonl`에 `outcome:"finding-retracted"`, `threadStatus:"closed"` 줄을 append하고(필드 구성은 아래 해소 경로와 같다), 성공하면 lock check 뒤 그 스레드를 `{"status":"closed"}`로 PATCH한다 — `fixed`가 아니다, 해결된 것이 아니라 지적이 잘못된 것이다. **원장 append가 실패하면 스레드를 건드리지 않고 그 PR을 미처리로 남긴다** — 다음 회차가 같은 판정에 도달해 다시 시도한다. 철회된 스레드는 미해결 집합에서 빠지므로 아래 재투표·close 판정이 그대로 적용된다.

**투표를 바꾼 PR은 그 자리에서 `state/pr-review-summary.jsonl`에 갱신 한 줄을 append한다.** lock check 뒤 `ts`·`key`·`srcCommit`(지금 판정한 것)·`prefixes`(**지금 열려 있는** 내 스레드의 접두어만)·`summary`·`vote`를 담는다. **이 append 실패는 그 PR의 실패다** — 미처리로 남기고 게이트를 commit하지 않는다. 게이트가 먼저 commit되면 다음 회차가 같은 digest를 SKIP하고, 해소된 `issue:`가 담긴 stale 요약이 가장 늦은 줄로 남아 배포승인을 영구히 막는다.

검증이 통과한 스레드는 먼저 라이브에서 lock check 뒤 `state/code-quality-list.jsonl`에 append한다. `occId`는 `"<project>/<repository>#<pullRequestId>/<threadId>"`이고, `ts`, `summary`, `prefix`, project/repository/PR/thread/filePath, `outcome:"resolved"`, `by:"pr-review-resolve"`를 포함한다. 스레드 상태를 PATCH하는 줄에는 실제로 적용한 상태를 `threadStatus` 필드로 함께 적는다 — 이 경로는 `fixed` PATCH를 하므로 `threadStatus:"fixed"`다. 타인 루트 답글처럼 PATCH하지 않는 줄에는 쓰지 않는다. 게이트 commit이 이 필드로 자기 쓰기를 귀속해 재생하므로, 적용한 상태와 필드 값이 다르면 다음 회차가 헛발화한다. 이 원장 append가 실패하면 대댓글·resolve·재투표를 하지 않고 해당 PR을 미처리로 남긴다.

원장 저장 후에만 lock check 뒤 PR 작성자 `@<GUID>` 리터럴 멘션, 검증 근거, `config`의 `disclaimer` 두 줄을 포함한 대댓글을 POST한다. 이어 lock check 뒤 스레드를 `fixed`로 resolve한다. **(2)의 타인 루트 답글은 내가 스레드를 닫을 수 없으므로**, 이 대댓글의 첫 줄을 `resolved:`로 시작해 해소를 기록하고 `fixed` PATCH는 하지 않는다. 같은 이유로 (2)에는 철회 분기를 쓰지 않는다. 반박이 맞으면 원장 `outcome`을 `finding-retracted`로 적고, 같은 `resolved:` 대댓글에 철회 사유를 남긴다. 경로 A의 검증 실패·애매함에는 lock check 뒤 같은 형식의 확인 요청 또는 유지 사유 대댓글을 남기되 스레드는 active로 둔다. 경로 B의 불확실한 결과에는 대댓글을 추가하지 않는다.

**재투표는 내 `issue:`·`discuss:` 지적이 전부 해소로 처리된 뒤에만 한다.** 하나라도 열려 있으면 투표를 바꾸지 않는다. **해소로 세는 것은 내가 검증해 처리한 것뿐이다.** 남이 닫은 스레드는 아래 「미검증 재검증」을 통과해야 해소로 센다.

**닫혔는지는 이번 회차의 검증 대상 수로 판단하지 않는다.** 경로 A·B의 대상이 0건인 것은 "이번에 검증할 것이 없다"는 뜻이지 "닫혔다"는 뜻이 아니다. 방금 내가 단 지적은 최신 댓글이 나라서 경로 A에도 B에도 안 걸리지만 열려 있다. 이 둘을 섞으면 지적이 열린 PR에 `approve`를 찍는다.

**ADO 스레드 상태로 다시 조회해 센다.**

- 내가 루트이고 `status`가 `active`·`pending`인 스레드(`commentType: system` 제외)
- 타인 루트의 `active`·`pending` 스레드에 단 내 `issue:`/`discuss:` 답글 중 `resolved:` 해소 기록이 없는 것(기준은 위 active 추림 (2)와 같다)
- 아래 「미검증 재검증」에서 `unresolved`·`unclear`로 나온 것

**미검증 재검증.** 같은 조회 결과에서 아래 두 가지를 더 골라 투표 판정 전에 검증한다.

- 내가 루트인 `issue:`·`discuss:` 스레드 중 `status`가 `active`·`pending`이 아니고(`fixed`·`wontFix`·`closed`·`byDesign` 등), 원장에 그 `occId`의 `resolved`·`finding-retracted` 줄이 없는 것. 이 루틴과 `pr-review-merged`는 스레드를 닫기 전에 반드시 원장에 쓴다. 그래서 원장에 없는 닫힌 스레드는 작성자나 다른 사람이 닫은 것이다. 원장은 PR마다 `grep -F '<project>/<repository>#<pullRequestId>/' state/code-quality-list.jsonl` 한 번으로 읽는다.
- 타인 루트이고 `status`가 `active`·`pending`이 아닌 스레드에 단 내 `issue:`·`discuss:` 답글 중 `resolved:` 해소 기록이 없는 것.

검증 기준과 판정 분기는 위 해소 분기와 같다. `resolved`면 lock check 뒤 원장에 `outcome:"resolved"` 줄을 append하고(타인 루트 답글이면 이어서 `resolved:` 대댓글을 단다) 상태는 그대로 둔다. 이 원장 줄이 있어야 다음 회차가 같은 스레드를 다시 검증하지 않는다. `unresolved`·`unclear`면 내 루트 스레드는 먼저 lock check 뒤 원장에 `outcome:"thread-reopened"`, `threadStatus:"active"` 줄을 같은 형식으로 append하고, 성공하면 유지 사유 대댓글을 남기고 `bin/body/thread-active.json`으로 `active`로 되돌린다. 원장 append가 실패하면 되돌리지 않고 그 PR을 미처리로 남긴다. 타인 루트 답글은 되돌릴 수 없으므로 상태를 그대로 두고 열린 지적으로만 센다. 원장 조회나 판정이 실패하면 그 PR을 미처리로 남긴다. 검증 없이 해소로 세면 남이 닫은 미해소 지적 위에 승인이 올라간다.

이 집합의 접두어로 투표를 정한다. 접두어는 그 스레드에 있는 **내 댓글**의 `issue:`·`discuss:`·`nit:`에서 읽는다 — 내가 루트면 첫 댓글이 내 것이고, 타인 루트면 내 답글이다. **첫 댓글에서 읽으면 안 된다**: 타인의 `nit:` 스레드에 내 `issue:` 답글이 열려 있을 때 `nit`만 남은 것으로 잘못 세어 승인으로 올라간다.

- 집합이 비어 있고 **그 PR에 내 `text` 스레드가 하나라도 있었으면** `approve`. `commentType`이 `system`인 스레드는 내 이름으로 생성돼도 리뷰가 아니다 — 착수 투표가 `<내 표시 이름> voted -5`를 만든다(2026-09-16 PR {PR}). 내 `text` 스레드가 아예 없으면 이 PR을 리뷰한 적이 없거나 리뷰가 중간에 실패한 것이므로 **투표를 건드리지 않고 미검토로 보고한다** — 비어 있음을 지적 없음으로 읽으면 검토되지 않은 PR이 승인된다
- 열린 것이 `nit:`뿐이면 `approve-with-suggestions`
- `issue:`·`discuss:`가 하나라도 열려 있으면 **투표를 바꾸지 않는다**

라이브면 lock check 뒤 투표한다. 비어 있거나 `nit:`뿐이라는 판정은 스레드를 실제로 조회해 확인했을 때만 성립한다. 같은 값으로 다시 투표해도 결과가 같으므로 현재 투표를 조회하지 않는다.

active PR에 **위 미해결 집합이 비어 있고 그 PR에 내 `text` 스레드가 하나라도 있었을 때만** 라이브에서 close(`reason:"all-threads-resolved"`)한다. 내 `text` 스레드가 아예 없으면 투표도 close도 하지 않고 미검토로 보고한다 — 착수 선등록 뒤 판정이 실패한 항목이 여기 해당하고, 닫으면 검토되지 않은 PR이 추적에서 빠진다. 경로 A·B의 처리 건수가 0인 것은 close 근거가 아니다. **close 직전에 위 재투표 판정을 반드시 먼저 수행한다.** 타인 루트 스레드의 해소 기록 없는 내 `issue:`/`discuss:` 답글도 미해결 집합에 들어 있으므로 close를 막는다. close append 직전 lock check를 한다.

PR 하나의 조회·검증·원장·ADO 쓰기·투표·close 실패는 그 PR만 미처리로 남기고 다음 PR로 넘어간다. 원장 → 근거 대댓글 → resolve → 재투표 순서는 바꾸지 않는다.

## 3. 상태 기록

원장과 worklist close는 2단계에서 각각의 대상 직후에만 append한다. 모든 대상이 성공했을 때만 회차 성공이다. dry-run에서는 각 append 예정과 ADO 수행 예정만 기록한다.

## 4. 회차 종료와 보고

정상 경로에서는 `python3 bin/round.py finish pr-review-resolve "$TOKEN" [--commit]`를 **한 번** 실행한다. 스크립트가 lock check → 게이트 commit → 락 해제를 한 번에 처리한다. `--commit`은 모든 대상이 성공했고 라이브일 때만 붙인다. 대상 하나라도 미처리이거나 dry-run이면 commit하지 않는다. `error`가 `lock-lost`면 소유권을 잃은 것이라 아무것도 하지 않았다는 뜻이다. `lock.sh release`·`precheck.py commit`을 따로 부르지 않는다.

한국어 보고에는 worklist 항목 수, `begin`이 `worklistSkipped`를 돌려줬으면 건너뛴 깨진 줄 수, active·completed·abandoned 분류, 경로 A/B별 resolve·대댓글·무동작·철회 건수, 미검증 재검증의 해소·`active` 복귀 건수, 재투표, 원장/close append, 미처리 PR과 사유(stale `srcCommit`으로 효과를 미룬 PR 포함), commit 여부와 dry-run 수행 예정 목록을 포함한다.
