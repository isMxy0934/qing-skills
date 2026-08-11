# V2 storage and projections

## Layout

```text
qing-plans/
├── .planctl.lock                 # not committed
├── .gitignore                    # ignores the lock file
├── dashboard.html                # read-only viewer, the only non-data artifact
├── index.json                    # authoritative lifecycle registry
├── project-map.json              # shared, incremental project map
├── migration.json                # only after verified V1 migration
└── <slug>/
    ├── plan.json                 # declared plan + execution history
    ├── status.json               # generated or terminal-frozen projection
    └── events/*.json             # append-only audit records
```

The runtime is never copied here. It stays in the skill and is always invoked as `python3 "$PLANCTL"`, so a repository carries only its own data plus the viewer that reads it, and no installed copy exists that could fall behind the skill writing to it. Everything needed to *read* a store elsewhere — the JSON and the self-contained `dashboard.html` — is committed; mutation needs the skill. `install-dashboard` refreshes the viewer after a skill upgrade.

## Authority

`index.json` alone owns each plan's `state`, `baselineCommit`, replacement link, and the single `currentPlanSlug`. `plan.json` owns goal, review policy/revision, phases/items, reviews, amendments, verification attempts, execution snapshots, checkpoint, and issues.

`project-map.json` is shared by successive plans. Each module has an ID, responsibility, path patterns, reason/evidence for the boundary, and introducing/updating plan. Dependencies store only `{moduleId: A, dependsOn: B, reason, evidence}`. Upstream/downstream and Plan overlays are projections, not duplicate stored graphs.

## Items and stage attribution

Each item has one or more `changeSets` or `noFileImpact: true`:

```json
{
  "moduleId": "reporting",
  "reason": "Give export and preview one shared row source",
  "files": [{"path": "src/reporting/rows.py", "action": "create", "from": null}]
}
```

On `in-progress`, a new append-only `executionAttempts[]` entry captures start `HEAD`, time, and planned path hashes; `execution` points to the current/latest attempt for convenient display. On pass, fail, or block it captures end `HEAD`, time, and before/after hashes with observed actions. Overall baseline coverage still detects off-plan work; the attempt history preserves which stage performed a change even if a retry or later stage touches the same file.

## Immutable review and amendment history

`reviews[]` binds a result to `targetType`, `targetId`, `targetRevision`, and `projectMapRevision`. Draft edits increment revision; old reviews remain audit evidence but no longer authorize activation.

An amendment stores kind, reason, evidence, proposed actor/time, ordered operations, reviews, status, and before/after plan/map revisions. Applied amendments increment the plan revision. Temporary amendments also bind a cleanup item.

## Checkpoint and handoff

The checkpoint stores item, last completed item, plan/map revisions, branch, `HEAD`, stop reason, concrete next action, actor/time, and handoff readiness. `resume` compares current branch/`HEAD`, dirty paths, upstream, and ahead/behind counts, then derives one next action. Only a clean, fully pushed state is `portable`.

## Status

Status combines lifecycle, item readiness, Planned/Observed/Verified file rows, Git change coverage, documentation impact, module overlay and warnings, handoff, amendments, issues, and next action. Read-only `show` and `resume` do not rewrite it. Mutations refresh it. Completion/cancellation freeze it.
