# Manage the plan lifecycle

Every lifecycle command requires a reason and `--actor-type human`.

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

Use `switch` only when the current plan should become terminal. It requires a clean Git tree, cancels the old plan with `replacedBy`, activates a draft with a fresh baseline, and updates the registry under one lock.

```bash
python3 scripts/planctl.py --root ROOT switch \
  --to urgent-export-fix \
  --reason "User replaced the current work" \
  --actor-type human
```

The plan manager intentionally does not support switching away from a paused plan and later resuming it in the same worktree. Use separate Git worktrees for resumable parallel execution.
