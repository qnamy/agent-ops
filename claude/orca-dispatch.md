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

## Chain units from a design

When `_chain/design.md` section 3 ends with 병렬 단위, those units are the dispatch list; do not draw a second one, and do not start before the design review has closed on that section. The worktree holding the design is the **parent**; its branch is the integration branch, its HEAD at dispatch is the **parent baseline**, and only the coordinator commits to it until the last unit has merged.

1. **Child worktree per unit** whose dependencies have all merged: `orca worktree create --repo name:<repo> --name <unit> --base-branch <parent branch> --parent-worktree name:<parent> --json`. A dependent unit is created only after the unit it depends on has merged, from the parent as it then stands. For a unit the design decided in full, copy the parent's `_chain/design.md`, the closing `design-review-N.md`, and `_chain/requirements.md` when there is one into the child's `_chain/` — a fresh worktree has none, so one chain per worktree still holds, the unit's own round files land beside its copy of the design, and every path in the unit's instruction resolves inside the child. For a unit marked 상세설계 위임, copy nothing: its `_chain/` starts empty and the unit's own chain fills it.
2. **Unit session**: open a terminal in the child with the model and effort chosen for the unit, and pass the instruction by reference. Two shapes, chosen by the unit's mark in the design.
   - *Decided unit*: run `implementation` with the design path, the design review verdict, the requirements path or the request verbatim, and a scope limit equal to the unit's files; then act as the coordinator of `implementation-review` in that worktree, with its own reviewer session of the other provider.
   - *상세설계 위임 unit*: run harnie `dev` on the unit's entry from the design, quoted verbatim, and on nothing else — the design wrote that entry to be the unit's whole request (boundary, what it must do, the requirement conditions that bind it), so the parent requirements and the parent request are not passed and the child chain judges against the entry alone. `dev` designs the internals, reviews, implements, reviews, and verifies inside the child; its Gate 2 still applies, so a unit that turns out larger than `dev` takes comes back as a split to revise. The parent's verification (step 4) is where the parent requirements are judged.
   Either way the unit commits on its branch once its last stage closes, and reports. The unit session never merges and never touches the parent. A verification part that waits on another unit's scope is reported as waiting, and its review closes on that; the parent's verification (step 4) is where the whole passes or fails.
3. **Merge, coordinator only**, one unit at a time after its review has closed: rebase the unit branch onto the parent, re-run the unit's verification command on the rebased tree and expect what the unit's report recorded, waiting parts included, then fast-forward the parent onto it. A conflict means two units wrote one file, which the design promised could not happen: stop, report the file and the two units, resolve nothing by hand — the design's 병렬 단위 is corrected under design review and the unit redispatched.
4. **Verification once, on the parent**, after the last merge: `acceptance-verification` in a session of the other provider that wrote none of the units, with the requirements or the request verbatim, the design's section 6, the parent baseline, and every unit's implementation report and review verdict. The result lands in the parent's `_chain/`. Unit-level review is the review; there is no second code review of the merged parent.
5. **Cleanup** follows the NEVER rules below: one unit worktree at a time, after its merge is on the parent and confirmed.

## NEVER

- Never remove a worktree orca does not own, and never one you did not create. On 2026-08-26 a cleanup session deleted a running run's worktree and its unpushed branch; the work survived only because the transcript could be replayed. Cleanup targets are enumerated explicitly, one at a time, after checking that the worktree is clean and its commits are on the remote.
- Never let the working session clean up after itself — the coordinator removes worktrees once the merge is confirmed.
- Never merge on a green test run from before the rebase. Rebase first, then re-run.

## Evidence

- `orca worktree ps` shows what is live; `orca file open-changed --mode diff --worktree name:<unit>` reviews a unit without a PR.
- After the last merge, `git status --short --branch` in the main checkout shows no divergence from `origin/main`, and `git branch --merged main` is what you delete from.
