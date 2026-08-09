# Create and activate a plan

1. Inspect the requested work and choose a 3-64 character lowercase slug.
2. Assign one named planner subagent to create the draft before implementation. Draft creation records its identity and intent but does not capture a Git baseline; it also installs `plan-dashboard.html` if this is the first plan in the repository.
3. The same planner subagent adds phases in execution order, small items with purpose, dependencies, exact planned files, and a verification kind, then declares documentation impact. Use `--no-file-impact` only when success genuinely requires no repository file change.
4. Validate and show the draft.
5. Assign a different named reviewer subagent to run `review-plan`. A failing review records the feedback; any later draft structure change resets the review to `pending`, so it must be reviewed again.
6. After the reviewer passes and the user approves activation, ensure Git is clean and transition the draft to `active`. Activation captures the current `HEAD` as the fixed baseline.
7. Commit `plans/` (and `plan-dashboard.html`, if this activation just installed it) before writing any code. This is the durable line between what was planned and what actually happened, and it is what makes the plan visible from another device.

```bash
python3 scripts/planctl.py --root ROOT create \
  --slug dashboard-migration \
  --name "Dashboard migration" \
  --goal "Move dashboard writes to one command path" \
  --owner "joy.mu" \
  --actor planner-agent --actor-type agent \
  --doc-mode required \
  --doc-coverage all \
  --doc-target "docs/architecture/**:keep module boundaries current"

python3 scripts/planctl.py --root ROOT add-phase \
  --plan dashboard-migration \
  --id phase-1 \
  --title "Command foundation" \
  --purpose "Create the shared command path" \
  --actor planner-agent --actor-type agent

python3 scripts/planctl.py --root ROOT add-item \
  --plan dashboard-migration \
  --phase phase-1 \
  --id p1-01 \
  --title "Add command contract" \
  --purpose "Give human and AI edits one contract" \
  --verify-kind test \
  --file packages/contracts/command.ts:create \
  --actor planner-agent --actor-type agent

python3 scripts/planctl.py --root ROOT validate
python3 scripts/planctl.py --root ROOT review-plan \
  --plan dashboard-migration --result pass \
  --evidence "Dependencies, file actions, and verification criteria are complete" \
  --actor plan-reviewer-agent --actor-type agent
python3 scripts/planctl.py --root ROOT transition \
  --plan dashboard-migration \
  --state active \
  --reason "User approved execution" \
  --actor-type human
```

Use `path:action` or `path:move:from-path` for `--file`. Use `--doc-mode none --doc-reason "why"` when documentation was considered and is not expected to change.

`review-plan` rejects the planner as reviewer and requires an agent identity distinct from the recorded planner. Activation fails if that independent review has not passed, another plan is current, the repository has no initial commit, `--root` is not the Git top-level, or the working tree is dirty outside the plan tool's own files.
