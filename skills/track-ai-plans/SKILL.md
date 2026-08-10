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

## Write in the user's language

Every stored text field — plan `--goal`, item `--title`/`--purpose`, `--evidence`/`--reason`, issue `--title`/`--detail`/`--next-action` — is content you author, not tool output. Write it in the language the user is using in conversation. The examples throughout this skill's reference files are in English only so the skill itself stays portable to read; they are not a template for what language to write plan content in. A dashboard mixing the user's language in its labels with English in every item's title reads as two systems stitched together — keep the content language consistent with what the user actually speaks.

## Core invariants

- `plans/index.json` is the only lifecycle registry. It owns every plan's state, baseline, and `currentPlanSlug`; do not duplicate those fields in `plan.json`.
- Keep at most one current plan. Both `active` and `paused` occupy `currentPlanSlug`; pausing does not make room for another resumable plan.
- Create plans as `draft`. Capture `baselineCommit` only when activating, after Git is clean outside `plans/` and `plan-dashboard.html`.
- A named planner subagent creates and edits a draft. Before activation, a different named reviewer subagent must pass `review-plan`; any draft structure change resets that approval.
- Every completed phase enters `phaseReview=pending`. A different agent from every completed-item agent in that phase must pass `review-phase` before work may enter a later phase.
- Only `active` plans may update items, verify work, checkpoint, or mutate issues. Draft plans may only define phases, items, and documentation impact. Completed and cancelled plans are immutable.
- Every item declares `--verify-kind test|llm-review|manual` and exactly one of: one or more `--file` values, or `--no-file-impact`.
- Enter `in-progress` or `done` only after dependencies are done. Keep at most one item `in-progress`.
- Mark `done` only with evidence and `--verified-by script|llm|human`.
- Treat `create`, `modify`, `delete`, and `move` as exact actions. A mismatched or missing planned change never satisfies completion.
- Complete only when every item is done, every planned file is observed exactly, no off-plan change or open issue exists, and required documentation coverage passes.
- Require `--actor-type human` for activation, pause, resume, completion, cancellation, and replacement.
- Require `--actor-type agent --actor NAME` for draft planning and plan review. Use distinct, stable subagent names for the planner and reviewer so the audit trail can enforce independence.
- Require `--actor-type agent --actor NAME` for phase review too. `completedBy` records who completed each item so a phase cannot self-approve.
- `planctl.py` can only check that the reviewer's `--actor` name differs from the planner or from every `completedBy` in the phase; it cannot check who actually ran the command. That name check is a guardrail, not the source of independence. Run `review-plan` and `review-phase` from a genuinely separate subagent invocation — a fresh Task/Agent call with no shared conversation history with the planner or the implementing agent. Never satisfy the gate by having the same context call itself again under a different `--actor` value; a same-context self-review passes the tool check but provides none of the independent judgment the gate exists for.
- Use `switch` only to terminate the current plan and activate a clean draft atomically. Use separate Git worktrees if resumable plans must execute in parallel.
- Use `planctl.py` for every mutation. It holds `plans/.planctl.lock`, writes an event, updates the authoritative registry, and refreshes only the affected status snapshots.

## Keep the store in Git

Track `plans/` and `plan-dashboard.html` — this is what makes the current plan and its progress visible from any device, not just the one that ran the last command. Commit at milestones (plan creation/activation before writing code, each phase completion, plan completion/pause/cancel/replacement) and always before switching devices or ending a session, even if the current item is not done — an item marked `in-progress` only locally is invisible everywhere else, and the single-in-progress-item guarantee ([Core invariants](#core-invariants)) is enforced against the local file, not across devices.

## Dashboard

`create` installs `plan-dashboard.html` automatically the first time (never overwrites an existing copy). Run `python3 scripts/planctl.py --root ROOT install-dashboard` only to force a refresh, for example after upgrading this skill to pick up a newer bundled dashboard. Serve the repository over HTTP and open `plan-dashboard.html` — a bare `file://` open cannot fetch the JSON it reads. The dashboard is read-only and reads the authoritative registry plus generated/frozen status files. Its task section can switch between a list and a Plan DAG derived directly from each item's `dependsOn`; the graph is never stored as separate plan state.

## Report back

Report only the current plan and phase, item just changed, completed/total count, stop reason or open problems, and next actionable item.
