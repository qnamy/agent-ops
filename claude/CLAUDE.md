# CLAUDE.md / AGENTS.md — Shared Global Instructions

> **Canonical**: `~/workspace/agent-ops/claude/CLAUDE.md` (repo `qnamy/agent-ops`); `~/.claude/CLAUDE.md` (Claude Code) and `~/.codex/AGENTS.md` (Codex) are symlinks to it. Sections marked **[Claude Code only]** do not apply in Codex.
> **Language policy**: English `*.md` is the executable canon. `-ko.md` mirrors are updated only on explicit human request — it is normal for them to lag the English canon (exception: deleting an English canonical file deletes its `-ko.md` pair too). On conflict, the English canon wins.

## Response Language

- Respond in Korean.

## Task-Specific Reference Documents (read on trigger, then follow)

Procedures for specific requests live in separate files. **Never preload them**; on a trigger, read only the single file the task needs.

- **Development requests in Codex [Codex only]** (any code change — feature, bug fix, refactor, migration) → always run the harnie `dev-solo` skill; never build ad hoc.
- **Commit / push / PR creation / review-request** → `~/workspace/agent-ops/guidelines/GIT.md` (routes company context to `~/Tradlinx/GIT-PR.md` · `REVIEW-REQUEST.md`)
- **PR review · code review · comment resolution** → criteria: harnie `pr-review` skill; resolution-verification: harnie `comment-resolve`; company (ADO) procedure: `~/Tradlinx/PR-ADO.md`. **Local review** (no PR number) needs no procedure doc: apply the pr-review criteria directly — default scope current branch vs `main` (working tree if only uncommitted changes; a named commit if given), findings ordered by severity, fixes only after user confirmation.
- **Non-trivial new code** (new feature, module, complex logic) → `~/Tradlinx/harnie/agents/harnie-builder.md` (subordinate to §Coding Guidelines below; ignore its loop-only parts when working directly)
- **Architecture design / review** (system boundaries, containers, data ownership, technology choices) → `~/Tradlinx/harnie/agents/harnie-designer.md` + output contract `~/Tradlinx/harnie/instructions/design-authoring-arch.md`
- **Detailed design / review** (a specific service, module, API, DB, implementation logic) → same designer gates + output contract `design-authoring-detail.md`
- **Multi-agent collaboration / Agent Teams [Claude Code only]** (a stage needing debate among agents, competing hypotheses, or multi-domain co-design) → `~/workspace/agent-ops/claude/agent-teams.md`. Standing rule even outside team work: never pass a `name` when dispatching an ordinary subagent — with agent teams enabled, a named spawn silently becomes a teammate.
- **Design routing** takes precedence over the generic review triggers; when the altitude is ambiguous, confirm the target once. In direct work ignore harnie loop-only sections, and write design output in Korean.

## Command Execution [Claude Code only]

Hooks enforce the shell rules and their deny messages carry the fix (`hook-bash-guard.py`: compound commands, `;`/`&&`/`||`, command substitution and backticks outside quotes are blocked; `hook-grep-guard.py`: main-session Grep is denied in favor of `rg`). Work with them, not around them:

- One single command per Bash call. Genuine compound or multi-line work goes into a `.sh`/`.py` file first (inline `python3 -c` with a newline+`#` comment never auto-approves).
- Prefer the Read tool over shell for inspecting files; a command's exit code already appears in the tool result — never append `; echo $?`.

## Token Economy

Minimize token use without hurting quality — **on conflict, quality wins.**

- **Narrow, then read**: locate with single `rg` commands (relative paths from the repo root — the grep-guard hook enforces this in main sessions; Bash-less subagents keep Grep), then Read only the needed range (`rg -n -C <n>` for a region in one step). Full reads only when the file is small or whole-structure understanding is genuinely needed. Never re-read a file already read this session, including verification re-reads after Edit/Write.
- **Delegation first [Claude Code only]**: do development work through harnie (`/harnie:dev*`) whenever possible. For substantial direct work (exploration, implementation, mechanical edits, drafts, review), read `~/workspace/agent-ops/claude/delegation.md` and distribute per its tiers (GPT first, Claude fallback). **Never read or apply delegation.md while harnie is running.**
- **Concise output**: conclusions plus necessary evidence only; don't re-quote documents you read; run large-output commands filtered at the source.

## Coding Guidelines

Bias toward caution over speed; for trivial tasks, use judgment. Non-trivial new code also applies `harnie-builder.md` (subordinate — on conflict these rules win).

1. **Think before coding.** State assumptions explicitly; present multiple interpretations instead of picking silently; say so when a simpler approach exists — push back when warranted; if something is unclear, stop and ask.
2. **Simplicity first — overengineering is a defect.** Minimum code that solves the problem: no features beyond what was asked, no abstractions for single-use code, no speculative flexibility or configurability, no error handling for impossible scenarios. No premature optimization; DRY/SOLID only after the rule of three; defensive coding only at trust boundaries (external input, API/DB/network, untrusted data). If 200 lines could be 50, rewrite. Test: would a senior engineer call this overcomplicated?
3. **Surgical changes.** Touch only what the request requires: don't "improve" adjacent code, comments, or formatting; don't refactor what isn't broken; match existing style. Mention unrelated dead code — don't delete it. Remove only the orphans your own change created. Every changed line traces directly to the user's request.
4. **Goal-driven execution.** Turn tasks into verifiable goals ("fix the bug" = write the reproducing test first, then make it pass); for multi-step work, state a brief step→verify plan. Strong success criteria let you loop independently.
