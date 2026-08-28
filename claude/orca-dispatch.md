# orca-dispatch.md — Parallel Dispatch with orca (Claude Code only)

> Detail rules split out of the global routing table. Read on trigger: you are splitting work into parallel units and dispatching them as separate sessions. orca owns dispatch, worktree lifecycle, terminals, and gates; harnie owns quality, evidence, and enforcement. They do not compete. In harnie 0.14, harnie receives the run root and no longer creates worktrees, so this ownership boundary is enforced by the implementation as well.
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

  Headless `codex exec` skill loading and Orca completion tracking for this command have not been measured. Use an interactive Codex session for a handoff that needs those guarantees, and inspect the first dispatched terminal before relying on its completion signal.

- **Pass the prompt by reference, not by value.** Write the unit instructions to a file and tell the session to read its section ("read <file>, do the §U3 card"). Long prompts through `--prompt`/`--text` break on shell quoting, and a referenced prompt picks up edits on redispatch.
- **Push with `git push origin HEAD:main`.** A linked worktree cannot `git switch main` — the main checkout holds that branch.
- **Fast-forward the main checkout after every merge**: `git -C <main checkout> merge --ff-only origin/main`. Skipping this leaves the local `main` behind `origin/main`, so later `--base-branch main` worktrees fork from a stale tree, and any file exposed through a symlink from the main checkout keeps serving the old content. `--ff-only` cannot lose commits.
- **Give every unit sole ownership of the files it edits.** Two units editing one file is a merge conflict you designed in; when a file must change for several reasons, name one owner and order the rest behind it.
- **Check the repo's setup script before the first dispatch** (`orca repo show --repo name:<repo> --json`). A `setup` script that does not fit the repo fails on every worktree create. Pass `--setup skip` to work around it; the fix itself is in the Orca app's repo settings — the CLI has no command for `hookSettings.scripts`.
- **Re-enter an existing unit in place.** For a handoff or resume, do not create another worktree. Run `orca terminal create --worktree name:<unit> --command '<replacement command>' --json` against the same unit worktree.
- **Create the workspace before harnie development.** Before running `dev` or `dev-solo` for an actual code change, create the target worktree and Orca workspace. harnie 0.14 accepts the run root and blocks neither the main checkout nor workspace creation; this rule replaces the safety net that its former worktree creation happened to provide.

## NEVER

- Never remove a worktree orca does not own, and never one you did not create. On 2026-08-26 a cleanup session deleted a running run's worktree and its unpushed branch; the work survived only because the transcript could be replayed. Cleanup targets are enumerated explicitly, one at a time, after checking that the worktree is clean and its commits are on the remote.
- Never let the working session clean up after itself — the coordinator removes worktrees once the merge is confirmed.
- Never merge on a green test run from before the rebase. Rebase first, then re-run.

## Evidence

- `orca worktree ps` shows what is live; `orca file open-changed --mode diff --worktree name:<unit>` reviews a unit without a PR.
- After the last merge, `git status --short --branch` in the main checkout shows no divergence from `origin/main`, and `git branch --merged main` is what you delete from.
