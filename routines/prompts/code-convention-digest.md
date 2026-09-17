<!-- sanitized template — 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다. 원본은 비공개 워크스페이스에서 운영 중. -->
# code-convention-digest

이 프롬프트 본문은 automation 트리거가 이미 줬다. **이 파일을 다시 읽지 않고, 자기 지시를 `rg`·`grep`으로 검색하지 않는다.** 재읽기 한 번과 자기 검색 한 번이 회차 도구 출력의 54%였다(2026-09-16 실측 7,659토큰). **개인 메모리(`~/.codex/memories/`)도 읽지 않는다** — 2026-09-17 07:20 회차가 첫 턴에 그것을 `rg`로 28,337자 올려 11턴 내내 다시 실었다. 무인 회차의 판단은 이 프롬프트와 `ROUTINE-CONFIG.md`만으로 한다.

이 실행은 `state/code-quality-list.jsonl`에 등록된 해소된 지적만 군집화해 팀 컨벤션 승격 후보를 Slack DM으로 제안한다. 새 리뷰를 만들거나 lint·CI·리뷰 기준을 변경하지 않는다. `~/work/ROUTINE-CONFIG.md`에서 사용자 Slack ID와 필요한 좌표를 읽고 값은 하드코딩하지 않는다. `~/work/.legacy-routine-state/`와 `~/work/legacy-routines/`에는 쓰지 않는다.

사내 레포의 읽기·fetch·clone·working tree 쓰기를 하지 않는다. **쓰기 직전의 lock check는 두 형태다.** 셸 명령인 쓰기(`bin/az`의 POST·PATCH·`set-vote`, 원장·worklist append, `state/deploy-approval-react.sh`, `pr-session.sh close`, `mark.py`)는 `bash bin/guarded.sh code-convention-digest "$TOKEN" run <명령…>` 또는 `bash bin/guarded.sh code-convention-digest "$TOKEN" append <파일> '<한 줄>'`로 실행한다 — 스크립트가 check를 먼저 하고 실패하면 명령을 실행하지 않고 exit 3으로 끝나며, 그때는 소유권을 잃은 것이니 그 자리에서 종료하고 상태 기록·commit·release를 시도하지 않는다. 셸 명령이 아닌 쓰기 — MCP 도구(Slack·Jira·Confluence)와 파일 도구로 덮어쓰는 `state/ask.*.md`·`state/ado-body.*.json` 같은 모든 `state/` 파일 — 는 직전에 `bash bin/lock.sh check code-convention-digest "$TOKEN"`을 따로 한다. **아래 본문의 'lock check 뒤'는 이 규칙대로 읽는다** — 셸 명령이면 guarded 한 번, 그 외면 check 한 번. 실행 수단이 무엇이든 `state/` 쓰기는 이 둘 중 하나다. **영속 셸에 보내는 명령은 판정까지 한 줄에 쓴다.** 영속 셸은 결과에 종료코드를 싣지 않는다. 다음 턴을 통째로 써서 `$?`를 읽으면 쓰기 하나가 4턴이 된다 — 2026-09-17 08:50 회차는 48호출 중 16(33%)이 종료코드 전용 턴이었다. `if bash bin/guarded.sh code-convention-digest "$TOKEN" run <명령…>; then print -r -- OK; else print -r -- FAIL; fi`처럼 **분기와 표식 출력을 같은 줄에** 넣는다. 전역 지침의 "`; echo $?`를 붙이지 마라"는 종료코드가 도구 결과에 그대로 실리는 단발 실행을 가리키며, 영속 셸에는 해당하지 않는다 — 여기서는 한 줄 안의 분기가 그 자리를 대신한다. 그 밖의 자리에서 `lock.sh check`를 부르지 않는다. 파일 생성·수정은 이 워크스페이스 안에서만 한다. `/tmp` 등 워크스페이스 밖 경로에 스크립트나 파일을 만들지 않는다. **파일을 지우지 않는다** — `rm`은 승인 프롬프트를 띄우고 무인 회차에는 답할 사람이 없어 그 자리에서 멈춘다. 재사용하는 파일은 덮어쓴다. **`git worktree`를 만들지 않고 빌드·테스트·패키지 매니저 명령(`mvn`·`gradle`·`npm`·`pytest` 등)을 실행하지 않는다.** 판정은 정적 읽기로만 한다 — 작업 사본을 만들면 정리가 필요해지고 그 정리가 다시 승인 프롬프트를 부른다.

Slack 접근은 codex Slack 플러그인 도구로만 하며 **도구 이름과 인자를 탐색하지 않는다** — `ALL_TOOLS` 필터로 찾으면 그 목록 전체가 컨텍스트에 남아 회차가 끝날 때까지 매 턴 다시 읽힌다. 아래 이름과 인자를 그대로 쓴다.

- 채널 읽기 `mcp__codex_apps__slack_slack_read_channel({channel_id, oldest, latest, limit, response_format:"detailed"})`
- 스레드 읽기 `mcp__codex_apps__slack_slack_read_thread({channel_id, message_ts, oldest, limit, response_format:"detailed"})`
- 반응 확인 `mcp__codex_apps__slack_slack_get_reactions({channel_id, message_ts})`
- 답글·DM `mcp__codex_apps__slack_slack_send_message({channel_id, thread_ts, message})`

**인자 이름은 `channel_id`와 `message_ts`다.** `channel`·`ts`·`thread_id`로 부르면 필수 인자 누락으로 거부되고, 첫 Slack 수집 실패는 회차 중단 사유라 그 회차가 통째로 버려진다. 본문 필드는 `text`가 아니라 `message`다.

Slack Web API를 직접 호출하는 스크립트나 curl 명령을 만들지 않는다. 봇 ✅를 **다는** 것만 예외이며 그것은 `state/deploy-approval-react.sh` 헬퍼가 담당한다.


**도구 이름을 모를 때만 탐색하고, 탐색은 이름만 뽑는다.** `ALL_TOOLS` 필터 결과를 도구 객체째로 출력하면 설명 필드까지 컨텍스트에 박혀 회차가 끝날 때까지 매 턴 다시 읽힌다(2026-09-15 실측: 한 번에 8,920토큰). `x.name`만 출력하고, 같은 회차에서 같은 탐색을 두 번 하지 않는다.

## 1. 회차 시작

`python3 bin/round.py begin code-convention-digest`를 **한 번** 실행한다. dry-run 판정·락 획득·맥락 파일 읽기를 스크립트가 한 번에 처리해 JSON 한 줄로 돌려준다. 이것들을 따로 실행하지 않는다 — 각각이 도구 호출 한 턴이었고 할 일 없는 회차조차 그것만으로 8턴을 썼다.

받는 값은 `live`(dry-run 여부)·`token`·`runStartedEpoch`(토큰과 같은 값)·`context`(맥락 파일 `state/gate/context.code-convention-digest.json` 내용, 없으면 null)다. `token`을 `TOKEN`으로 보관한다.

`error`가 있으면(`lock-busy`) 그 사유로 **대상 특정 전 실패**를 보고하고 종료한다 — 스크립트가 락을 이미 풀었으므로 release를 부르지 않는다.

`live`가 false면 dry-run이다. 입력 읽기·중복 제거·군집화·상태 판정은 라이브와 같게 수행하되 Slack DM과 `state/code-quality-exposure.json` 쓰기는 수행 예정으로만 보고한다.

## 2. 입력·군집화·DM

ROUTINE-CONFIG를 읽어 해석한다. 상태 루트 또는 입력 파일을 읽을 수 없으면 대상 특정 전 실패로 보고하고 release만 실행한다. `state/code-quality-list.jsonl`이 없거나 비어 있으면 `누적된 해소 지적 로그 없음 — 이번 주 다이제스트 없음`으로 보고하고 종료한다. 이 경우 스킬을 읽지 않는다.

입력은 `occId`로 먼저 중복 제거한다. 같은 `occId`가 여러 줄이어도 하나의 occurrence로만 세며, rule of three의 빈도도 고유 `occId` 수만 쓴다. 이 원장은 읽기 전용이며 수정·압축·정리하지 않는다. 입력이 확인된 시점에 `~/work/harnie/skills/quality-digest/SKILL.md`를 읽어 군집화와 후보 선정 기준을 적용한다. 본문을 복사하지 않는다.

같은 안티패턴·반복 계약 위반·반복 누락을 의미 기준으로 묶고, 1회성·맥락 특수적인 지적은 제외한다. 고유 occurrence 3건 미만 군집은 후보로 승격하지 않는다. 후보마다 대표 예시 2~3개(`project/repository#PR: 요약`), 빈도, 가장 적합한 `lint|CI|criteria` 메커니즘 하나, false-positive 위험을 정리한다. 특정 lint 규칙·설정 스니펫을 만들거나 레포 설정을 읽지 않는다.

`state/code-quality-exposure.json`을 읽는다. 없으면 `[]`로 취급한다. 후보는 내용상 같은 기존 항목과 병합해 id를 유지하고 `frequency`, `examples`, `lastSeenAt`을 갱신한다. 새 후보는 kebab-case 요약 id와 `exposureCount:0`, `status:"active"`로 만든다. `active`이면서 한 번 이상 노출된 후보는 `lastMessageTs`의 DM 스레드를 읽어 `lastExposedAt` 이후 ROUTINE-CONFIG의 사용자 답글이 있는지 확인한다. 답글이 있으면 `adopted`로 바꾸고 이번 발송에서 제외한다. 답글이 없고 `exposureCount`가 이미 3이면 `expired`로 바꾸고 이번 발송에서 제외하며 라이브 저장 시 배열에서 제거한다. 나머지와 새 후보는 발송 대상이다.

발송 대상이 있으면 한국어 DM을 작성한다. 제목은 `이번 주 팀 컨벤션 승격 후보`이며 후보별 문제 요약, 대표 예시, 빈도, 제안 메커니즘, false-positive 위험을 간결히 쓴다. 신규과 재노출 후보 및 재노출 횟수를 구분하고, 채택은 사용자 선택이며 자동 반영하지 않는다고 명시한다. 라이브에서는 lock check 뒤 `slack_send_message`로 ROUTINE-CONFIG의 사용자 Slack user ID를 channel로 사용해 DM을 보낸다. 응답 TS를 얻은 각 발송 후보만 `exposureCount`를 1 증가시키고 `lastExposedAt`, `lastMessageTs`를 갱신한다.

adopted·expired 판정만 있고 발송 대상이 없더라도 라이브에서는 그 상태 변경을 반영한다. 상태 배열을 바꿀 때는 lock check 뒤 tmp 파일 후 원자 교체로 `state/code-quality-exposure.json`만 쓴다. `code-quality-list.jsonl`은 어떤 경우에도 쓰지 않는다. dry-run에서는 DM 전문과 상태 변경 예정만 보고한다.

## 3. 상태 기록

외부 DM과 노출 상태 갱신은 위 단계의 라이브 경로에서만 한다. DM 발송 또는 exposure 저장 실패는 실패로 보고하고, 입력 원장은 변경하지 않는다.

## 4. 회차 종료와 보고

정상 경로에서는 `python3 bin/round.py finish code-convention-digest "$TOKEN"`를 **한 번** 실행한다. 스크립트가 lock check → 락 해제를 한 번에 처리한다. `error`가 `lock-lost`면 소유권을 잃은 것이라 아무것도 하지 않았다는 뜻이다. `lock.sh release`·`precheck.py commit`·`pr-session.sh sweep`을 따로 부르지 않는다.

한국어 보고에는 고유 occurrence 수, 군집 수와 rule-of-three 미달 수, 신규·재노출 후보와 노출 횟수, adopted·expired, DM 발송과 요지, exposure 저장 여부, dry-run 수행 예정과 실패 단계를 포함한다.
