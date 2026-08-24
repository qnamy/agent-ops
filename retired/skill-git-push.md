# [은퇴] claude.ai 사용자 스킬 "git-push" (2026-08-24 제거)

> 제거 사유: 전역 라우터(CLAUDE.md → GIT.md → GIT-PR.md)의 완전 부분집합이면서 컨텍스트 판별이 없어, "커밋해줘" 트리거를 가로채 비회사 레포에도 Jira 형식을 적용하거나 규약 미준수 커밋을 유발(2026-08-24 준수율 프로브에서 실증 — rg-grep-verification 메모리 참조). 고유 요소였던 Jira 티켓 커밋 형식은 GIT-PR.md가 티켓 부재 폴백까지 포함해 상위호환으로 보유. 복원이 필요하면 아래 원문을 claude.ai 스킬로 재등록.

## 원문 (제거 시점 스냅샷)

현재 브랜치의 변경사항을 커밋하고 push하는 작업을 수행해줘.

### 순서

1. `git branch --show-current`로 현재 브랜치명을 확인해.
   - 브랜치명은 `{type}/{Jira-Ticket-No}` 형태야. (예: `fix/PROJ-123`, `feat/PROJ-456`, `refactor/PROJ-789`)
   - `{type}`은 fix, feat, refactor, chore, docs, style, test, perf, ci 등이 될 수 있어.
   - `{Jira-Ticket-No}`는 브랜치명에서 `/` 뒤의 부분이야.
2. `git diff --staged`와 `git diff`를 확인해서 변경사항을 파악해.
   - 스테이징되지 않은 변경사항이 있으면 `git add -A`로 모두 스테이징해.
3. 변경사항을 분석해서 커밋 메시지를 작성해.
   - 제목 형식: `{type}: [{Jira-Ticket-No}] 변경사항 요약`
   - 변경사항 요약은 한국어로, 100자 이내로 작성해.
   - 명령형 어투로 작성해. (예: "로그인 API 응답 처리 로직 수정", "사용자 프로필 페이지 추가")
   - 필요하면 본문(body)도 추가해서 상세 내용을 설명해.
4. `git commit`을 실행해.
5. push할 remote를 결정해.
   - `git remote`로 remote 목록을 확인해.
   - `upstream`이 있으면 `upstream`으로, 없으면 `origin`으로 push해.
   - `git push {remote} {현재브랜치명}`을 실행해.
6. 완료 후 커밋 해시와 push 결과를 알려줘.
