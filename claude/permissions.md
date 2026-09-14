# permissions.md — Permission rules the routed workflows depend on

**[Claude Code only]** — Codex approves per-command through its own sandbox model and reads nothing here.

This file is not a copy of a machine's settings and does not track one. It records **which allow rules the workflows this repo routes to assume already exist**, and why each is scoped the way it is. The runtime is the machine's user settings — `~/.claude/settings.json`, key `permissions.allow`. Everything else in that file (hostnames, accounts, absolute paths) is local and stays out of this public repo.

Without a rule below, the workflow that needs it does not fail — it stops at a prompt, in the middle of a chain that may be running unattended in another terminal.

| Rule | What prompts without it |
|---|---|
| `Skill(harnie:*)` | Every harnie chain skill call: `requirements`, `software-design`, `software-design-review`, `implementation`, `implementation-review`, `acceptance-verification`, and the skills outside the chain |
| `Bash(orca terminal *)` | `orca terminal create｜send｜read` — the reviewer and verifier sessions the chain opens, and unit dispatch per [orca-dispatch.md](orca-dispatch.md) |
| `Bash(orca automations *)` | Automation state queries through orca |
| `Bash(git *)` | The commit and push flow in [../guidelines/GIT.md](../guidelines/GIT.md) |

## Deliberately not granted

- **`Bash(orca *)`** — it would cover `orca worktree rm`. On 2026-08-26 a cleanup wiped a running run's worktree and its unpushed branch, so worktree removal stays behind a prompt. Widen the orca rules subcommand by subcommand, never with one wildcard.
- **Outward-facing MCP sends** (chat messages, review requests) — each one reaches other people, so each stays a decision rather than a setting.

## Keep them in user settings, not in a repo

A machine-wide rule duplicated into a repository's `.claude/settings.local.json` applies in that checkout only. A worktree of the same repository has its own working tree and does not see it, and the two copies drift. Measured 2026-09-14: two orca rules existed only in one checkout's local file, so every other worktree of that repository prompted for the same commands.

A repository's own `.claude/settings.json` is for what belongs to the repository — hooks that run its scripts, its `.mcp.json` approvals — and is committed for everyone working on it.
