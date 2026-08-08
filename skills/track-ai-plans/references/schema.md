# V2 storage schema

V2 separates lifecycle registry, declared plan content, observed status, and audit events.

## Layout

```text
plans/
├── .planctl.lock
├── index.json
└── <slug>/
    ├── plan.json
    ├── status.json
    └── events/
        └── <timestamp>-<event>-<id>.json
```

## Authoritative registry

`index.json` is authoritative, not generated. It is the only source for lifecycle state, activation baseline, replacement linkage, and the current-plan slot.

```json
{
  "schemaVersion": 2,
  "revision": 12,
  "currentPlanSlug": "dashboard-migration",
  "updatedAt": "ISO-8601",
  "plans": [
    {
      "slug": "dashboard-migration",
      "name": "Dashboard migration",
      "state": "active",
      "path": "dashboard-migration/plan.json",
      "createdAt": "ISO-8601",
      "updatedAt": "ISO-8601",
      "activatedAt": "ISO-8601",
      "baselineCommit": "git commit captured on first activation",
      "replacedBy": null
    }
  ]
}
```

States are `draft`, `active`, `paused`, `completed`, and `cancelled`. Exactly one `active` or `paused` entry must equal `currentPlanSlug`; otherwise `currentPlanSlug` is null. Drafts have no baseline. Terminal entries are immutable.

## Declared plan content

`plan.json` never stores lifecycle state or baseline.

```json
{
  "schemaVersion": 2,
  "slug": "dashboard-migration",
  "goal": "Move dashboard writes to one command path",
  "owner": "joy.mu",
  "createdAt": "ISO-8601",
  "updatedAt": "ISO-8601",
  "currentPhaseId": "phase-1",
  "documentationImpact": {
    "mode": "required",
    "coverage": "all",
    "reason": null,
    "targets": [
      {"pattern": "docs/architecture/**", "purpose": "keep boundaries current"}
    ]
  },
  "phases": [
    {
      "id": "phase-1",
      "title": "Command foundation",
      "purpose": "Create the shared path",
      "items": [
        {
          "id": "p1-01",
          "title": "Add command contract",
          "purpose": "Use one contract",
          "dependsOn": [],
          "status": "not-started",
          "verifyKind": "test",
          "verifiedBy": "unverified",
          "evidence": null,
          "reason": null,
          "noFileImpact": false,
          "plannedFiles": [
            {"path": "packages/contracts/command.ts", "action": "create", "from": null}
          ],
          "updatedAt": "ISO-8601"
        }
      ]
    }
  ],
  "checkpoint": {
    "currentItemId": null,
    "lastCompletedItemId": null,
    "stopReason": null,
    "updatedAt": "ISO-8601"
  },
  "issues": []
}
```

Every item has a verification kind and exactly one file-impact mode: non-empty `plannedFiles`, or `noFileImpact: true`.

## Generated and frozen status

For active and paused plans, `show` derives status from the registry baseline and current Git tree. Each successful mutation refreshes `status.json`. On completion or cancellation, the final status is frozen; later Git activity cannot rewrite history.

`changeCoverage` contains `planned`, `observed`, `pending`, `mismatched`, `unexpected`, and `offPlanChanges`. Completion requires `pending = mismatched = unexpected = 0` for done items and exact action/source matches.

If a done item still has a `pending` or `action-mismatch` observation, status emits a critical `planned-file-mismatch` derived issue. It contributes to `summary.openIssues` and `nextActions`, then disappears automatically when the declaration and Git observation agree.

The dashboard derives its Plan DAG from `phases[].items[].dependsOn` in this status projection. There is no persisted graph file or second dependency model.

Event files are append-only audit records. Use `planctl.py history --plan SLUG` to read them. They are not a replay database.
