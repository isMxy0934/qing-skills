# Execute and amend a plan

## Resume before work

```bash
python3 "$PLANCTL" --root ROOT validate
python3 "$PLANCTL" --root ROOT resume
```

Report the checkpoint branch/commit, portability, warnings, current item or blocker, and deterministic next action. Do not auto-resume a paused plan or hijack an unrelated user request merely because a plan exists.

When no plan is current, `resume` discovers a single unfinished draft and reports whether it needs definition, review, or human activation. If several drafts exist, it returns `select-draft` with candidates; choose explicitly with `--plan`.

## Execute one item

```bash
python3 "$PLANCTL" --root ROOT update-item \
  --item p1-01 --status in-progress --actor implementer --actor-type agent

# edit files and run the declared check

python3 "$PLANCTL" --root ROOT verify \
  --item p1-01 --result pass --evidence "12 row-builder tests passed" \
  --verified-by script --actor implementer --actor-type agent
```

Only one item may be in progress. Dependencies must be done. `done` is available only through a passing verification so an item cannot bypass append-only evidence. A failed or blocked state requires a reason.

## Track and resolve issues

Record a blocker as an issue instead of leaving it implicit in a checkpoint note. An open issue (including one the tool derives itself from a planned-file or attribution mismatch) blocks completion.

```bash
python3 "$PLANCTL" --root ROOT add-issue \
  --item p1-01 --title "Row order is not stable across runs" \
  --detail "Rows come back in database order, so two exports of the same filter differ" \
  --next-action "Sort by the report's declared key, then rerun the export tests" \
  --severity critical --actor implementer --actor-type agent

python3 "$PLANCTL" --root ROOT resolve-issue \
  --issue issue-12345678 --resolution "Added an explicit sort; export tests pass" \
  --actor implementer --actor-type agent
```

`--item` is optional for issues that are not scoped to a single item. Use `history` (optionally `--limit N`) to read the plan's append-only event log when reconstructing what happened and why.

## Amend active scope

Do not use draft commands or direct JSON edits on an active plan. Propose JSON operations. Supported operation names are `add-phase`, `add-item`, `add-file`, `remove-file`, `upsert-module`, `upsert-dependency`, and `set-documentation-impact`. `add-file` is an upsert: if the path already exists on that item, it can correct its action, reason, or module without leaving duplicate declarations. `remove-file` may set `"noFileImpact": true` when it removes the final path.

```bash
python3 "$PLANCTL" --root ROOT propose-amendment \
  --kind corrective --reason "Real records contain the separator, which the row builder does not escape" \
  --evidence "Exporting order 4471 shifted every column after the address field" \
  --operation '{"op":"add-file","itemId":"p1-01","moduleId":"reporting","reason":"Escape separators before rows reach the writer","path":"src/reporting/escaping.py","action":"create"}' \
  --actor implementer --actor-type agent
```

With `none`, a valid amendment applies immediately. With `single`, it remains `pending-review` until a different agent passes it:

```bash
python3 "$PLANCTL" --root ROOT review-amendment \
  --amendment amend-12345678 --result pass \
  --evidence "Change is necessary and bounded" \
  --actor amendment-reviewer --actor-type agent
```

A temporary amendment must name `--cleanup-item`; that item may already exist or be added by the same amendment. Completion remains blocked until it is done.

## Checkpoint

```bash
python3 "$PLANCTL" --root ROOT checkpoint \
  --item p1-02 --reason "Row order is not stable across runs" \
  --next-action "Sort by the report's declared key, then rerun the export tests" \
  --actor implementer --actor-type agent
```

Commit and push code plus `qing-plans/` before changing computers. `portable` means the tree is clean and `HEAD` has no commits ahead of its upstream. A dirty tree, missing upstream, or unpushed commit is `local-only`; `resume` reports dirty paths and push state so the agent does not overclaim handoff readiness.
