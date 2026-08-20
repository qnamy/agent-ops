# delegation.md — Delegation First + Model-Tier Matching (Claude Code only)

> Detail rules split out of the global §Token Economy. **Never read or apply this document while harnie (`/harnie:dev*`) is running** — model assignment is harnie's job. These rules apply only when delegating substantial work during direct (non-harnie) tasks: instruction or harnie maintenance, search and research, and the like.

Delegate substantial work (exploration, implementation, mechanical edits, drafts, reviews) to subagents/GPT-MCP whenever possible, and keep the expensive main session focused on orchestration and final judgment. Even work that requires some reasoning should be split into the tiers below rather than absorbed by the main session.

- **GPT first, Claude fallback**: the default delegate is GPT (codex MCP) — it consumes no Claude usage. Grant `sandbox=workspace-write` when writes are needed. Use Claude subagents when (a) codex fails, refuses, or hits a structural limit (git metadata writes in worktrees; tasks that need this session's MCP tools such as Slack/ADO), or (b) it is Claude's turn in a cross-model review (reviewing GPT output).
- **Claude subagents**: mechanical/bulk work (translation mirrors, repetitive edits, simple exploration) = Haiku (`claude-haiku-4-5`); general implementation / mid-level reasoning = Sonnet (`claude-sonnet-5`); hard judgment / review = Opus (`claude-opus-5`).
- **GPT (codex MCP)**: hard reasoning = Sol (`gpt-5.6-sol`); mid-level reasoning / general implementation = Terra (`gpt-5.6-terra`); light = Luna (`gpt-5.6-luna`); mechanical/bulk = Spark (`gpt-5.3-codex-spark`).
- **Exception**: do directly anything where the delegation overhead (writing the prompt + receiving the result) exceeds the work itself — a single small edit, a simple lookup.
