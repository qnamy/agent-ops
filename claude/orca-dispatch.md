# orca-dispatch.md — Parallel Dispatch with orca (Claude Code only)

> Detail rules split out of the global routing table. Read on trigger: you are splitting work into parallel units and dispatching them as separate sessions. orca owns dispatch, worktree lifecycle, terminals, and gates; harnie owns quality and evidence through its chain skills. They do not compete. harnie creates no worktrees and keeps no run state; its artifacts live in the worktree's `_chain/`.
> Measured 2026-08-27 while dispatching an 11-unit release program across two repos.

## Goal

Turn a unit list into running sessions with the intended model and effort, and merge them back without losing work or leaving stale checkouts behind.

## MUST

- **Two commands per unit, not one.** `orca worktree create --agent claude --prompt "..."` cannot set model or effort — `--agent <id>` takes an agent id, not a command line. Create the worktree first, then open a terminal that carries the flags:

  ```
  orca worktree create --repo name:<repo> --name <unit> --base-branch main --no-parent --json
  orca terminal create --worktree name:<unit> --command 'claude --model <alias> --effort <low|medium|high|xhigh|max> "<instruction>"' --json
  ```

  For Codex, use the equivalent explicit command:

  ```
  orca worktree create --repo name:<repo> --name <unit> --base-branch main --no-parent --json
  orca terminal create --worktree name:<unit> --command 'codex exec -m <model> -s workspace-write -c model_reasoning_effort="<level>" "<instruction>"' --json
  ```

  Headless `codex exec` skill loading has not been measured — use an interactive Codex session for a handoff that needs that guarantee.

  **Do not watch a Codex TUI by scraping its terminal.** Measured 2026-08-28: the screen interleaves the session's own output with the transcripts of nested `codex exec` subprocesses, so a filter cannot tell whose `HARNIE_STATUS` line it just matched, and approval prompts vary enough in wording that matching them fails too. Three successive filters gave false readings before the approach was abandoned. Use one of these instead:

  - **What the work produced.** Poll for the artifact the job promises — for a harnie chain stage, the file in `_chain/` (`design.md`, `design-review-N.md`, `implementation-review-N.md`, `acceptance-verification.md`). The file tells you the artifact exists and what it says; it does not tell you the stage is finished — a reviewer may still be self-checking or reading after writing it. Stage completion is the session's turn-completion signal (next two bullets); read the artifact after that, and never start changing the design or code it points at before then.
  - **Turn completion.** `notify = ["<program>", ...]` in `~/.codex/config.toml` fires an external program on `agent-turn-complete` with a JSON payload (`thread-id`, `turn-id`, `cwd`, `last-assistant-message`). It is the only event `notify` supports — it says nothing about starts or approval waits.
  - **Full state, including approvals.** `codex app-server --listen ws://127.0.0.1:<port>` plus `codex --remote ws://127.0.0.1:<port>` exposes `turn/started`, `turn/completed`, `thread/status/changed`, and unresolved `item/*/requestApproval` requests over JSON-RPC. The client must be attached from session start; attaching to an already-running TUI is not supported.

  **Approval prompts**: `-a never` (`--ask-for-approval never`, or `approval_policy = "never"`) suppresses them, but under Codex's `workspace-write` sandbox any git metadata write then fails: the sandbox denies writes under `.git/` even inside the workspace, so `git add`/`git commit` fail with `Operation not permitted`. Probed 2026-08-31: `os.tmpdir()` writes are allowed and relocating the git index does not help — the denial is the object database, and it reproduces in an ordinary repo as well as a linked worktree. So a Codex session that must commit runs with approvals **on**, one prompt per new command prefix; `-a never` fits read-and-write-files sessions such as a chain reviewer (it writes only into `_chain/`) or a researcher. Opening `.git` through `writable_roots` would work but unlocks what the sandbox protects — not recommended.

  **Chain reviewer sessions**: open the other provider's interactive session in the same worktree and tell it to act as the review skill's reviewer. Give it the narrowest write surface the runtime offers, and name honestly what that buys. For Codex, `workspace-write` — there is no per-directory allowlist, and `read-only` would block the result file, so the "results only" rule rests on the skill text. For Claude, `--permission-mode dontAsk` with a scoped `Edit`/`Write` allow on `_chain/` restricts the file tools only when no broader allow rule is inherited from settings and Bash and MCP writes are closed separately; short of all three, the session runs on the skill's rule alone, and it is not a guard. Exchange request and result as files under `_chain/`.

- **Pass the prompt by reference, not by value.** Write the unit instructions to a file and tell the session to read its section ("read <file>, do the §U3 card"). Long prompts through `--prompt`/`--text` break on shell quoting, and a referenced prompt picks up edits on redispatch.
- **Push with `git push origin HEAD:main`.** A linked worktree cannot `git switch main` — the main checkout holds that branch.
- **Fast-forward the main checkout after every merge**: `git -C <main checkout> merge --ff-only origin/main`. Skipping this leaves the local `main` behind `origin/main`, so later `--base-branch main` worktrees fork from a stale tree, and any file exposed through a symlink from the main checkout keeps serving the old content. `--ff-only` cannot lose commits.
- **Give every unit sole ownership of the files it edits.** Two units editing one file is a merge conflict you designed in; when a file must change for several reasons, name one owner and order the rest behind it.
- **Check the repo's setup script before the first dispatch** (`orca repo show --repo name:<repo> --json`). A `setup` script that does not fit the repo fails on every worktree create. Pass `--setup skip` to work around it; the fix itself is in the Orca app's repo settings — the CLI has no command for `hookSettings.scripts`.
- **Re-enter an existing unit in place.** For a handoff or resume, do not create another worktree. Run `orca terminal create --worktree name:<unit> --command '<replacement command>' --json` against the same unit worktree.
- **Create the workspace before a harnie chain starts.** Before the first chain stage of an actual code change, create the target worktree and Orca workspace; `_chain/` lives there, one chain per worktree.

## NEVER

- Never remove a worktree orca does not own, and never one you did not create. On 2026-08-26 a cleanup session deleted a running run's worktree and its unpushed branch; the work survived only because the transcript could be replayed. Cleanup targets are enumerated explicitly, one at a time, after checking that the worktree is clean and its commits are on the remote.
- Never let the working session clean up after itself — the coordinator removes worktrees once the merge is confirmed.
- Never merge on a green test run from before the rebase. Rebase first, then re-run.

## Evidence

- `orca worktree ps` shows what is live; `orca file open-changed --mode diff --worktree name:<unit>` reviews a unit without a PR.
- After the last merge, `git status --short --branch` in the main checkout shows no divergence from `origin/main`, and `git branch --merged main` is what you delete from.
