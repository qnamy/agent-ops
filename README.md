# agent-ops

Claude Code와 Codex를 **하나의 지침 체계로 묶어 운영**하는 개인 AI 운영 리포지토리.
전역 지침의 정본, 도구 간 동기화 구조, 그리고 상시 자동화 루틴의 아키텍처·템플릿을 담는다.

> 자매 프로젝트 [harnie](https://github.com/qnamy/harnie)가 **하네스 엔지니어링**(크로스-모델 빌드/리뷰 루프, 스킬 허브)이라면,
> agent-ops는 그 하네스를 포함한 도구들을 **일상 업무에서 어떻게 운영하는가**(지침 라우팅 · 토큰 경제 · 자동화)를 다룬다.

## 구성

```
claude/
├── CLAUDE.md        # 전역 지침 정본(영문) — Claude(~/.claude/CLAUDE.md)와 Codex(~/.codex/AGENTS.md)가 심링크로 공유
└── delegation.md    # 위임·모델 티어 매칭 규칙 (on-demand 로드)
guidelines/
└── GIT.md           # 커밋·푸시·PR 라우팅 (회사/개인 컨텍스트 자동 판별)
routines/
├── README.md        # "Claude 트리거 + GPT 실행" 루틴 아키텍처 (핵심 문서)
└── templates/       # 루틴 5종 지시서 + wrapper + 디스패처 (새니타이즈 템플릿)
scripts/
├── sanitize.py      # 라이브 루틴 문서 → 템플릿 결정적 치환 + 유출 검사 내장 (실패 시 exit 1)
├── sync-templates.sh# 치환 → 유출검사 → 변경 시 로컬 자동 커밋 (푸시는 사람이 확인 후)
└── hook-routine-sync.py # Claude Code PostToolUse 훅 — 라이브 루틴 수정 감지 시 위 동기화 자동 실행
```

템플릿은 라이브 루틴 문서의 치환본이며, PostToolUse 훅이 라이브 수정을 감지해 자동으로 재생성·커밋한다.
공개 관문(push)만 사람이 남는다 — 자동 치환이 새 유형의 식별자를 놓치는 사고를 구조적으로 막기 위해서다.
훅 등록 조각은 [scripts/hook-routine-sync.py](scripts/hook-routine-sync.py) 상단 주석에 있다.

## 설계 원칙

1. **정본은 하나, 사본은 없다** — 지침은 이 레포의 파일이 유일한 정본이고, 각 도구는 심링크·절대경로 참조로 같은 파일을 읽는다. "가져오기"식 스냅샷 복사는 드리프트를 만들기 때문에 쓰지 않는다.
2. **도구 중립 코어 + 도구 전용 마킹** — 공통 지침은 그대로 두 도구에 적용되고, 한쪽에만 유효한 절은 `[Claude Code only]`처럼 명시해 다른 쪽이 무시한다.
3. **영문 정본 + 한국어 미러** — 지침 문서는 영문(`*.md`)이 실행 정본이고, 각 문서의 한국어 미러(`*-ko.md`)를 쌍으로 유지한다(harnie와 동일한 언어 정책). 정본을 수정하면 같은 변경에서 미러도 갱신한다 — 이 의무 자체가 상시 로드되는 정본에 명시돼 있어 어느 세션이 지침을 고치든 미러 동기화를 빠뜨릴 수 없다.
3. **판단 기준의 SSOT는 harnie** — 코드리뷰 기준(pr-review)·설계 계약(design-authoring)·코딩 접근법(builder)은 harnie가 정본이고, 여기의 지침은 그 문서로 라우팅만 한다. 같은 기준을 사람 요청·자동 루틴·개발 루프가 전부 공유한다.
4. **토큰 경제** — 상시 로드되는 지침은 얇게, 상세 규칙은 트리거 시에만 읽는 on-demand 문서로. 자동 루틴은 저비용 트리거(Haiku)와 실행(GPT)을 분리한다. → [routines/README.md](routines/README.md)
5. **공개 가능한 구조** — 지시서에 식별값을 하드코딩하지 않고 실행 시 주입(ROUTINE-CONFIG)하므로, 운영 문서를 거의 그대로 템플릿으로 공개할 수 있다. 회사 내부 정보(도메인 맵·문제 인벤토리 등)는 이 레포 밖 로컬에만 둔다.

## 새 머신 셋업

```bash
git clone https://github.com/qnamy/agent-ops.git ~/workspace/agent-ops
```

```bash
ln -sf ~/workspace/agent-ops/claude/CLAUDE.md ~/.claude/CLAUDE.md
```

```bash
ln -sf ~/workspace/agent-ops/claude/CLAUDE.md ~/.codex/AGENTS.md
```

## License

MIT
