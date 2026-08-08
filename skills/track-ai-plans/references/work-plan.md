# Work on the current plan

1. Run `show`. Work only when the registry state is `active`.
2. Read `nextActions`; start only an item whose readiness is `ready`.
3. Mark it `in-progress` before substantial implementation. Keep only one item in progress.
4. Perform the repository work. Git, not the agent's file report, remains the source of observed changes.
5. If scope grows, register the path with `update-item --file`. Supplying an existing path replaces its expected action, so an incorrect declaration can be fixed.
6. Record done evidence and `verifiedBy`, or stop with a failed/blocked reason.
7. Add an issue only when the problem needs a separate next action.

```bash
python3 scripts/planctl.py --root ROOT update-item \
  --item p1-01 --status in-progress

python3 scripts/planctl.py --root ROOT update-item \
  --item p1-01 --status done \
  --evidence "contract tests: 8 passed" \
  --verified-by script

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
