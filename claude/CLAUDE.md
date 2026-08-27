# CLAUDE.md / AGENTS.md — Shared Global Instructions

> **Canonical**: `~/workspace/agent-ops/claude/CLAUDE.md` (repo `qnamy/agent-ops`); `~/.claude/CLAUDE.md` (Claude Code) and `~/.codex/AGENTS.md` (Codex) are symlinks to it. Sections marked **[Claude Code only]** do not apply in Codex.
> **Language policy**: English `*.md` is the executable canon. `-ko.md` mirrors are updated only on explicit human request — it is normal for them to lag the English canon (exception: deleting an English canonical file deletes its `-ko.md` pair too). On conflict, the English canon wins.

## Response Language

- Respond in Korean.

## Task-Specific Reference Documents (read on trigger, then follow)

Procedures for specific requests live in separate files. **Never preload them**; on a trigger, read only the single file the task needs.

- **Development requests in Codex [Codex only]** → run the harnie `dev-solo` skill when the change needs design judgment (new logic, multi-file blast radius, migration); a localized fix in an existing pattern is done directly under §Coding Guidelines. Ad-hoc building at the first size is the failure this routes around — not the second. Note what dev-solo buys: the pipeline's contract (grounding → design → review loop → verification), *not* cross-model review — its reviewer is Codex reviewing Codex.
- **Commit / push / PR creation / review-request** → `~/workspace/agent-ops/guidelines/GIT.md` (routes company context to `~/Tradlinx/GIT-PR.md` · `REVIEW-REQUEST.md`)
- **PR review · code review · comment resolution** → criteria: harnie `pr-review` skill; resolution-verification: harnie `comment-resolve`; company (ADO) procedure: `~/Tradlinx/PR-ADO.md`. **Local review** (no PR number) needs no procedure doc: apply the pr-review criteria directly — default scope current branch vs `main` (working tree if only uncommitted changes; a named commit if given), findings ordered by severity, fixes only after user confirmation.
- **Non-trivial new code** (new feature, module, complex logic) → `~/Tradlinx/harnie/agents/harnie-builder.md` (subordinate to §Coding Guidelines below; ignore its loop-only parts when working directly)
- **Architecture design / review** (system boundaries, containers, data ownership, technology choices) → `~/Tradlinx/harnie/agents/harnie-designer.md` + output contract `~/Tradlinx/harnie/instructions/design-authoring-arch.md`
- **Detailed design / review** (a specific service, module, API, DB, implementation logic) → same designer gates + output contract `design-authoring-detail.md`
- **Parallel dispatch / worktree lifecycle / terminal orchestration [Claude Code only]** → **orca owns it**, not harnie: `orca worktree create` · `orca terminal create|read|send` · `orca worktree ps` · `orca worktree rm`. harnie owns quality, evidence, and enforcement; the two do not compete. Load usage with "use orca cli", or `orca agent-context --json` where the skill is unavailable. **When you are dispatching parallel units, read `~/workspace/agent-ops/claude/orca-dispatch.md` first** — it carries the measured command shape (model/effort ride on the launched command, not on `--agent`), the merge sequence from a linked worktree, and the cleanup rules. **Never clean up a worktree orca does not own, and never one you did not create** — a 2026-08-26 cleanup wiped a running run's worktree and unpushed branch; cleanup targets are enumerated explicitly, one at a time.
- **Multi-agent collaboration / Agent Teams [Claude Code only]** (a stage needing debate among agents, competing hypotheses, or multi-domain co-design) → `~/workspace/agent-ops/claude/agent-teams.md`. Standing rule even outside team work: never pass a `name` when dispatching an ordinary subagent — with agent teams enabled, a named spawn silently becomes a teammate.
- **Design routing** takes precedence over the generic review triggers; when the altitude is ambiguous, confirm the target once. In direct work ignore harnie loop-only sections, and write design output in Korean.

## Command Execution [Claude Code only]

**Goal**: run shell commands in the shape the hooks already enforce, and inspect files the cheapest way.

**MUST**

- Read a hook's deny message and comply with the fix it carries (`hook-bash-guard.py` blocks compound commands; `hook-grep-guard.py` denies main-session Grep in favor of `rg`).
- Prefer the Read tool over shell for inspecting files.

**NEVER**

- Never fight a hook — don't retry a denied call in the same shape.
- Never append `; echo $?` to a command: the exit code is already in the tool result.

**Evidence**: the hook allowed the call, or a denied call came back in a different shape.

## Token Economy

**Goal**: minimize token use without hurting quality — **on conflict, quality wins.**

**MUST**

- **Narrow, then read**: locate with single `rg` commands (relative paths from the repo root — the grep-guard hook enforces this in main sessions; Bash-less subagents keep Grep), then Read only the needed range (`rg -n -C <n>` for a region in one step). Full reads only when the file is small or whole-structure understanding is genuinely needed.
- **Delegation first [Claude Code only]**: development runs in a **plain session by default** (2026-08-26 measurement: an M `/harnie:dev` run beat it on neither time nor tokens). Reach for `/harnie:dev` when its enforcement is what the job needs — approval gate, seal, receipts, cross-model review loop. **When you do run one, leave a line in `~/Tradlinx/harnie/docs/m-pipeline-kill-criteria.md`** (tokens, wall-clock, user interventions, rework rounds) — that file's verdict is due 2026-11-27 and no samples exist yet. For substantial direct work (exploration, implementation, mechanical edits, drafts, review), read `~/workspace/agent-ops/claude/delegation.md` and distribute per its tiers (GPT first, Claude fallback).
- **Concise output**: conclusions plus necessary evidence only; run large-output commands filtered at the source.

**NEVER**

- Never re-read a file already read this session, including verification re-reads after Edit/Write.
- **Never read or apply delegation.md while a harnie run is in progress** — model assignment is harnie's.
- Never re-quote documents you read.

**Evidence**: each file appears at most once in the session's read history; large-output commands arrive already filtered.

## Coding Guidelines

**Goal**: bias toward caution over speed; for trivial tasks, use judgment. Non-trivial new code also applies `harnie-builder.md` (subordinate — on conflict these rules win).

**MUST**

1. **Think before coding.** State assumptions explicitly; present multiple interpretations instead of picking silently; say so when a simpler approach exists — push back when warranted; if something is unclear, stop and ask.
2. **Simplicity first.** Overengineering is a defect — canonical rule (no speculative features/abstractions/flexibility, defensive coding only at trust boundaries like external input/API/DB/network): `~/Tradlinx/harnie/instructions/builder-contract.md`. DRY/SOLID only after the rule of three; if 200 lines could be 50, rewrite — would a senior engineer call this overcomplicated?
3. **Surgical changes.** Touch only what the request requires; match existing style. Mention unrelated dead code. Remove only the orphans your own change created.
4. **Goal-driven execution.** Turn tasks into verifiable goals ("fix the bug" = write the reproducing test first, then make it pass); for multi-step work, state a brief step→verify plan. Strong success criteria let you loop independently.

**NEVER**

- No error handling for impossible scenarios; no premature optimization.
- Don't "improve" adjacent code, comments, or formatting; don't refactor what isn't broken.
- Never delete unrelated dead code — mention it instead.

**Evidence**: every changed line traces directly to the user's request; the stated goal's verification actually ran.
