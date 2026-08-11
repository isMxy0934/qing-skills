#!/usr/bin/env bash
# Generate a deterministic, non-production Qing Plans store for dashboard QA.
set -euo pipefail

if [ "$#" -ne 1 ]; then
  echo "usage: $0 ROOT" >&2
  exit 2
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLANCTL="$SCRIPT_DIR/planctl.py"
FIXTURE_ROOT="$1"

if [ -e "$FIXTURE_ROOT/qing-plans" ]; then
  echo "refusing to overwrite existing store: $FIXTURE_ROOT/qing-plans" >&2
  exit 2
fi

mkdir -p "$FIXTURE_ROOT"
if [ ! -d "$FIXTURE_ROOT/.git" ]; then
  git -C "$FIXTURE_ROOT" init -q
  git -C "$FIXTURE_ROOT" config user.email dashboard-fixture@example.invalid
  git -C "$FIXTURE_ROOT" config user.name dashboard-fixture
  printf 'dashboard fixture\n' >"$FIXTURE_ROOT/fixture.txt"
  git -C "$FIXTURE_ROOT" add fixture.txt
  git -C "$FIXTURE_ROOT" commit -qm "dashboard fixture baseline"
fi

P() {
  python3 "$PLANCTL" --root "$FIXTURE_ROOT" "$@" >/dev/null
}

P create --slug dashboard-scale --name "Dashboard Scale Fixture" \
  --goal "Validate Phase overview, one-at-a-time task graphs, and task-scoped module impact with a deliberately large dependency model" \
  --review-policy single --doc-mode none --doc-reason "Synthetic dashboard fixture" \
  --actor fixture-planner --actor-type agent

P upsert-module --plan dashboard-scale --id platform --name Platform --description "Runtime and shared infrastructure" \
  --path-pattern 'src/platform/**' --reason "Exercise foundational impact" --evidence "dashboard fixture" \
  --actor fixture-planner --actor-type agent
P upsert-module --plan dashboard-scale --id data --name Data --description "Persistence and data access" \
  --path-pattern 'src/data/**' --reason "Exercise storage impact" --evidence "dashboard fixture" \
  --actor fixture-planner --actor-type agent
P upsert-module --plan dashboard-scale --id domain --name Domain --description "Business rules and contracts" \
  --path-pattern 'src/domain/**' --reason "Exercise domain impact" --evidence "dashboard fixture" \
  --actor fixture-planner --actor-type agent
P upsert-module --plan dashboard-scale --id api --name API --description "Application service boundary" \
  --path-pattern 'src/api/**' --reason "Exercise service impact" --evidence "dashboard fixture" \
  --actor fixture-planner --actor-type agent
P upsert-module --plan dashboard-scale --id experience --name Experience --description "User-facing product surfaces" \
  --path-pattern 'src/experience/**' --reason "Exercise UI impact" --evidence "dashboard fixture" \
  --actor fixture-planner --actor-type agent
P upsert-module --plan dashboard-scale --id docs --name Docs --description "Architecture and operating documentation" \
  --path-pattern 'docs/**' --reason "Exercise documentation impact" --evidence "dashboard fixture" \
  --actor fixture-planner --actor-type agent

P upsert-dependency --plan dashboard-scale --module data --depends-on platform --reason "Data uses platform runtime" --evidence "fixture topology" --actor fixture-planner --actor-type agent
P upsert-dependency --plan dashboard-scale --module domain --depends-on data --reason "Domain reads persisted state" --evidence "fixture topology" --actor fixture-planner --actor-type agent
P upsert-dependency --plan dashboard-scale --module api --depends-on domain --reason "API exposes domain behavior" --evidence "fixture topology" --actor fixture-planner --actor-type agent
P upsert-dependency --plan dashboard-scale --module experience --depends-on api --reason "Experience calls the API" --evidence "fixture topology" --actor fixture-planner --actor-type agent
P upsert-dependency --plan dashboard-scale --module docs --depends-on domain --reason "Docs describe domain contracts" --evidence "fixture topology" --actor fixture-planner --actor-type agent

previous_merge=""
for number in $(seq 1 12); do
  printf -v suffix '%02d' "$number"
  phase_id="phase-$suffix"
  prepare="p${suffix}-prepare"
  left="p${suffix}-experience"
  right="p${suffix}-api"
  merge="p${suffix}-merge"

  P add-phase --plan dashboard-scale --id "$phase_id" --title "Delivery Wave $suffix" \
    --purpose "Validate scalable Phase navigation and scoped impact" --actor fixture-planner --actor-type agent

  prepare_args=(add-item --plan dashboard-scale --phase "$phase_id" --id "$prepare" --title "Prepare contracts $suffix" \
    --purpose "Prepare the domain contract for wave $suffix" --module domain --change-reason "Define wave $suffix contracts" \
    --file "src/domain/wave-$suffix-contract.ts:modify" --verify-kind test --actor fixture-planner --actor-type agent)
  if [ -n "$previous_merge" ]; then
    prepare_args+=(--depends-on "$previous_merge")
  fi
  P "${prepare_args[@]}"

  P add-item --plan dashboard-scale --phase "$phase_id" --id "$left" --title "Build experience $suffix" \
    --purpose "Implement the user-facing branch for wave $suffix" --depends-on "$prepare" \
    --module experience --change-reason "Expose wave $suffix in the product" \
    --file "src/experience/wave-$suffix-view.tsx:modify" --verify-kind test --actor fixture-planner --actor-type agent
  P add-item --plan dashboard-scale --phase "$phase_id" --id "$right" --title "Build API $suffix" \
    --purpose "Implement the service branch for wave $suffix" --depends-on "$prepare" \
    --module api --change-reason "Serve wave $suffix contracts" \
    --file "src/api/wave-$suffix-route.ts:modify" --verify-kind test --actor fixture-planner --actor-type agent
  P add-item --plan dashboard-scale --phase "$phase_id" --id "$merge" --title "Merge and document $suffix" \
    --purpose "Join both branches and document wave $suffix" --depends-on "$left,$right" \
    --module docs --change-reason "Record the integrated wave $suffix behavior" \
    --file "docs/wave-$suffix.md:modify" --verify-kind manual --actor fixture-planner --actor-type agent

  previous_merge="$merge"
done

P refresh-status --plan dashboard-scale
printf 'Dashboard fixture created at %s/qing-plans/dashboard.html\n' "$FIXTURE_ROOT"
