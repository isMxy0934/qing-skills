# Verify plan work

1. Read the item's purpose, dependencies, verification kind, and exact expected files.
2. Run the smallest reliable check.
3. Record `pass` or `fail` with concise evidence and the real source:
   - `script`: an automated command ran;
   - `llm`: the model reviewed the artifact;
   - `human`: the user confirmed the result.
4. A passing verification may mark an item done only when its dependencies are done.
5. Verification does not override Git coverage. Completion independently rejects missing or mismatched planned files.

```bash
python3 scripts/planctl.py --root ROOT verify \
  --item p1-01 --result pass \
  --evidence "8 tests passed" --verified-by script

python3 scripts/planctl.py --root ROOT verify \
  --item p1-02 --result fail \
  --evidence "3 passed, 1 failed" \
  --reason "rollback leaves an outbox row" \
  --verified-by script

python3 scripts/planctl.py --root ROOT changes
```

`not-run` records an honest event without changing item state. Before requesting completion, run `changes` and ensure `pending`, `mismatched`, and `unexpected` are all zero.
