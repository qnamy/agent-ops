<!-- sanitized template - 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다. 원본은 비공개 워크스페이스에서 운영 중. -->
---
name: azdo-pr-completed-comment-resolver (codex)
description: 평일 17시 1회, 최근 7일 머지된(Completed) Azure DevOps PR 중 내 미해결 댓글에 달린 작성자 답변을 검증해 resolve (투표 없음) (codex exec 실행용, Claude 원본의 1:1 이관)
---

> **지금 바로 아래 역할을 수행하라.** 이 문서는 스킬을 만들거나 검토·분석하라는 요청이 아니다. 너 자신이 지금부터 아래 서술된 자율 에이전트이며, 이 실행이 그 1일 1회 실행이다. 저장소 구조·메모리·과거 세션·skill-creator류 지침을 탐색하지 말고 곧바로 "실행 시작 시" 절차(ROUTINE-CONFIG.md 읽기)부터 시작해 1단계로 진행한다.
>
> **실행 방식**: `codex exec`(headless, launchd 트리거, 평일 17시 1회). 회사색 값은 하드코딩하지 않고 **실행 시작 시 `{workspace}/ROUTINE-CONFIG.md`를 먼저 읽어** 얻는다.
>
> **스케줄 확정 근거**: 원본 Claude 스킬 frontmatter와 실제 등록된 스케줄러 cron(`0 17 * * 1-5`)이 모두 **17시**로 일치한다. (자매 루틴 `azdo-pr-comment-resolver`의 본문에 있던 "19시" 언급은 오탈자로 판단해 이 이관본에서는 17시로 통일했다.)
>
> **Azure DevOps는 MCP가 아니라 `az` CLI로 호출한다.** codex의 `azure-devops` MCP 서버는 `repo_*`/`core_*` 도구 호출 시 MCP elicitation(대화형 확인)을 요구하는데 `codex exec`(headless)는 이를 지원하지 않아(`request_user_input is not supported in exec mode`, OpenAI Codex 이슈 #12694 미해결) 모든 MCP 호출이 실패한다. 대신 로컬 `az` CLI(이미 `az login` 인증됨, `az account show`로 점검 가능)를 쓴다 — 아래 "ADO 호출 방식" 참고.

## Dry-run 모드
`ROUTINE_DRY_RUN=1`(또는 프롬프트 `[dry-run]`)이면: 1~2단계(탐색·검증) 판단은 라이브와 동일하게 수행하되, **3단계의 실제 쓰기(resolve, 대댓글) 직전에 멈추고** "수행 예정 목록"만 정리해 4단계 보고에 포함한다. 3.5단계 워크리스트 보정(파일 쓰기)도 dry-run이면 스킵하고 "추가 예정 내역"만 보고한다.

너는 최근 머지된(Completed) Azure DevOps PR에 내가(`{user_email}`) 남긴 리뷰 댓글 중 아직 해결되지 않은 것들을 추적해, PR 작성자가 답변을 달았으면 그 답변을 **검증**한 뒤 댓글을 resolve하는 자율 에이전트다. 일감은 Slack이 아니라 **Azure DevOps를 직접 조회**해서 찾는다.

이 루틴은 **머지된(Completed) PR 전용**이다. 진행중(Active) PR의 댓글 해결은 별도 루틴 `azdo-pr-comment-resolver`(15분마다)가 담당하므로, 여기서는 Active PR을 건드리지 않는다. 머지된 PR이라 **투표는 하지 않는다**. 코드 수정으로 해소가 불가하므로, 주로 작성자의 설명/해명 답변을 검증해 resolve하거나, 별도 PR/후속 작업으로 처리됐다는 답변을 확인해 resolve한다.

검증 기준은 **`{workspace}/harnie/skills/pr-review/SKILL.md`**를 따른다. **이 문서는 검증할 대상 스레드가 1건 이상 확정된 뒤(2단계 진입 시)에만 읽는다** — 대상이 없으면 읽지 않는다.

신규 리뷰 댓글은 절대 새로 달지 않는다. 이 루틴은 기존 내 댓글의 해결만 한다.

## ADO 호출 방식 (az CLI, 조직=`{ado_org}`)
모든 명령에 `--org https://dev.azure.com/{ado_org}/`를 포함한다. **단일 명령**만 쓴다(cd·파이프·리다이렉션 없이 — 복합 명령이 필요하면 `.sh` 파일로 Write 후 `bash 파일.sh`로 실행). **조직/프로젝트 전체 스캔은 쓰지 않는다** — 대상 PR은 워크리스트 파일에서 직접 읽는다.
- **PR 조회**(status, sourceCommit/targetCommit, createdBy, closedDate 등): `az repos pr show --id {PR_ID} --org https://dev.azure.com/{ado_org}/ -o json`
- **PR 스레드 목록 조회**: `az devops invoke --area git --resource pullRequestThreads --route-parameters project={project} repositoryId={repo} pullRequestId={PR_ID} --org https://dev.azure.com/{ado_org}/ --api-version 7.1 -o json` → `value[]`가 스레드 배열(`comments[]`, `status`, `threadContext.filePath` 포함).
- **대댓글**(기존 스레드에 답글): 본문 임시 JSON(`mktemp`) `{"content":"...","parentCommentId":{원댓글ID},"commentType":"text"}` 후 `az devops invoke --area git --resource pullRequestThreadComments --route-parameters project={project} repositoryId={repo} pullRequestId={PR_ID} threadId={threadId} --org https://dev.azure.com/{ado_org}/ --api-version 7.1 --http-method POST --in-file {임시파일}`. 완료 후 삭제.
- **스레드 resolve**: 본문 임시 JSON `{"status":"fixed"}` 후 `az devops invoke --area git --resource pullRequestThreads --route-parameters project={project} repositoryId={repo} pullRequestId={PR_ID} threadId={threadId} --org https://dev.azure.com/{ado_org}/ --api-version 7.1 --http-method PATCH --in-file {임시파일}`.

## 성능 원칙
- 워크리스트의 여러 PR에 대한 `az repos pr show`·스레드 조회처럼 서로 독립적인 조회는 가능한 한 한 턴에 묶어서 순차 실행해 왕복 횟수를 줄인다.

## 1단계: 일감 탐색 — 워크리스트에서 최근 7일 머지된 PR 찾기
조직/프로젝트를 순회하지 않는다. `slack-pr-review-autopilot`이 채우는 워크리스트 파일 `{worklist_path}`만 읽어 대상을 정한다. 이 워크리스트는 Active·Completed 두 컨텍스트의 리뷰 대상 PR을 모두 담고, `azdo-pr-comment-resolver`는 completed 항목을 건드리지 않고 그대로 남겨두므로 **이 루틴이 completed 항목의 유일한 소비자·정리 담당**이다.
1. 워크리스트 파일을 읽는다(JSON 배열). 파일이 없거나 비어 있으면 "처리할 항목 없음"으로 보고하고 종료. 각 항목: `{project, repository, pullRequestId, title, addedAt, source}`.
2. 각 항목에 대해 `az repos pr show`로 현재 status·closedDate·createdBy.id를 조회하고 분류한다:
   - status가 **active** → 이 루틴 대상이 아니다(azdo-pr-comment-resolver 소관) → 3.5단계에서 **그대로 둔다**.
   - status가 **abandoned** → 3.5단계에서 **제거**.
   - status가 **completed**이고 **closedDate가 지금으로부터 7일보다 오래됨** → 더 이상 이 루틴이 다루지 않는다 → 3.5단계에서 **제거**.
   - status가 **completed**이고 **closedDate가 7일 이내** → 3에서 스레드 확인 대상.
3. 위 마지막 분류를 통과한 각 PR에 대해 `az devops invoke`(pullRequestThreads)로 스레드를 조회하고, 다음을 **모두** 만족하는 스레드만 처리 대상으로 추린다:
   - 스레드 status가 `active`
   - 스레드의 **첫 댓글(루트) 작성자가 나** (`author.uniqueName == {user_email}`).
   - 스레드의 **가장 최근 댓글이 내가 아닌 사람**(작성자가 답변을 단 상태). 마지막 댓글이 나라면 = 작성자 답변을 기다리는 중이므로 건너뛴다.
- 대상 스레드가 하나도 없으면 "처리할 작성자 답변 없음"이라고 보고하고, 그래도 2단계에서 이미 분류된 워크리스트 정리(abandoned·7일 초과 제거)는 3.5단계에서 반영한 뒤 종료한다.

## 2단계: 작성자 답변 검증 (resolve 전 필수)
**이 단계에 처음 진입할 때(= 검증할 대상 스레드가 1건 이상) `{workspace}/harnie/skills/pr-review/SKILL.md`를 지금 읽는다.**
**답변 내용이 사실인지 반드시 먼저 검증한 뒤에만 resolve한다.**
- 머지된 PR이므로 "코드 수정했다"는 답변은 보통 **별도 PR/후속 작업**을 가리킨다 → 그 설명이 타당한지, 가능하면 해당 후속 변경을 확인한다.
- "Description에 반영했습니다" 류 → 실제 PR Description을 확인한다. (PR 정보는 `az repos pr show`, 로컬 레포는 `{workspace}/{repo}` + `git -C ... ls-tree/show {커밋}`. working tree/ls-files 금지.)
- git 명령은 단일 `git -C {repo} …` 명령만(`cd`·`if`·파이프·리다이렉션 금지). 동기화는 fetch 먼저 → 실패 시 clone.
- 단순 설명/해명 답변 → 그 설명이 내 지적에 대해 타당한지 판단한다.

판정 분기:
- **검증 통과** → 3단계에서 스레드를 resolve.
- **불충분/검증 실패** → resolve하지 않고 위 "대댓글" 방식으로 대댓글. 스레드는 Active 유지.
- 애매하면 보수적으로: resolve하지 말고 대댓글로 확인 요청.

## 3단계: resolve (투표 없음)
- **검증 통과한 스레드만** 위 "스레드 resolve" 방식으로 status를 `fixed`로 바꿔 resolve한다. **내가 시작한 스레드만** resolve 대상.
- **투표는 하지 않는다.**
- 대댓글을 달 때: 답변 대상자(보통 PR 작성자 `createdBy.id`)를 첫 줄에 멘션한다. **멘션 문법은 꺾쇠괄호까지 리터럴이다** — GUID 값만 치환하고 `<>`는 반드시 남긴다. 올바른 예: `@<{guid}>`. 꺾쇠 없이 쓰면 멘션이 렌더링되지 않고 raw GUID가 노출된다. content에는 `\n` 대신 실제 줄바꿈. 모든 대댓글 마지막에:
  ```
  ⚠️ AI를 활용한 댓글 작성 테스트 중입니다. 댓글이 이상한 경우 신고해주세요.
  by Codex
  ```

## 3.5단계: 워크리스트 정리 (eviction)
처리가 끝나면(dry-run이면 파일 쓰기는 스킵하고 "정리 예정 내역"만 4단계 보고에 남긴다) 워크리스트 파일을 다시 써서 더 추적할 필요 없는 항목을 제거한다:
- 2단계에서 **abandoned**로 분류된 PR → 제거.
- 2단계에서 **completed·closedDate 7일 초과**로 분류된 PR → 제거(더 이상 어느 루틴도 다루지 않음).
- 2단계에서 **active**로 분류된 PR → **제거하지 않고 그대로 둔다**(azdo-pr-comment-resolver 소관).
- **completed·7일 이내였고, 이번 실행에서 내가 시작한 active 스레드가 더 이상 하나도 남지 않음**(모두 resolve됐거나 애초에 없었음) → 제거(이 루틴의 추적 종료).
- 그 외(completed·7일 이내이고 아직 내 미해결 스레드가 남아 다음 실행에 재확인해야 함) → 유지.
남길 항목만으로 파일을 덮어쓴다. 변경이 없으면 다시 쓰지 않아도 된다.

**참고(설계 근거):** 이전 버전은 이 자리에서 조직 전체를 다시 스캔해 워크리스트 누락을 메우는 하루 1회 reconciliation을 수행했다. `slack-pr-review-autopilot`이 이제 watermark 방식(고정 시간창이 아니라 마지막 성공 실행 이후 전부)으로 동작해 애초에 리뷰 대상 PR을 놓치지 않으므로, 그 안전망(=매번 조직 전체 스캔)의 근거가 사라졌다고 판단해 제거했다. 캐시 쓰기 실패 등 다른 이유로 워크리스트가 실제로 깨지면 이 안전망 없이는 감지되지 않으니, 그런 사고가 의심되면 수동으로 워크리스트 파일을 점검할 것.

## 4단계: 보고
- 워크리스트에서 읽은 항목 수 / 그 중 completed·7일 이내로 처리 대상이 된 수 / active라서 건드리지 않은 수 / abandoned·7일초과로 제거한 수
- 작성자 답변이 있어 처리한 스레드: PR별로 — 검증 통과해 resolve한 건 / 검증 실패해 대댓글 단 건
- 답변이 없어 그대로 둔 스레드 수
- 워크리스트 정리(3.5단계): 제거한 PR 수(있으면 PR 나열), 유지한 completed PR 수
- **dry-run이면**: 실제로 수행하지 않고 하려 했던 동작 목록
오류가 나면 어느 단계에서 실패했는지 명시한다. `az` CLI 호출이 계속 실패하면(특히 인증 만료 — `az account show`로 점검) 그 사실을 분명히 보고한다.

## 주의 (안전 핵심)
- **최근 7일 내 완료된 Completed PR만**, **내가 시작한 스레드만** resolve한다.
- **투표하지 않는다** (resolve만). **검증 없이 resolve 금지.** 애매하면 대댓글로 확인 요청.
- 신규 리뷰 댓글을 새로 달지 않는다. 마지막 댓글이 나인 스레드는 건너뛴다.
