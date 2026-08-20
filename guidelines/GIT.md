# GIT.md — Commit · Push · PR Creation · Review-Request Routing

On requests like "커밋해줘", "푸시해줘", "PR 생성해줘", "리뷰 요청해줘", follow the rules below.

## Context Detection

- If `git remote get-url upstream` resolves, use the upstream URL; otherwise check `git remote get-url origin`.
- A remote URL containing `dev.azure.com` or `ssh.dev.azure.com` means **company** context; `github.com` means **personal**.
- Use the directory only as a secondary signal when the remote URL is inconclusive. Anything under `~/Tradlinx` is likely company context, but personal GitHub repos live there too, so never decide on the directory alone.
- If still ambiguous after the secondary signal, ask the user which context applies.

## Common Rules

- Write the commit summary in Korean, within 100 characters, in the imperative mood.
- Pick the type from `fix`, `feat`, `refactor`, `chore`, `docs`, `style`, `test`, `perf`, `ci`.
- Stage all changes with `git add -A` before committing.
- Add a detailed body when useful.
- Push to upstream if `git remote` has one, otherwise to origin.
- Run as `git push {remote} {current-branch}`.

## Personal (GitHub) Rules

- No ticket-number convention.
- Commit title format: `{type}: summary`.
- Default workflow: commit directly on `main`, push, and finish without a PR.
- Create a temporary branch and a PR only when the user explicitly asks for one:
  - PR title: `{type}: summary` (no ticket)
  - PR body: **changes only**, concise.
  - No review-request step.
  - Delete the temporary branch after merge.

## Company (Azure DevOps) Rules

In company context, read and follow `~/Tradlinx/GIT-PR.md`.

The methodology for writing PR body and review-request content (the "what") is generalized in the harnie plugin's `pr-delivery` skill (`/harnie:pr-delivery`); the profile (title convention, body section set) is injected from the per-context rules above (optional reference).
