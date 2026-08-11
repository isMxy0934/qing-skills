# Manage lifecycle

Lifecycle changes require a reason and `--actor-type human`.

## States

- `draft → active`: non-empty, clean Git baseline, free current slot, and current plan/map review under `single`.
- `active → paused`: keeps `currentPlanSlug`; no other plan can activate.
- `paused → active`: explicit user-authorized resume; preserves the original baseline.
- `active → completed`: all completion gates pass; releases the slot and freezes status.
- non-terminal `→ cancelled`: releases the slot when current and freezes status.

```bash
python3 "$PLANCTL" --root ROOT transition \
  --state paused --reason "User paused execution" --actor-type human

python3 "$PLANCTL" --root ROOT transition \
  --state active --reason "User resumed execution" --actor-type human

python3 "$PLANCTL" --root ROOT transition \
  --state completed --reason "All work and cleanup verified" --actor-type human
```

Paused plans are read-only and are never auto-resumed. Terminal plans are immutable; `show` reads their frozen snapshot so later Git changes cannot rewrite historical file/module impact.

## Replace

`switch` atomically cancels the current plan and activates a reviewed, non-empty draft with a fresh clean baseline:

```bash
python3 "$PLANCTL" --root ROOT switch \
  --to urgent-export-fix --reason "User replaced current work" \
  --actor-type human
```

Use separate Git worktrees for parallel resumable plans. Qing Plans deliberately does not coordinate multiple agents mutating one worktree concurrently.
