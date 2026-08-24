# CLAUDE.md / AGENTS.md — Shared Global Instructions

> **Canonical**: `~/workspace/agent-ops/claude/CLAUDE.md` (repo `qnamy/agent-ops`). `~/.claude/CLAUDE.md` (Claude Code) and `~/.codex/AGENTS.md` (Codex) are symlinks to this file — edit one place and both tools pick it up.
> Sections marked **[Claude Code only]** apply only in Claude Code; ignore them in Codex.
> **Language policy**: English files (`*.md`) are the executable canon in this repo; each has a Korean mirror (`*-ko.md`) for human reading. **Whenever you edit a canonical instruction file, update its `-ko.md` mirror in the same change** (keep content equivalent — never let the two diverge). On conflict or ambiguity, the English canon wins.

## Response Language

- Respond in Korean.

---

## Task-Specific Reference Documents (read the file on trigger, then follow its rules)

These are procedures needed only for specific requests, so they live in separate files. When a trigger matches, read that file and execute per its rules.

- **Commit / push / PR creation / review-request** ("커밋해줘", "푸시해줘", "PR 생성해줘", "리뷰 요청해줘", etc.) → `~/workspace/agent-ops/guidelines/GIT.md` (routes company context to `~/Tradlinx/GIT-PR.md` · `REVIEW-REQUEST.md`)
- **PR review · code review · comment resolution** ("PR 리뷰해줘", "PR {id} 봐줘", "리뷰해줘", "댓글 해결해줘", etc.) → the criteria (what to flag and why) are the harnie `pr-review` skill (`~/Tradlinx/harnie/skills/pr-review/SKILL.md`, plugin `harnie@harnie` installed); the resolution-verification methodology is the harnie `comment-resolve` skill. The **company (ADO) execution procedure** (lookup, comments, mentions, votes) is `~/Tradlinx/PR-ADO.md`. **Local code review** (no PR number) needs no procedure doc — review directly against the pr-review criteria; default scope is the current branch vs `main` (the working tree if only uncommitted changes are wanted; a specific commit if one is named), report findings ordered by severity, and apply fixes only after user confirmation.
- **Non-trivial new code** (new feature, module, complex logic) → harnie builder instructions `~/Tradlinx/harnie/agents/harnie-builder.md` (subordinate to §Coding Guidelines below. Ignore the loop-only parts — design-file path references, response-length budget, the `${CLAUDE_PLUGIN_ROOT}` verification-tier path — when working directly)
- **Architecture design / review** ("아키텍처 설계해줘", "시스템 설계해줘", "아키텍처 설계 리뷰해줘", etc. — requests about system boundaries, containers, data ownership, technology choices) → gates and working principles: `~/Tradlinx/harnie/agents/harnie-designer.md`; output contract: `~/Tradlinx/harnie/instructions/design-authoring-arch.md`
- **Detailed design / review** ("상세 설계해줘", "구현 설계해줘", "상세 설계 리뷰해줘", etc. — requests about a specific service, module, API, DB, implementation logic) → gates and working principles: `~/Tradlinx/harnie/agents/harnie-designer.md`; output contract: `~/Tradlinx/harnie/instructions/design-authoring-detail.md`
- **Design routing:** requests to author or review design artifacts take precedence over the generic PR/code-review triggers above. For phrasing that could mean either altitude ("설계서 써줘", "설계 리뷰해줘", "컴포넌트 설계해줘"), confirm the target once, then read only that altitude's output contract. Ignore harnie loop-only sections (reference-gate rev-N, output-path contract, orchestrator delegation format) in direct work, and write the output in Korean.

---

## Command Execution Cautions (permission-prompt avoidance) [Claude Code only]

- **Never put a newline + `#` comment inside `python3 -c "..."`.** That pattern trips the Claude Code security guard ("Newline followed by # ... hide arguments from path validation"), so it **cannot be auto-approved even by allow rules and prompts every time** (automated routines stall on it).
- When parsing tool-result files (e.g. `tool-results/*.txt`) or JSON:
  1. Prefer the **`Read` tool** and process in context (avoid shell parsing altogether).
  2. If python is truly needed, write it **as a single line** with no `#` comments. For anything multi-line or commented, **Write a `.py` file and run `python3 file.py`** (inline `-c` forbidden).
- **No shell expansion or compound commands in Bash calls that should auto-approve.** `; echo $?`, `&& echo ...`, `$?` · `$(...)` · backticks trip the security guard ("Contains simple_expansion / command_substitution" etc.), so allow rules cannot auto-approve them and a prompt appears every time. (The global `settings.json` PreToolUse hook — `agent-ops/scripts/hook-bash-guard.py` — is quote-aware: it auto-blocks `&&` · `;` · `||` · command substitution · backticks **outside quotes**. Operators inside single quotes, and `;` · `&&` · `||` inside double quotes, are literal and pass — e.g. `jq 'test("a;b")'`, `rg 'foo;bar'` are fine. `$(...)` and backticks are blocked even inside double quotes because they still execute. For genuine compound commands, split into multiple single commands, or Write a `.sh` file and run `bash file.sh`.)
  - **Check file existence/content with the `Read` tool** (no `test -s … ; echo $?`). If shell is unavoidable, run a **single command** like `test -s file` with no `; echo $?` tail (the exit code already appears in the tool result).

---

## Token Economy

Minimize token use without hurting quality. **When this conflicts with quality or correctness, quality wins.**

- **Partial reads**: for large files, narrow the location with `rg` (or Grep), then Read only that range with offset/limit — or pull just the needed region in one step with `rg -n -C <n>`. Full reads only when the file is small or whole-structure understanding is genuinely needed.
- **No re-reads**: never re-read a file already read in this session, including verification re-reads right after Edit/Write (failures surface as tool errors).
- **Narrow exploration**: don't open files one by one; narrow candidates with `rg`/Glob and read only what's needed.
- **`rg` over the Grep tool [Claude Code only]**: where Bash is available (main session), run searches as single `rg` commands from the repo root with **relative paths**. Same ripgrep engine, but Grep-tool results prefix every output line with an absolute path (~70+ chars in a deep worktree) plus header lines, while relative `rg` output does not; `Bash(rg *)` is allowlisted so there is no prompt cost. A global PreToolUse hook (`agent-ops/scripts/hook-grep-guard.py`) enforces this by denying main-session Grep; Bash-less subagents (read-only agents) and `.harnie` paths keep Grep.
- **Delegation first [Claude Code only]**: do development work through harnie (`/harnie:dev*`) whenever possible (harnie manages model assignment). For direct work outside harnie, when delegating substantial work (exploration, implementation, mechanical edits, drafts, review), read `~/workspace/agent-ops/claude/delegation.md` and distribute per its tiers (GPT first, Claude fallback). **Never read or apply delegation.md while harnie is running.**
- **Concise output**: responses carry conclusions plus necessary evidence only. Don't re-quote whole files or documents you read. Run large-output commands filtered (`--quiet`, `tail`, `grep`, etc.).
- **Reference docs on-demand**: never preload reference documents (GIT.md, PR-ADO.md, delegation.md, harnie instructions, etc.) without a trigger. Even then, read only the single document the task needs.

---

## Coding Guidelines

Behavioral guidelines to reduce common LLM coding mistakes. Merge with project-specific instructions as needed.

**Tradeoff:** These guidelines bias toward caution over speed. For trivial tasks, use judgment.

> When writing non-trivial new code (new feature, new module, complex logic), also apply the harnie builder instructions (`~/Tradlinx/harnie/agents/harnie-builder.md`). The builder instructions are subordinate to §1–4 below; on conflict, these rules win. For edits to existing code and small changes, follow §3 Surgical Changes instead of that flow.

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
