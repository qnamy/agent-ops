<!-- sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다. 원본은 비공개 워크스페이스에서 운영 중. -->
# pr-review-merged

이 프롬프트 본문은 automation 트리거가 이미 줬다. **이 파일을 다시 읽지 않고, 자기 지시를 `rg`·`grep`으로 검색하지 않는다.** 재읽기 한 번과 자기 검색 한 번이 회차 도구 출력의 54%였다(2026-09-16 실측 7,659토큰). **개인 메모리(`~/.codex/memories/`)도 읽지 않는다** — 2026-09-17 07:20 회차가 첫 턴에 그것을 `rg`로 28,337자 올려 11턴 내내 다시 실었다. 무인 회차의 판단은 이 프롬프트와 맥락 파일의 `config`만으로 한다.

이 실행은 `state/pr-review-worklist.jsonl`의 활성 항목 중 Completed PR의 내 active 루트 리뷰 스레드를 정리한다. Active PR은 건드리지 않고, 투표도 하지 않는다. 조직·사용자·ADO 댓글 면책 문구는 `state/gate/context.pr-review-merged.json`의 `config`에서 읽는다 — precheck가 `ROUTINE-CONFIG.md`를 이미 파싱해 실어 둔다. **`config`가 없을 때만 `~/work/ROUTINE-CONFIG.md`를 직접 읽는다.** 회사 좌표·GUID·문구를 하드코딩하지 않는다. `~/work/.legacy-routine-state/`와 `~/work/legacy-routines/`에는 쓰지 않는다. 크리덴셜 값은 출력하거나 기록하지 않는다.

ADO 호출은 전부 `bash bin/az pr-review-merged ...`로 한다. 레포 접근은 `git --no-optional-locks -C ~/work/<repository> ...` 읽기 명령으로 제한하고 fetch·clone·working tree 접근을 하지 않는다. **쓰기 직전의 lock check는 두 형태다.** 셸 명령인 쓰기(`bin/az`의 POST·PATCH·`set-vote`, 원장·worklist append, `state/deploy-approval-react.sh`, `pr-session.sh close`, `mark.py`)는 `bash bin/guarded.sh pr-review-merged "$TOKEN" run <명령…>` 또는 `bash bin/guarded.sh pr-review-merged "$TOKEN" append <파일> '<한 줄>'`로 실행한다 — 스크립트가 check를 먼저 하고 실패하면 명령을 실행하지 않고 exit 3으로 끝나며, 그때는 소유권을 잃은 것이니 그 자리에서 종료하고 상태 기록·commit·release를 시도하지 않는다. 셸 명령이 아닌 쓰기 — MCP 도구(Slack·Jira·Confluence)와 파일 도구로 덮어쓰는 `state/ask.*.md`·`state/ado-body.*.json` 같은 모든 `state/` 파일 — 는 직전에 `bash bin/lock.sh check pr-review-merged "$TOKEN"`을 따로 한다. **아래 본문의 'lock check 뒤'는 이 규칙대로 읽는다** — 셸 명령이면 guarded 한 번, 그 외면 check 한 번. 실행 수단이 무엇이든 `state/` 쓰기는 이 둘 중 하나다. 그 밖의 자리에서 `lock.sh check`를 부르지 않는다. 파일 생성·수정은 이 워크스페이스 안에서 한다. `/tmp` 등 워크스페이스 밖 경로에 스크립트나 파일을 만들지 않는다. **파일을 지우지 않는다** — `rm`은 승인 프롬프트를 띄우고 무인 회차에는 답할 사람이 없어 그 자리에서 멈춘다. 재사용하는 파일은 덮어쓴다. **`git worktree`를 만들지 않고 빌드·테스트·패키지 매니저 명령(`mvn`·`gradle`·`npm`·`pytest` 등)을 실행하지 않는다.** 판정은 정적 읽기로만 한다 — 작업 사본을 만들면 정리가 필요해지고 그 정리가 다시 승인 프롬프트를 부른다.


**도구 이름을 모를 때만 탐색하고, 탐색은 이름만 뽑는다.** `ALL_TOOLS` 필터 결과를 도구 객체째로 출력하면 설명 필드까지 컨텍스트에 박혀 회차가 끝날 때까지 매 턴 다시 읽힌다(2026-09-15 실측: 한 번에 8,920토큰). `x.name`만 출력하고, 같은 회차에서 같은 탐색을 두 번 하지 않는다.

## 도구와 명령 형식

### ADO 호출 규율

`repos`·`devops` 호출에는 `--org <config 조직 URL>`을 포함한다. 인증 확인용 `account show`는 그 인자를 받지 않으므로 붙이지 않는다. 모든 az 호출은 **단일 명령**으로만 실행한다. `cd`·파이프·리다이렉션을 쓰지 않으며, 복합이 필요하면 워크스페이스 안에 `.sh`를 만들고 `bash <파일>`로 실행한다. **조회 다이어트**: `--project` 없는 조직 전체 `pr list`와 `--top 1000`류 전량 덤프를 금지하고, 모든 조회는 `--query`로 필요한 최소 필드만 뽑는다. 대형 JSON 덤프는 컨텍스트를 태워 회차를 상한까지 끌고 간다(2026-08-24 실관측).

- **스레드 목록**: `bash bin/az pr-review-merged devops invoke --area git --resource pullRequestThreads --route-parameters project={project} repositoryId={repo} pullRequestId={PR_ID} --org <config 조직 URL> --api-version 7.1 -o json` → `value[]`(각 `comments[]`·`status`·`threadContext.filePath`·`comments[].author.uniqueName`·`comments[].publishedDate`).
- **대댓글**: 본문 JSON을 `state/ado-body.pr-review-merged.json`에 쓴다 — `{"content":"...","parentCommentId":{원댓글ID},"commentType":"text"}`를 넣고 `bash bin/az pr-review-merged devops invoke --area git --resource pullRequestThreadComments --route-parameters project={project} repositoryId={repo} pullRequestId={PR_ID} threadId={threadId} --org <config 조직 URL> --api-version 7.1 --http-method POST --in-file state/ado-body.pr-review-merged.json`. 매번 덮어쓰고 지우지 않는다.
- **스레드 resolve**: `state/ado-body.pr-review-merged.json`에 `{"status":"fixed"}`를 쓴 후 `bash bin/az pr-review-merged devops invoke --area git --resource pullRequestThreads --route-parameters project={project} repositoryId={repo} pullRequestId={PR_ID} threadId={threadId} --org <config 조직 URL> --api-version 7.1 --http-method PATCH --in-file state/ado-body.pr-review-merged.json`.

## 1. 회차 시작

`bash bin/round.py begin pr-review-merged`를 **한 번** 실행한다. dry-run 판정·락 획득·인증 확인·맥락 파일 읽기·worklist 폴드를 스크립트가 한 번에 처리해 JSON 한 줄로 돌려준다. 이것들을 따로 실행하지 않는다 — 각각이 도구 호출 한 턴이었고 할 일 없는 회차조차 그것만으로 8턴을 썼다.

받는 값은 `live`(dry-run 여부)·`token`·`runStartedEpoch`(토큰과 같은 값)·`auth`(`bin/az` 인증 확인 결과)·`context`(맥락 파일 `state/gate/context.pr-review-merged.json` 내용, 없으면 null)·`worklist`(`pr-review-worklist.jsonl`의 활성 집합, 폴드 완료)다. `token`을 `TOKEN`으로 보관한다.

`error`가 있으면(`lock-busy`·`auth-failed`·`fold-failed`) 그 사유로 **대상 특정 전 실패**를 보고하고 종료한다 — 스크립트가 락을 이미 풀었으므로 release를 부르지 않는다.

`live`가 false면 dry-run이다. 조회·분류·검증은 라이브와 같게 수행하되 ADO 댓글·resolve와 worklist·원장 쓰기는 하지 않고 예정만 보고한다.

## 2. 일감·검증·정리

`config`는 `begin` JSON의 `context.config`, 활성 집합은 `begin` JSON의 `worklist`다. 인증은 `begin`이 `auth:ok`로 이미 확인했다 — `account show`도 `fold-worklist.py`도 다시 부르지 않는다. 빈 `worklist`는 성공한 no-op이다.

각 PR을 순차 처리한다.

**completed PR의 source commit을 로컬에서 얻을 수 없으면 `처리 불가`로 분류한다.** 병합 시 `refs/pull/<id>/source`가 삭제되어 재시도로 복구되지 않는다. active PR의 커밋 부재는 `미처리`다. `처리 불가`는 보고에 사유와 함께 남긴다.

- active는 이 루틴 대상이 아니므로 worklist에 그대로 둔다.
- abandoned는 라이브에서 lock check 뒤 `pr-review-worklist.jsonl`에 key, `op:"close"`, `reason:"abandoned"`, `by:"pr-review-merged"`를 append한다.
- completed이고 closedDate가 7일 초과면 같은 방식으로 `reason:"closed-over-7-days"`로 close한다.
- completed이며 7일 이내인 PR만 스레드를 본다. status active, 첫 댓글 작성자가 나, 최신 댓글 작성자가 내가 아닌 사람인 스레드만 검증 대상이다. `commentType`이 `system`인 스레드(투표·푸시 알림)는 내 이름으로 생성돼도 제외한다. 최신 댓글이 나인 스레드는 작성자 답변 대기이므로 건너뛴다.

검증 대상이 처음 생긴 시점에 `~/work/harnie/skills/pr-review/SKILL.md`와 `~/work/harnie/skills/comment-resolve/SKILL.md`를 읽어 적용한다. 본문은 복사하지 않는다. 근거는 Slack이 아니라 PR description과 후속 PR/커밋이다. description 반영 주장은 실제 description으로, 코드 수정·후속 작업 주장은 해당 변경으로, 설명·해명은 지적에 대한 타당성으로 검증한다.

검증이 통과한 스레드는 라이브에서 먼저 lock check 뒤 `state/code-quality-list.jsonl`에 append한다. `occId`는 `"<project>/<repository>#<pullRequestId>/<threadId>"`이며 `ts`, summary, prefix, project/repository/PR/thread/filePath, `outcome:"resolved"`, `by:"pr-review-merged"`를 포함한다. append가 실패하면 외부 효과를 내지 않고 해당 PR을 미처리로 남긴다. 성공하면 lock check 뒤 PR 작성자 `@<GUID>` 리터럴 멘션, 검증 근거, `config`의 `disclaimer` 두 줄을 가진 대댓글을 남기고, 다시 lock check 뒤 `fixed`로 resolve한다. 투표는 하지 않는다.

검증은 실패했지만 지적 자체가 유효한 스레드는 무한 폴링하지 않는다. 라이브에서 먼저 lock check 뒤 같은 원장에 `ts`, `occId`와 지적 식별·요약 필드, `outcome:"moved-from-merged"`, `by:"pr-review-merged"`를 append한다. 성공한 뒤에만 lock check 뒤 PR 작성자 멘션과 `config`의 `disclaimer` 두 줄을 붙여 `머지된 PR이라 이 지적은 후속 과제로 넘긴다`는 대댓글을 남긴다. 그 뒤 lock check를 하고 해당 PR key를 `reason:"moved-to-quality-list"`로 close한다. 원장 append 실패 시 대댓글·close를 하지 않는다.

completed 7일 이내 PR에서 내 active 루트 스레드가 더 이상 없으면 라이브에서 lock check 뒤 `reason:"all-threads-resolved"`로 close한다. 그 외에는 worklist에 남긴다. close가 이미 moved-to-quality-list로 기록된 PR에는 추가 close를 쓰지 않는다.

PR 하나의 조회·검증·원장·ADO 댓글·resolve·close 실패는 그 PR만 `미처리`로 남기고 다음 PR로 진행한다. **`처리 불가`로 분류한 PR은 회차 성공 판정에서 뺀다.** 원장 → 외부 대댓글/resolve → worklist close 순서는 바꾸지 않는다.

## 3. 상태 기록

원장과 close 이벤트는 2단계에서 각 대상 처리 직후에만 append한다. dry-run에서는 원장·close 예정과 ADO 수행 예정만 보고한다. 모든 대상 성공 여부는 보고에 남긴다.

## 4. 회차 종료와 보고

정상 경로에서는 `bash bin/round.py finish pr-review-merged "$TOKEN"`를 **한 번** 실행한다. 스크립트가 lock check → 락 해제를 한 번에 처리한다. `error`가 `lock-lost`면 소유권을 잃은 것이라 아무것도 하지 않았다는 뜻이다. `lock.sh release`·`precheck.py commit`·`pr-session.sh sweep`을 따로 부르지 않는다.

한국어 보고에는 worklist 수, active·abandoned·7일 초과·7일 이내 분류, 검증 통과 resolve, 검증 실패 후 quality-list 이관, close 사유, 미처리 PR과 사유, dry-run 수행 예정 목록을 포함한다.
