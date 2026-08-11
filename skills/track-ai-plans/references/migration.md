# Migrate `plans/` to `qing-plans/`

V2 recognizes a repository containing only V1 `plans/`. In that state, `validate`, `show`, `changes`, `history`, and `resume` are read-only; every mutation is rejected.

## Safe sequence

1. Validate the old store and confirm read-only discovery.
2. Run a dry run. It validates V1 and reports plan/event counts plus source hashes without creating `qing-plans/`.
3. Commit the entire working tree, including `plans/`; the real migration accepts no dirty path except its own `plans/.planctl.lock`, so rollback always has a Git anchor.
4. Run the real migration. It builds a staging store, converts every plan/event/status, installs the dashboard, validates V2, writes a verified manifest, then atomically publishes `qing-plans/`.
5. Keep `plans/` and the root `plan-dashboard.html` until the command reports `safeToDeleteLegacy: true`.
6. After optional deletion, run V2 validation again. The tool never deletes legacy files automatically.

```bash
python3 "$PLANCTL" --root ROOT validate
python3 "$PLANCTL" --root ROOT migrate-store --dry-run
python3 "$PLANCTL" --root ROOT migrate-store
python3 "$PLANCTL" --root ROOT validate
```

## Conversion

- V1 `planReview` becomes an immutable revision-1 review.
- Phase review data remains under `legacyPhaseReview` for audit but creates no V2 phase gate.
- `plannedFiles` becomes an `_unmapped` change set using the item purpose as reason.
- Existing evidence becomes a synthetic legacy verification attempt.
- Checkpoints gain plan/map revision, branch/commit, next action, and `unknown` legacy handoff readiness.
- Completed/cancelled status is transformed and frozen; it is never recomputed from today's Git tree.
- Project map begins with `_unmapped` and `_cross-cutting` and is refined by later plans.

If both directories exist without a verified `qing-plans/migration.json`, the tool refuses to choose. With a verified manifest, `qing-plans/` is authoritative and `plans/` stays read-only until the user removes it.
