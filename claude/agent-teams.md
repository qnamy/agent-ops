# agent-teams.md — Agent Teams Usage (Claude Code only)

> Read on trigger from the global CLAUDE.md. Agent Teams is an **experimental** Claude Code feature (`CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1`), interactive sessions only — headless `-p` silently falls back to ordinary subagents even when the flag is set. Not available in Codex. Facts below follow the official docs as of Claude Code 2.1.245 (2026-08); re-verify on major CLI upgrades.

## Activation (staged)

- **Stage 1 (current)**: enable per project only, in that project's `.claude/settings.json` `env` block — non-harnie projects only. Keep harnie run sessions flag-off until the two blocking E2E checks pass (① plugin hooks fire in teammate sessions, ② unnamed dispatches stay ordinary subagents while the flag is on).
- **Stage 2**: after both checks pass, promote the flag to `~/.claude/settings.json` and enable harnie's team-collab path.

## Routing: direct vs subagent vs team

Decision order — first match wins:

1. Headless session or flag off → never a team.
2. Small, sequential, or same-file-focused work → direct or a single subagent (official guidance: teams cost significantly more tokens and coordination).
3. A single task where only the result matters (exploration, solo design, solo review) → **unnamed subagent**.
4. Form a team only when **≥3 of 5** are yes: members need direct information exchange / members must rebut each other's hypotheses or designs / a shared task list with self-coordination is needed / several independent domains must be fitted together simultaneously / expected quality-speed gain exceeds the token + coordination cost.

A subagent that discovers mid-task that collaboration is needed does **not** form a team (nested teams are unsupported); it returns `NEEDS-COLLAB: <reason>` plus the path of its partial artifact, and the top-level session re-runs that stage as a team with the partial artifact as prior work.

## Hard rules

1. **Never pass `name` when dispatching an ordinary subagent.** In a flag-on session a named spawn silently becomes a teammate with a different return contract. This rule stands even when you are not doing team work.
2. **One artifact owner per team.** Exactly one teammate writes the single output file; all others are read-only contributors. No source-code writes in a team phase.
3. **Completion is three conditions together**: the artifact exists on disk ∧ the team task list is closed ∧ the owner's result message has been received. An idle notification alone is never completion — it carries no output.
4. **Independent reviewers never join a production team.** A "challenger / devil's advocate" inside a team is an explorer role, not a reviewer. Team output that feeds a formal review loop (e.g. harnie's cross-model loops) still goes through it unabridged — team-internal debate is same-provider and replaces nothing.
5. **Team state is disposable.** Teammates do not survive `/resume`; recovery is restarting the phase from the on-disk artifact, or degrading to a single subagent that continues from the partial artifact.
6. **Teammates never touch authority state** (e.g. harnie `.harnie/` CLIs, ledgers, approval flows).
7. **Caps and spawn hygiene**: ≤4 teammates per team, one artifact per team phase. Always specify each teammate's model explicitly at spawn — an unspecified teammate inherits the lead's model, which is usually wrong. Reasoning effort cannot be set per teammate (inherits the lead); distribute capability via model choice only.

## Team member = three axes

process role (explorer / designer / builder / reviewer — reviewer prohibited in teams) × domain profile (injected via the spawn prompt, never new agent definitions) × model tier:

| Tier | Claude | GPT (Codex) | Use |
|---|---|---|---|
| T4 | fable | sol + high effort | irreversible architecture decisions, ambiguous incident analysis |
| T3 | opus | sol | complex design, review, security, data integrity |
| T2 | sonnet | terra | standard design, implementation, review |
| T1 | haiku | luna | exploration, classification, narrow verification |

Inside harnie, `instructions/model-matrix.md` is canonical and overrides this table; outside harnie, `delegation.md` tiers apply.

## Templates (adapt these; don't multiply fixed org charts)

- **T-A multi-domain contract design**: policy-analyst (explorer × policy × T2) + lead-designer, artifact owner (designer × backend × T3–T4) + frontend-designer (designer × frontend × T2) + challenger (explorer × QA/reliability × T3). Output: one design draft → formal review loop. Add a security / migration / performance explorer (T3) only when that risk is present.
- **T-B competing-hypothesis incident analysis**: hypothesis-1..N (explorer × one hypothesis each × T2, N≤3) + refuter (explorer × rebuttal × T3) + incident-writer, artifact owner (designer × synthesis × T3). Output: one incident report.

## Known limitations (official docs — design around them)

No nested teams; one team per session; `/resume` does not restore in-process teammates; in-process teammates cannot spawn background subagents; task status can lag (nudge, don't wait forever); a teammate referencing a subagent definition applies its `tools:` and `model:` but **not** `skills:` or `mcpServers:`.
