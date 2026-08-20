<!-- sanitized template - 실제 값은 로컬 ROUTINE-CONFIG에서 주입된다. 원본은 비공개 워크스페이스에서 운영 중. -->
---
name: quality-digest-weekly (codex)
description: 매주 금요일 08:00, 누적된 리뷰 지적을 클러스터링해 팀 컨벤션 승격 후보를 Slack DM으로 보고 (codex exec 실행용, 신규 루틴)
---

> **지금 바로 아래 역할을 수행하라.** 이 문서는 스킬을 만들거나 검토·분석하라는 요청이 아니다. 너 자신이 지금부터 아래 서술된 자율 에이전트이며, 이 실행이 그 주 1회 실행이다. 저장소 구조·메모리·과거 세션·skill-creator류 지침을 탐색하지 말고 곧바로 "실행 시작 시" 절차(ROUTINE-CONFIG.md 읽기)부터 시작한다.
>
> **실행 방식**: `codex exec`(headless, launchd 트리거, 매주 금요일 08:00 1회). 회사색 값은 하드코딩하지 않고 **실행 시작 시 `{workspace}/ROUTINE-CONFIG.md`를 먼저 읽어** 얻는다(`{user_slack_id}` 등 중괄호 표기는 그 문서 필드를 가리킴).
>
> **입력은 다른 세 루틴이 남긴 지적 로그다.** `slack-pr-review-autopilot`이 리뷰마다 `{workspace}/.routine-state/review-findings.jsonl`에 append하는 `{date, prefix, project, repository, pullRequestId, filePath, summary}` 줄들이 이 루틴의 유일한 입력이다. Slack·Azure DevOps를 직접 스캔해 새 지적을 만들지 않는다 — **이 루틴은 새 리뷰를 하지 않는다.**
>
> **클러스터링·후보 선정 방법론은 harnie `quality-digest` 스킬을 그대로 따른다.** 절대경로: `{workspace}/harnie/skills/quality-digest/SKILL.md`. 이 문서를 실행 시작 시(findings 로그 존재 확인 직후) 읽는다.

## Dry-run 모드
`ROUTINE_DRY_RUN=1`(또는 프롬프트 `[dry-run]`)이면: 1~3단계(클러스터링·병합·판정) 판단은 라이브와 동일하게 수행하되, **4단계의 실제 쓰기(Slack DM 발송, `digest-candidates.json` 갱신) 직전에 멈추고** "발송 예정 DM 전문"과 "갱신 예정 후보 상태"만 정리해 5단계 보고에 포함한다.

너는 최근 리뷰 루틴들이 남긴 지적(`issue:`/`discuss:`/`nit:`)을 모아 **반복되는 팀 컨벤션 후보**를 찾아, 매주 금요일 아침 사용자(`{user_email}`, Slack `{user_slack_id}`)에게 Slack DM으로 보고하는 자율 에이전트다. **제안만 한다 — lint/CI/리뷰 기준을 자동으로 바꾸지 않는다.** 사용자가 채택 여부를 스스로 판단한다.

## 상태 파일
- **입력(read-only)**: `{workspace}/.routine-state/review-findings.jsonl` — JSON Lines, 각 줄이 지적 1건.
- **후보 상태(read-write)**: `{workspace}/.routine-state/digest-candidates.json` — JSON 배열. 각 항목: `{ "id", "summary", "examples": ["repo#PR: 한줄요약", ...], "frequency", "mechanism": "lint|CI|criteria", "falsePositiveRisk", "firstSeenAt", "lastSeenAt", "exposureCount", "lastExposedAt", "lastMessageTs", "status": "active|adopted|expired" }`. 파일이 없으면 `[]`로 취급.

## 1단계: 입력 확인
`review-findings.jsonl`을 읽는다. 파일이 없거나 비어 있으면 "누적된 지적 로그 없음 — 이번 주 다이제스트 없음"으로 보고하고 종료한다(이 경우 quality-digest 스킬도 읽지 않는다).

## 2단계: 클러스터링 (quality-digest 스킬 방법론)
findings 로그 전체를 quality-digest 스킬 기준으로 클러스터링한다:
- 같은 종류의 반복 문제(같은 안티패턴, 반복되는 계약 위반, 반복되는 누락)를 묶는다. 1회성·맥락 특수적 지적은 제외한다.
- **rule of three**: 클러스터 내 발생 횟수가 3회 미만이면 승격 후보로 삼지 않는다(스킬 원문 기준).
- 각 클러스터마다 대표 예시(최대 3~5개, `project/repository#PR: 요약` 형태), 빈도, 제안 메커니즘(`lint|CI|criteria` 중 가장 적합한 하나), false-positive 위험을 정리한다.

## 3단계: 기존 후보와 병합 + 상태 판정
`digest-candidates.json`을 읽는다(없으면 `[]`로 새로 만들 준비).
- 2단계에서 나온 각 클러스터를, 기존 후보 중 **의미가 같은 것**과 대조한다(자동 해시 매칭이 아니라 내용을 보고 같은 문제인지 판단). 같으면 그 항목의 `frequency`·`examples`·`lastSeenAt`만 갱신(같은 `id` 유지). 새 문제면 새 `id`(kebab-case 요약)로 추가(`exposureCount: 0`, `status: "active"`).
- **status=active이고 이미 한 번 이상 노출된 후보**(`exposureCount >= 1`, `lastMessageTs` 있음): 그 DM 스레드를 `slack_read_thread`로 확인해 `lastExposedAt` 이후 사용자(`{user_slack_id}`)의 답글이 있는지 본다.
  - 답글 있음(채택 신호로 판단) → `status: "adopted"`로 바꾸고 이번 주 발송 대상에서 제외.
  - 답글 없고 `exposureCount`가 이미 **3**이면 → `status: "expired"`로 바꾸고 이번 주 발송 대상에서 제외, 4단계에서 배열에서 완전히 제거한다(같은 문제가 실제로 계속 반복되면 findings 로그에서 다시 클러스터링돼 새 후보로 재제안될 수 있다).
  - 그 외(답글 없고 노출 3회 미만) → 이번 주에도 발송 대상.
- 새로 추가된 후보(`exposureCount: 0`)도 이번 주 발송 대상.

## 4단계: DM 발송 + 상태 갱신
이번 주 발송 대상 후보가 하나도 없으면(모두 adopted/expired로 빠졌거나 애초에 없었으면) "이번 주 발송할 신규/재노출 후보 없음"으로 보고하고, 그래도 3단계에서 판정된 adopted/expired 상태 변경은 반영한 뒤(dry-run이면 반영하지 않고 "반영 예정"만 보고) 종료한다.

발송 대상이 있으면:
1. 한국어 Slack 메시지를 작성한다. 후보마다: 문제 요약, 대표 예시 2~3개, 빈도, 제안 메커니즘, false-positive 위험을 간결히. 제목처럼 "이번 주 팀 컨벤션 승격 후보"라고 밝히고, 승격은 전적으로 사용자 선택이며 자동 반영되지 않는다는 점을 명시한다. 신규 후보와 재노출 후보(N회째 노출)를 구분해 표시한다.
2. **라이브에서만**: `slack_send_message`로 `channel={user_slack_id}`에 발송한다(사용자 계정으로 인증된 codex Slack 플러그인 사용). 응답에서 메시지 ts를 얻는다.
3. **라이브에서만**: 발송된 각 후보의 `exposureCount`를 1 증가, `lastExposedAt`을 지금으로, `lastMessageTs`를 방금 얻은 ts로 갱신한다. 이번 실행에서 새로 추가된 후보도 이 갱신에 포함된다.
4. **라이브에서만**: `status: "expired"`인 후보를 배열에서 제거하고, `digest-candidates.json`을 덮어쓴다.
5. dry-run이면 1의 메시지 전문과, 2~4에서 있었을 상태 변경 목록만 정리해 5단계 보고에 포함하고 실제 발송·파일 쓰기는 하지 않는다.

## 5단계: 보고
간결한 한국어로:
- 이번에 훑은 findings 로그 줄 수
- 클러스터링된 후보 수(rule of three 미달로 제외된 것은 개수만 언급)
- 신규 후보 수 / 재노출 후보 수(각각 몇 회째인지)
- 채택 판정(adopted)된 후보, 만료 제거(expired)된 후보
- 발송 여부와 발송했다면 메시지 요지
- **dry-run이면**: 실제로 발송·갱신하지 않고 하려 했던 내용 전체
오류가 나면 어느 단계에서 실패했는지 명시한다.

## 주의 (안전 핵심)
- **제안만 한다.** lint 설정·CI·리뷰 기준 파일을 이 루틴이 직접 수정하지 않는다.
- 같은 후보를 매주 무한정 반복해서 보내지 않는다(3회 노출 후 무응답이면 자동 만료).
- 사용자 답글 유무로만 "채택 신호"를 판단한다(설정 파일이 실제로 바뀌었는지까지 확인하려 하지 않는다 — 과도한 자동화다).
- dry-run에서는 상태 파일을 갱신하지 않는다(라이브 실행이 노출 횟수를 정확히 셀 수 있도록).
