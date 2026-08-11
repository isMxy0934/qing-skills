---
name: track-ai-plans
description: Track long, multi-step AI implementation work in Git so another agent or computer can resume it without restating intent. Use when work needs a durable plan, file/module impact, reasons, upstream/downstream context, independent plan review, scope amendments, checkpoints, verification history, migration from plans/, or a visual qing-plans dashboard.
---

# Track AI Plans

Use `qing-plans/` as durable project memory: what the user wants, why the plan is shaped this way, what each stage changes, which modules are affected, what was observed and verified, and exactly what should happen next.

## Preflight

1. Treat the Git top-level as `ROOT`. Set `PLANCTL` to this skill's own `scripts/planctl.py` and run every command as `python3 "$PLANCTL" --root ROOT ...`. A repository holds plan data and `dashboard.html` only — never the runtime — so the same command works before the first plan exists and on every later machine.
2. If `qing-plans/index.json` exists, run `validate`, then `resume`. With no current plan, `resume` discovers one unfinished draft or lists draft candidates instead of silently ignoring them.
3. If only `plans/index.json` exists, it is V1 and read-only. Read [references/migration.md](references/migration.md) before mutation.
4. If both directories exist, continue only when `qing-plans/migration.json` is verified; then `qing-plans/` is authoritative and `plans/` is legacy evidence.
5. A paused plan is current but never auto-resumed. Report it and ask the user before changing its lifecycle.

## Route the request

- Create a plan or define modules: read [references/create-plan.md](references/create-plan.md).
- Continue work, checkpoint, or change active scope: read [references/work-plan.md](references/work-plan.md).
- Record test, model-review, or human evidence: read [references/verify-plan.md](references/verify-plan.md).
- Activate, pause, complete, cancel, or replace: read [references/plan-lifecycle.md](references/plan-lifecycle.md).
- Migrate V1 `plans/`: read [references/migration.md](references/migration.md).
- Diagnose JSON or dashboard projections: read [references/schema.md](references/schema.md).

## Core rules

- `qing-plans/index.json` alone owns lifecycle state, baseline, and `currentPlanSlug`. At most one `active` or `paused` plan is current.
- New plans use review policy `single` by default. Use `none` for ordinary work where tests and verification evidence are sufficient.
- `single` requires one genuinely independent agent to review the current immutable plan revision and project-map revision before activation. It also reviews every material active amendment. It does not require phase reviews.
- Reviewer-name inequality is only a guardrail: invoke a genuinely separate agent for `single`; never relabel the planner/implementer context as a reviewer.
- A draft's named planner defines phases, items, documentation impact, and the project map. Draft edits increment the plan revision, making older reviews stale without deleting history.
- Never edit active scope directly. Use `propose-amendment` with kind `scope`, `corrective`, or `temporary`. A temporary amendment names a cleanup item that must finish before completion.
- Every file-changing item groups files into `changeSets` with a module and reason. Use `_unmapped` only while classification is genuinely unknown and `_cross-cutting` for cross-module/no-file work.
- Project dependencies have one direction only: `A dependsOn B`. Derive upstream and downstream from that relation. Do not introduce AST/import analysis as a hidden second source of truth.
- Mark an item `in-progress` before implementation. The tool snapshots planned file hashes and Git `HEAD`; completing it captures end hashes and observed actions so later edits cannot erase stage attribution.
- Verification attempts are append-only. Enforce `test → script`, `llm-review → llm`, and `manual → human`.
- Only human-authorized commands activate, pause, resume a paused plan, complete, cancel, or replace a plan. The read-only `resume` inspection command itself never changes lifecycle. Terminal snapshots are frozen.
- Completion requires non-empty work, all items done, temporary cleanup done, no open issue/pending amendment/off-plan change, exact planned actions, and required documentation coverage.
- Route every mutation through `$PLANCTL`. It locks, appends audit events, updates the registry, and refreshes the affected status snapshot.

## Handoff discipline

At a stop, run `checkpoint` with the current item, stop reason, and concrete next action. Commit `qing-plans/` together with code at meaningful milestones and push the branch before changing computers. A dirty tree, missing upstream, or unpushed commit makes the checkpoint `local-only`; another computer can read any already-synced intent but cannot reliably fetch the complete state.

`resume` is deterministic: pending amendment/review gate, current in-progress item, failed/blocked item, first dependency-ready item, then completion checks. It also warns when branch or `HEAD` differs from the checkpoint.

## Dashboard

`create` and migration install `qing-plans/dashboard.html` plus a `.gitignore` for the lock file; the viewer is the only non-data artifact a repository receives. Run `refresh-status` when the dashboard needs a fresh Git observation without changing plan semantics. Run `install-dashboard` to refresh the viewer after upgrading this skill. Serve `qing-plans/` over HTTP; the dashboard shows handoff first, Plan/phase selection, Planned/Observed/Verified file rows (a verified badge downgrades to mismatched when observed attribution disagrees with the plan), a language toggle, clickable module relations, amendments, and issues. Its per-plan impact map reads only that plan's own `status.json` projection — frozen at completion for terminal plans — never the live root `project-map.json`; the "global map" toggle is the only view that reads the live map.

## Write and report in the user's language

Write goals, purposes, reasons, evidence, issues, stop reasons, and next actions in the user's language. Report the current plan and phase, item just changed, completed/total count, handoff portability or blocker, and next action.
