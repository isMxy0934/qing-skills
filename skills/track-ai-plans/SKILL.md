---
name: track-ai-plans
description: Create, execute, verify, pause, resume, replace, complete, and summarize one current AI work plan in a Git repository. Use when Codex needs a multi-step implementation plan, must continue recorded work, track blockers and changed files, verify plan items, or show durable progress in a dashboard.
---

# Track AI Plans

Use a repository-local plan store to answer: what is current, what was intended, what changed, what is verified, and what stops the work.

## Preflight

1. Treat the Git top-level as `ROOT`; refuse activation from a subdirectory or a repository without an initial commit.
2. Run `python3 scripts/planctl.py --root ROOT validate` before changing an existing store.
3. Run `python3 scripts/planctl.py --root ROOT show` before continuing current work.
4. Report the current plan, current item, completed count, open problems, and next actionable item before substantial changes.

## Route the request

- Create or restructure a plan: read [references/create-plan.md](references/create-plan.md).
- Start work, record progress, or stop with a reason: read [references/work-plan.md](references/work-plan.md).
- Record verification evidence: read [references/verify-plan.md](references/verify-plan.md).
- Pause, resume, complete, cancel, or replace: read [references/plan-lifecycle.md](references/plan-lifecycle.md).
- Diagnose stored JSON: read [references/schema.md](references/schema.md).

## Core invariants

- `plans/index.json` is the only lifecycle registry. It owns every plan's state, baseline, and `currentPlanSlug`; do not duplicate those fields in `plan.json`.
- Keep at most one current plan. Both `active` and `paused` occupy `currentPlanSlug`; pausing does not make room for another resumable plan.
- Create plans as `draft`. Capture `baselineCommit` only when activating, after Git is clean outside `plans/` and `plan-dashboard.html`.
- Only `active` plans may update items, verify work, checkpoint, or mutate issues. Draft plans may only define phases, items, and documentation impact. Completed and cancelled plans are immutable.
- Every item declares `--verify-kind test|llm-review|manual` and exactly one of: one or more `--file` values, or `--no-file-impact`.
- Enter `in-progress` or `done` only after dependencies are done. Keep at most one item `in-progress`.
- Mark `done` only with evidence and `--verified-by script|llm|human`.
- Treat `create`, `modify`, `delete`, and `move` as exact actions. A mismatched or missing planned change never satisfies completion.
- Complete only when every item is done, every planned file is observed exactly, no off-plan change or open issue exists, and required documentation coverage passes.
- Require `--actor-type human` for activation, pause, resume, completion, cancellation, and replacement.
- Use `switch` only to terminate the current plan and activate a clean draft atomically. Use separate Git worktrees if resumable plans must execute in parallel.
- Use `planctl.py` for every mutation. It holds `plans/.planctl.lock`, writes an event, updates the authoritative registry, and refreshes only the affected status snapshots.

## Dashboard

Install once with `python3 scripts/planctl.py --root ROOT install-dashboard`, serve the repository over HTTP, and open `plan-dashboard.html`. The dashboard is read-only and reads the authoritative registry plus generated/frozen status files. Its task section can switch between a list and a Plan DAG derived directly from each item's `dependsOn`; the graph is never stored as separate plan state.

## Report back

Report only the current plan and phase, item just changed, completed/total count, stop reason or open problems, and next actionable item.
