# CLAUDE.md / AGENTS.md — 공통 전역 지침

> **정본**: `~/workspace/agent-ops/claude/CLAUDE.md` (repo `qnamy/agent-ops`). `~/.claude/CLAUDE.md`(Claude Code)와 `~/.codex/AGENTS.md`(Codex)가 이 파일을 심링크로 공유한다 — 한 곳만 수정하면 두 도구에 동시 적용된다.
> **[Claude Code 전용]** 표시가 붙은 절은 Claude Code에서만 적용하고, Codex에서는 무시한다.

## 응답 언어

- 한국어로 응답한다.

---

## 작업별 참조 문서 (필요 시 해당 파일을 읽고 그 규칙을 따른다)

아래는 특정 요청이 올 때만 필요한 절차라 별도 파일로 분리했다. 해당 트리거를 만나면 그 파일을 읽어 규칙대로 수행한다.

- **커밋 / 푸시 / PR 생성 / 리뷰요청 전송** ("커밋해줘", "푸시해줘", "PR 생성해줘", "리뷰 요청해줘" 등) → `~/workspace/agent-ops/guidelines/GIT.md` (컨텍스트별로 회사=`~/Tradlinx/GIT-PR.md`·`REVIEW-REQUEST.md`로 라우팅)
- **PR 리뷰 · 코드리뷰 · 댓글해결** ("PR 리뷰해줘", "PR {id} 봐줘", "리뷰해줘", "댓글 해결해줘" 등) → 기준(무엇을·왜 지적하는가)은 harnie `pr-review` 스킬(`~/Tradlinx/harnie/skills/pr-review/SKILL.md`), 댓글 해소 검증 방법론은 harnie `comment-resolve` 스킬. **회사(ADO) 실행 절차**(조회·댓글·멘션·투표)는 `~/Tradlinx/PR-ADO.md`. **로컬 코드리뷰**(PR 번호 없음)는 절차 문서 없이 pr-review 기준으로 직접 리뷰한다 — 기본 범위는 현재 브랜치의 `main` 대비 변경(미커밋만 원하면 워킹 트리, 특정 커밋 지정 시 그 커밋만), 결과는 심각도 순으로 정리하고 수정은 사용자 확인 후 적용.
- **비자명한 신규 코드 작성** (새 기능·모듈·복잡한 로직) → harnie 빌더 지침 `~/Tradlinx/harnie/agents/harnie-builder.md` (아래 §코딩 가이드라인에 종속. 루프 전용 절 — 설계 파일 경로 참조·응답 분량·`${CLAUDE_PLUGIN_ROOT}` 검증 티어 경로 — 은 직접 작업에서 무시)
- **아키텍처 설계·검토** ("아키텍처 설계해줘", "시스템 설계해줘", "아키텍처 설계 리뷰해줘" 등 시스템 경계·컨테이너·데이터 소유권·기술 선택에 관한 요청) → 게이트·작업 원칙은 `~/Tradlinx/harnie/agents/harnie-designer.md`, 출력 계약은 `~/Tradlinx/harnie/instructions/design-authoring-arch.md`
- **상세 설계·검토** ("상세 설계해줘", "구현 설계해줘", "상세 설계 리뷰해줘" 등 특정 서비스·모듈·API·DB·구현 로직에 관한 요청) → 게이트·작업 원칙은 `~/Tradlinx/harnie/agents/harnie-designer.md`, 출력 계약은 `~/Tradlinx/harnie/instructions/design-authoring-detail.md`
- **설계 라우팅:** 설계 산출물의 작성·검토 요청은 위의 일반 PR·코드리뷰 트리거보다 우선한다. "설계서 써줘"·"설계 리뷰해줘"·"컴포넌트 설계해줘"처럼 아키텍처/상세 설계가 모두 가능한 표현이면 대상을 한 번 확인한 뒤 해당 고도(altitude)의 출력 계약 문서만 읽는다. harnie 루프 전용 절(레퍼런스 게이트의 rev-N·출력 경로 계약·오케스트레이터 위임 형식)은 직접 작업에서 무시하고, 출력은 한국어로 한다.

---

## 명령 실행 주의 (권한 프롬프트 회피) [Claude Code 전용]

- **`python3 -c "..."` 안에 줄바꿈 + `#` 주석을 쓰지 않는다.** 이 패턴은 Claude Code 보안 가드("Newline followed by # ... hide arguments from path validation")에 걸려 **allow 규칙으로도 자동승인이 안 되고 매번 권한 프롬프트가 뜬다.** (자동 루틴에서는 실행이 멈춘다.)
- tool 결과 파일(예: `tool-results/*.txt`)이나 JSON을 파싱할 때:
  1. 가능하면 **`Read` 툴로 읽어** 컨텍스트에서 직접 처리한다 (셸 파싱 자체를 피함).
  2. 꼭 python이 필요하면 **한 줄로** 쓰고 `#` 주석을 넣지 않는다. 여러 줄/주석이 필요한 스크립트는 **`.py` 파일로 Write한 뒤 `python3 파일.py`로 실행**한다 (인라인 `-c` 금지).
- **자동승인 받을 Bash 명령에 셸 확장·복합명령을 쓰지 않는다.** `; echo $?`, `&& echo ...`, `$?`·`$(...)`·`` `...` `` 같은 확장이 들어가면 보안 가드("Contains simple_expansion / command_substitution" 등)에 걸려 allow 규칙으로도 자동승인이 안 되고 매번 프롬프트가 뜬다. (전역 `settings.json`의 PreToolUse 훅이 `&&`·`;`·`||`·명령치환·백틱을 포함한 Bash 명령을 자동 차단한다 — 단일 명령 여러 개로 나누거나 `.sh` 파일로 Write 후 `bash 파일.sh`로 실행한다.)
  - **파일 존재/내용 확인은 `Read` 툴로 한다** (`test -s … ; echo $?` 금지). 굳이 셸이 필요하면 `test -s 파일` 처럼 **단일 명령**만 쓰고 `; echo $?` 같은 꼬리를 붙이지 않는다 (종료코드는 tool 결과에 이미 나온다).

---

## 토큰 절약

품질을 해치지 않는 선에서 토큰 사용을 최소화한다. **품질·정확성과 충돌하면 품질이 우선.**

- **부분 읽기**: 큰 파일은 Grep으로 위치를 좁힌 뒤 offset/limit으로 해당 구간만 Read한다. 전체 Read는 파일이 작거나 전체 구조 파악이 꼭 필요할 때만.
- **재읽기 금지**: 같은 세션에서 이미 읽은 파일을 다시 읽지 않는다. Edit/Write 직후 확인 목적의 재읽기도 하지 않는다(실패하면 툴 에러로 드러난다).
- **탐색은 좁혀서**: 파일을 하나씩 열어보며 찾지 않는다. Grep/Glob으로 후보를 좁힌 뒤 필요한 것만 읽는다.
- **위임 우선 [Claude Code 전용]**: 개발 작업은 가급적 harnie(`/harnie:dev*`)로 수행한다(모델 배정은 harnie가 관리). harnie 밖 직접 작업에서 실질 작업(탐색·구현·기계적 편집·초안·리뷰)을 위임할 때는 `~/workspace/agent-ops/claude/delegation.md`를 읽고 그 티어(GPT 우선·Claude 폴백)대로 배분한다. **harnie 실행 중에는 delegation.md를 읽지도 적용하지도 않는다.**
- **출력 간결**: 응답은 결론+필요한 근거만. 읽은 코드·문서 전문을 응답에 다시 인용하지 않는다. 출력이 큰 명령은 필터링해 실행한다(`--quiet`, `tail`, `grep` 등).
- **참조 문서는 on-demand**: 트리거 없이 참조 문서(GIT.md·PR-ADO.md·delegation.md·harnie 지침 등)를 미리 읽지 않는다. 읽더라도 해당 작업에 필요한 문서 하나만.

---

## 코딩 가이드라인

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

> 비자명한 신규 코드(새 기능·새 모듈·복잡한 로직)를 쓸 때는 harnie 빌더 지침(`~/Tradlinx/harnie/agents/harnie-builder.md`)의 접근법을 함께 적용한다. 빌더 지침은 아래 §1~4에 종속되며, 충돌 시 아래 규칙이 우선한다. 기존 코드 편집·소규모 변경은 그 흐름 대신 §3 Surgical Changes를 따른다.

### 1. Think Before Coding

**Don't assume. Don't hide confusion. Surface tradeoffs.**

Before implementing:
- State your assumptions explicitly. If uncertain, ask.
- If multiple interpretations exist, present them - don't pick silently.
- If a simpler approach exists, say so. Push back when warranted.
- If something is unclear, stop. Name what's confusing. Ask.

### 2. Simplicity First

**Minimum code that solves the problem. Nothing speculative.**

- No features beyond what was asked.
- No abstractions for single-use code.
- No "flexibility" or "configurability" that wasn't requested.
- No error handling for impossible scenarios.
- If you write 200 lines and it could be 50, rewrite it.

Overengineering is a defect, not a virtue:
- No premature optimization. Discuss Big-O or optimize only when performance actually matters (hot path, large N, explicit constraint).
- Apply DRY/SOLID only after the rule of three. No preemptive interfaces or abstractions for a single call site.
- Defensive coding belongs at trust boundaries only (external input, API/DB/network responses, untrusted data). Don't blanket internal calls with null checks, and never let "robustness" excuse code growth.

Ask yourself: "Would a senior engineer say this is overcomplicated?" If yes, simplify.

### 3. Surgical Changes

**Touch only what you must. Clean up only your own mess.**

When editing existing code:
- Don't "improve" adjacent code, comments, or formatting.
- Don't refactor things that aren't broken.
- Match existing style, even if you'd do it differently.
- If you notice unrelated dead code, mention it - don't delete it.

When your changes create orphans:
- Remove imports/variables/functions that YOUR changes made unused.
- Don't remove pre-existing dead code unless asked.

The test: Every changed line should trace directly to the user's request.

### 4. Goal-Driven Execution

**Define success criteria. Loop until verified.**

Transform tasks into verifiable goals:
- "Add validation" → "Write tests for invalid inputs, then make them pass"
- "Fix the bug" → "Write a test that reproduces it, then make it pass"
- "Refactor X" → "Ensure tests pass before and after"

For multi-step tasks, state a brief plan:
```
1. [Step] → verify: [check]
2. [Step] → verify: [check]
3. [Step] → verify: [check]
```

Strong success criteria let you loop independently. Weak criteria ("make it work") require constant clarification.

---

**These guidelines are working if:** fewer unnecessary changes in diffs, fewer rewrites due to overcomplication, and clarifying questions come before implementation rather than after mistakes.
