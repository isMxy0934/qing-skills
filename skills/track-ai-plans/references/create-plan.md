# Create and activate a plan

1. Inspect the requested work and choose a 3-64 character lowercase slug.
2. Create a draft before implementation. Draft creation records intent but does not capture a Git baseline.
3. Add phases in execution order.
4. Add small items with purpose, dependencies, exact planned files, and a verification kind. Use `--no-file-impact` only when success genuinely requires no repository file change.
5. Declare documentation impact.
6. Validate and show the draft.
7. After the user approves activation, ensure Git is clean and transition the draft to `active`. Activation captures the current `HEAD` as the fixed baseline.

```bash
python3 scripts/planctl.py --root ROOT create \
  --slug dashboard-migration \
  --name "Dashboard migration" \
  --goal "Move dashboard writes to one command path" \
  --owner "joy.mu" \
  --doc-mode required \
  --doc-coverage all \
  --doc-target "docs/architecture/**:keep module boundaries current"

python3 scripts/planctl.py --root ROOT add-phase \
  --plan dashboard-migration \
  --id phase-1 \
  --title "Command foundation" \
  --purpose "Create the shared command path"

python3 scripts/planctl.py --root ROOT add-item \
  --plan dashboard-migration \
  --phase phase-1 \
  --id p1-01 \
  --title "Add command contract" \
  --purpose "Give human and AI edits one contract" \
  --verify-kind test \
  --file packages/contracts/command.ts:create

python3 scripts/planctl.py --root ROOT validate
python3 scripts/planctl.py --root ROOT transition \
  --plan dashboard-migration \
  --state active \
  --reason "User approved execution" \
  --actor-type human
```

Use `path:action` or `path:move:from-path` for `--file`. Use `--doc-mode none --doc-reason "why"` when documentation was considered and is not expected to change.

Activation fails if another plan is current, the repository has no initial commit, `--root` is not the Git top-level, or the working tree is dirty outside the plan tool's own files.
