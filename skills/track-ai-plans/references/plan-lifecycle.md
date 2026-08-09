# Manage the plan lifecycle

Every lifecycle command requires a reason and `--actor-type human`.

## Review gates

Plan activation needs two separate approvals: a named planner subagent creates and updates the draft, then a different named reviewer subagent runs `review-plan` with `--result pass`. The user still performs the final `transition --state active` authorization. Any draft structure change invalidates an earlier plan review, so request a fresh review before activation.

Every phase follows the same separation. Once all of its items are done, its `phaseReview` becomes `pending`. A named agent who did not complete any item in that phase must run `review-phase --result pass`; a failed review requires a reason. Subsequent phases remain blocked until every earlier phase has passed review, and Plan completion also requires a passed review for the final phase.

```bash
python3 scripts/planctl.py --root ROOT review-phase \
  --phase phase-1 --result pass --evidence "tests and planned files reviewed" \
  --actor independent-phase-reviewer --actor-type agent
```

## Pause and resume

Pause keeps the plan in `currentPlanSlug`; no other plan can activate while it remains resumable. Resume preserves the original baseline.

```bash
python3 scripts/planctl.py --root ROOT transition \
  --state paused --reason "User paused execution" --actor-type human

python3 scripts/planctl.py --root ROOT transition \
  --state active --reason "User resumed execution" --actor-type human
```

## Complete

```bash
python3 scripts/planctl.py --root ROOT transition \
  --state completed --reason "All work verified" --actor-type human
```

Completion rejects unfinished items, open issues, off-plan changes, planned files that are pending or action-mismatched, and missing required documentation. A completed status snapshot is frozen so later repository changes cannot rewrite its historical result.

## Cancel

```bash
python3 scripts/planctl.py --root ROOT transition \
  --state cancelled --reason "User no longer wants this work" --actor-type human
```

Cancellation releases `currentPlanSlug` and freezes the last status. Terminal plans cannot be mutated or reactivated.

## Replace the current plan

Use `switch` only when the current plan should become terminal. It requires a clean Git tree and an independently approved target draft, cancels the old plan with `replacedBy`, activates the target with a fresh baseline, and updates the registry under one lock.

```bash
python3 scripts/planctl.py --root ROOT switch \
  --to urgent-export-fix \
  --reason "User replaced the current work" \
  --actor-type human
```

The plan manager intentionally does not support switching away from a paused plan and later resuming it in the same worktree. Use separate Git worktrees for resumable parallel execution.
