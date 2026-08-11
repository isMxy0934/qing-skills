# Create a V2 plan

`PLANCTL` is this skill's own `scripts/planctl.py`, before and after the first plan exists.

## Choose review policy

- `none`: ordinary work; tests and verification evidence are the review boundary.
- `single`: default for long work; one independent agent reviews the initial immutable plan/map revision and each material amendment.

## Define map, phases, and items

Create the draft, define stable modules and `A dependsOn B` relations, then add phases and small executable items. A file-changing item requires a module, change reason, exact file action, and verification kind.

```bash
python3 "$PLANCTL" --root ROOT create \
  --slug csv-export --name "CSV export" \
  --goal "Let users download a filtered report as CSV" \
  --review-policy single \
  --doc-mode required --doc-target "docs/**:keep operating docs current" \
  --actor planner-agent --actor-type agent

python3 "$PLANCTL" --root ROOT upsert-module \
  --plan csv-export --id reporting --name "Reporting" \
  --description "Assemble report rows from stored records" --path-pattern "src/reporting/**" \
  --reason "Keep row assembly in one place" --evidence "reporting service interface" \
  --actor planner-agent --actor-type agent

python3 "$PLANCTL" --root ROOT add-phase \
  --plan csv-export --id phase-1 --title "Row assembly" \
  --purpose "Get rows correct before any file-format work" \
  --actor planner-agent --actor-type agent

python3 "$PLANCTL" --root ROOT add-item \
  --plan csv-export --phase phase-1 --id p1-01 \
  --title "Add row builder" --purpose "Turn a filter into ordered report rows" \
  --module reporting --change-reason "Give export and preview one shared row source" \
  --file src/reporting/rows.py:create --verify-kind test \
  --actor planner-agent --actor-type agent
```

Use `path:create|modify|delete` or `path:move:from-path`. Use `--no-file-impact` only when repository files genuinely do not change; it maps to `_cross-cutting`.

For a map dependency:

```bash
python3 "$PLANCTL" --root ROOT upsert-module \
  --plan csv-export --id http-api --name "HTTP API" \
  --description "Expose report endpoints" --path-pattern "src/api/**" \
  --reason "Keep transport separate from row assembly" --evidence "route table" \
  --actor planner-agent --actor-type agent

python3 "$PLANCTL" --root ROOT upsert-dependency \
  --plan csv-export --module http-api --depends-on reporting \
  --reason "The download endpoint serves rows the reporting module builds" \
  --evidence "handler imports the row builder" \
  --actor planner-agent --actor-type agent
```

## Review and activate

For `single`, a different agent reviews after every draft edit is finished:

```bash
python3 "$PLANCTL" --root ROOT review-plan \
  --plan csv-export --result pass \
  --evidence "Scope, dependencies, modules, file actions, and checks are coherent" \
  --actor plan-reviewer-agent --actor-type agent

python3 "$PLANCTL" --root ROOT transition \
  --plan csv-export --state active \
  --reason "User approved execution" --actor-type human
```

Activation rejects an empty plan, a stale/missing review under `single`, another current plan, a non-root Git path, a repository without a commit, or dirty files outside the managed Qing Plans files.
