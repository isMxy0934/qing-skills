# Work on the current plan

1. Run `show`. Work only when the registry state is `active`.
2. If `changeCoverage` shows `offPlanChanges` or a `mismatched` observation, reconcile before picking new work — Git is ahead of `plan.json` (commonly because work happened on another device, or a checkpoint was skipped). Check whether the changed paths plausibly satisfy a not-done item's `purpose`/`plannedFiles`. If they do, actually run that item's declared `verifyKind` check and record the real outcome through `verify` or `update-item --file`; a diff existing is not evidence, it only tells you where to look. If no not-done item plausibly matches, treat it as ordinary off-plan drift: register it or revert it.
3. Read `nextActions`; start only an item whose readiness is `ready`.
4. A later phase remains blocked until every earlier phase has `phaseReview.status = passed`. Do not try to start around this gate; `planctl.py` rejects the transition.
5. Mark it `in-progress` before substantial implementation. Keep only one item in progress.
6. Perform the repository work. Git, not the agent's file report, remains the source of observed changes.
7. If scope grows, register the path with `update-item --file`. Supplying an existing path replaces its expected action, so an incorrect declaration can be fixed.
8. Record done evidence and `verifiedBy`, or stop with a failed/blocked reason. `completedBy` is recorded automatically from the command actor.
9. When the final item in a phase is done, assign a separate reviewer subagent. It must not be any agent recorded as `completedBy` for that phase. Resolve a failed review and record a passing `review-phase` before starting its successor phase.
10. Add an issue only when the problem needs a separate next action.

```bash
python3 scripts/planctl.py --root ROOT update-item \
  --item p1-01 --status in-progress

python3 scripts/planctl.py --root ROOT update-item \
  --item p1-01 --status done \
  --evidence "contract tests: 8 passed" \
  --verified-by script

python3 scripts/planctl.py --root ROOT review-phase \
  --phase phase-1 --result pass \
  --evidence "Reviewed implementation, tests, and declared file actions" \
  --actor phase-reviewer-agent --actor-type agent

python3 scripts/planctl.py --root ROOT checkpoint \
  --item p1-02 \
  --reason "transaction rollback test failed"

python3 scripts/planctl.py --root ROOT add-issue \
  --item p1-02 \
  --title "Rollback leaves an outbox row" \
  --detail "The write is outside the transaction" \
  --next-action "Move the outbox write into the transaction"
```

Paused plans are read-only but retain `currentPlanSlug` and their original baseline. Resume before changing them. Completed and cancelled plans are immutable.
