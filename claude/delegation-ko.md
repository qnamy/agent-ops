# delegation.md — 위임 우선 + 모델 티어 매칭 (Claude Code 전용)

> 전역 지침 §토큰 절약에서 분리한 상세 규칙. **harnie(`/harnie:dev*`) 실행 중에는 이 문서를 읽지도, 적용하지도 않는다** — 모델 배정은 harnie가 관리한다. 이 규칙은 harnie 밖 직접 작업(지침·harnie 자체 수정, 검색·조사 등)에서 실질 작업을 위임할 때만 적용한다.

실질 작업(탐색·구현·기계적 편집·초안·리뷰)은 가능한 한 서브에이전트/GPT-MCP로 위임하고, 고비용 메인 세션은 오케스트레이션·최종 판단에 집중한다. 어느 정도 추론이 필요한 작업도 메인이 떠안지 말고 아래 티어로 나눠 보낸다.

- **GPT 우선, 실패 시 Claude 폴백**: 기본 위임처는 GPT(codex MCP) — Claude usage를 소모하지 않는다. 쓰기가 필요하면 `sandbox=workspace-write`를 준다. Claude 서브에이전트는 (a) codex가 실패·거부하거나 구조적 제약에 걸릴 때(worktree git 메타데이터 쓰기, 이 세션의 MCP 툴(Slack·ADO 등)이 필요한 작업), (b) 크로스-모델 리뷰의 Claude 차례(GPT 산출물 검토)일 때 쓴다.
- **Claude 서브에이전트**: 기계적·대량 작업(번역 미러·반복 편집·단순 탐색)=Haiku(`claude-haiku-4-5`), 일반 구현·중간 추론=Sonnet(`claude-sonnet-5`), 고난도 판단·리뷰=Opus(`claude-opus-5`).
- **GPT (codex MCP)**: 고난도 추론=Sol(`gpt-5.6-sol`), 중간 추론·일반 구현=Terra(`gpt-5.6-terra`), 경량=Luna(`gpt-5.6-luna`), 기계적·대량=Spark(`gpt-5.3-codex-spark`).
- **Agent Teams**: 서브에이전트에서 에이전트 팀으로 전환하는 기준은 `~/workspace/agent-ops/claude/agent-teams.md`가 관장한다; 위 Claude 티어는 팀원에게도 적용된다 — 스폰 시 각 팀원의 모델을 항상 명시한다.
- **예외**: 단일 소규모 편집·단순 조회처럼 위임 오버헤드(프롬프트 작성+결과 수신)가 작업 자체보다 큰 것은 직접 한다.
