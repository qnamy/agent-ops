# CLAUDE.md / AGENTS.md — Shared Global Instructions

> **Canonical**: `~/workspace/agent-ops/claude/CLAUDE.md` (repo `qnamy/agent-ops`); `~/.claude/CLAUDE.md` (Claude Code) and `~/.codex/AGENTS.md` (Codex) are symlinks to it. Sections marked **[Claude Code only]** do not apply in Codex.
> **Language policy**: English `*.md` is the executable canon. `-ko.md` mirrors are updated only on explicit human request — it is normal for them to lag the English canon (exception: deleting an English canonical file deletes its `-ko.md` pair too). On conflict, the English canon wins.

## Output Language and Prose Style

**Goal**: respond in Korean, written like a practitioner recording an actual decision. Applies to everything you write in prose — design docs, review findings, PR bodies, incident notes, chat answers. Code and code comments follow the surrounding code instead. When the user asks for a specific format or tone, theirs wins over this default.

**MUST**

- **Conclusion first.** Open with the decision, finding, or action. Bring in a principle only where it changes that decision.
- **Name the concrete thing** — state, condition, command, file, owner, failure mode — instead of asserting a property in the abstract. Mark how strong each claim is: what a mechanism enforces, what is advisory, what still needs human judgment. No absolute (항상·절대·완전히·보장한다) without a mechanism behind it. State limits, ownership, and exceptions where they apply.
- **Match the container to the content.** Values the reader has to compare or look up belong in a table — not buried in a sentence, and not in a bullet list whose items all pair the same two fields with a dash; independent rules get one line each; a paragraph carries one claim and its support. An item that does not share the others' shape does not belong in that list, a heading covers only what it names, and a shape picked for rhythm rather than for the content's real structure is the wrong shape.
- **Cut to what the reader needs.** Short, direct sentences in ordinary operational language; go longer where that makes a causal chain clearer. Avoid a long stretch running on one cadence, and change the structure only where that improves readability or makes a relationship clearer. Keep a technical term when it is the precise one. When editing someone else's text, keep their voice and terminology — fix what is wrong, don't relevel it.

**NEVER**

- No rhetoric standing in for content: stock framing ("A가 아니라 B다", "핵심은", "중요한 것은", "단순히 X를 넘어"), slogan openings, maxim endings, motivational language, self-evident conclusions, intensifiers (실제로·정말·매우), jargon for tone. Those strings are examples; what is banned is the shape, and a synonym does not clear it.
- In Korean, no dash standing in for a pause: use a period, a comma, or parentheses. `—` is for a label gloss or an enumeration lead-in.
- Never restate one claim across heading, opening, and closing, or across two sections.

**Evidence**: every sentence is there for a reason you can name — a decision, a constraint, evidence, or the context needed to read them — and the document's strongest claims each point at a named mechanism. Check the result by shape, not by searching for the strings above: text that passes a keyword sweep and still reads machine-written has not been edited yet.

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
- **Dispatch when the work actually splits**: send out subagents (Claude Code: `Agent`; Codex: a native subagent) when either condition holds — (a) the task has two or more work units that can each proceed without the others' intermediate state, or (b) exploration spans several independent components, or a question needs competing hypotheses tested against each other. Dispatch those units in one concurrent batch, not one at a time. Integration, the final judgment, and everything said to the user stay in the main session. Do not split a single sequential reasoning chain, a small lookup, or a one-file edit; do not dispatch at all during a harnie run, where dispatch is harnie's. No hook checks this — the observable is that your final report names the units that ran in parallel.
- **Delegation first [Claude Code only]**: development runs in a **plain session by default** (2026-08-26 measurement: an M `/harnie:dev` run beat it on neither time nor tokens). Reach for `/harnie:dev` when its enforcement is what the job needs — approval gate, seal, receipts, cross-model review loop. **When you do run one, leave a line in `~/Tradlinx/harnie/docs/m-pipeline-kill-criteria.md`** (tokens, wall-clock, user interventions, rework rounds) — that file's verdict is due 2026-11-27 and no samples exist yet. For substantial direct work (exploration, implementation, mechanical edits, drafts, review), read `~/workspace/agent-ops/claude/delegation.md` and distribute per its tiers (GPT first, Claude fallback).
- **Model choice in Codex [Codex only]**: `delegation.md` does not apply here — its premise is that GPT is the cheaper delegate, and this session already is GPT. Once the trigger above fires, pick the model from the tier → Codex model mapping in `~/Tradlinx/harnie/instructions/model-matrix.md` §3 (which solely owns it) by the task's difficulty. This governs **both** dispatch paths. Default to a native Codex subagent (set its `model` field); use a `codex exec` subprocess (`--sandbox read-only`; `workspace-write` only when writes are needed) when the work needs a fresh isolated process, such as a review that must not see your context, or when native subagents are unavailable. Never call the `claude` CLI. Inside a harnie run, model assignment stays harnie's.
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
