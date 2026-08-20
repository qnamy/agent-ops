# GIT.md — Git 커밋 · 푸시 · PR 생성 · 리뷰요청 라우팅 규칙

"커밋해줘", "푸시해줘", "PR 생성해줘", "리뷰 요청해줘" 등의 요청 시 아래 규칙을 따른다.

## 컨텍스트 판별

- `git remote get-url upstream`으로 upstream URL을 확인할 수 있으면 upstream을, 없으면 `git remote get-url origin`으로 origin URL을 확인한다.
- remote URL에 `dev.azure.com` 또는 `ssh.dev.azure.com`이 포함되면 **회사**, `github.com`이 포함되면 **개인** 컨텍스트다.
- remote URL로 판별할 수 없을 때만 디렉터리를 보조 신호로 사용한다. `~/Tradlinx` 하위는 회사 컨텍스트일 가능성이 높지만, 개인 GitHub 레포도 있으므로 디렉터리만으로 확정하지 않는다.
- 보조 신호까지 확인해도 모호하면 사용자에게 회사/개인 컨텍스트를 질문한다.

## 공통 규칙

- 커밋 변경사항 요약은 한국어, 100자 이내, 명령형 어투로 작성한다.
- type은 `fix`, `feat`, `refactor`, `chore`, `docs`, `style`, `test`, `perf`, `ci` 중에서 고른다.
- 커밋 전 `git add -A`로 모든 변경사항을 스테이징한다.
- 필요시 본문(body)에 상세 변경 내용을 추가한다.
- push는 `git remote`에 upstream이 있으면 upstream으로, 없으면 origin으로 한다.
- `git push {remote} {현재브랜치}` 형식으로 실행한다.

## 개인 (GitHub) 규칙

- 티켓 번호 규칙은 없다.
- 커밋 제목은 `{type}: 변경사항 요약` 형식으로 작성한다.
- 기본 워크플로는 브랜치를 새로 만들지 않고 `main`에서 직접 커밋·push한 뒤 PR 없이 종료하는 것이다.
- 사용자가 PR 생성을 명시적으로 요청한 경우에만 임시 브랜치를 만들고 PR을 생성한다.
  - PR 제목: `{type}: 요약` (티켓 없음)
  - PR 본문: **변경사항만** 간결히 작성한다.
  - 리뷰요청 단계는 없다.
  - merge 후 임시 브랜치를 삭제한다.

## 회사 (Azure DevOps) 규칙

회사 컨텍스트에서는 `~/Tradlinx/GIT-PR.md`를 읽고 따른다.

PR 본문·리뷰요청 내용 작성 방법론(무엇)은 harnie 플러그인 `pr-delivery` 스킬(`/harnie:pr-delivery`)이 일반화 소스이며, 프로필(제목 규칙·본문 섹션 구성)은 위 컨텍스트별 규칙을 주입값으로 쓴다(선택적 참조).
