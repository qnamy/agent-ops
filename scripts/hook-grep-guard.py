#!/usr/bin/env python3
"""PreToolUse guard: deny main-session Grep tool calls in favor of `rg` via Bash.

Rationale (token economy): the Grep tool is the same ripgrep engine, but its
results carry an absolute-path prefix on every output line (~70+ chars in a
deep worktree), while a relative-path `rg` run from the repo root does not.
`Bash(rg *)` is allowlisted, so the redirect costs no permission prompt.

Scope:
- Subagent calls pass through untouched (`agent_id`/`agent_type` present):
  read-only agents (harnie-scout/-reviewer/-designer, Explore, Plan) have no
  Bash, so Grep is their only search tool.
- Grep with a path referencing `.harnie` passes through: harnie's run Bash
  guard blanket-blocks `.harnie` in shell commands (reads included), so the
  Grep/Read tools stay the sanctioned readers there.
- Fail-open on any parse error: this guard must never brick a session.
"""
import json
import sys


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
        sys.exit(0)  # fail-open

    if data.get("tool_name") != "Grep":
        sys.exit(0)
    if data.get("agent_id") or data.get("agent_type"):
        sys.exit(0)  # subagent (possibly Bash-less): Grep stays available
    tool_input = data.get("tool_input") or {}
    if ".harnie" in str(tool_input.get("path") or ""):
        sys.exit(0)  # harnie run Bash guard blocks `.harnie` in shell; keep Grep

    print(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": (
                "Main-session Grep is disabled by policy (token economy): run the "
                "same search as a single `rg` command via Bash, from the repo root "
                "with RELATIVE paths — e.g. `rg -n \"pat\" src`, `rg -l \"pat\"`, "
                "`rg -n -C 3 \"pat\" file` to read just the needed region. Same "
                "ripgrep engine; rg output carries no absolute-path prefixes. "
                "(Subagents without Bash keep Grep; `.harnie` paths keep Grep.)"
            ),
        }
    }))
    sys.exit(0)


main()
