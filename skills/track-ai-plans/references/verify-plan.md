# Record verification evidence

Read the item's purpose, verification kind, declared module/reason/files, dependencies, and start snapshot. Run the smallest reliable check, then append the real outcome.

The source mapping is strict:

| verifyKind | verified-by | Meaning |
|---|---|---|
| `test` | `script` | An automated command actually ran |
| `llm-review` | `llm` | A model inspected the artifact |
| `manual` | `human` | The user or human operator confirmed it |

```bash
python3 "$PLANCTL" --root ROOT verify \
  --item p1-01 --result pass --evidence "pytest: 18 passed" \
  --verified-by script --actor implementer --actor-type agent

python3 "$PLANCTL" --root ROOT verify \
  --item p1-02 --result fail --evidence "17 passed, 1 failed" \
  --reason "A quoted field containing the separator still splits into two columns" \
  --verified-by script --actor implementer --actor-type agent
```

`not-run` honestly records a verification attempt without changing item state. `pass` and `fail` require the item to already be `in-progress`; they capture end `HEAD`, time, hashes, and observed file actions. Restarting a failed/blocked item appends another execution attempt instead of overwriting attribution history.

Verification does not override Git coverage. Before completion, `changes` must show no pending/mismatched/unexpected file and no per-item attribution mismatch.
