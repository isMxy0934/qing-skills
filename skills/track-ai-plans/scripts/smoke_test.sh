#!/usr/bin/env bash
# Regression test: authoritative registry, clean activation baseline,
# dependency/state guards, exact Git actions, completion gates, frozen terminal
# status, event history, and paused-plan slot ownership.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLANCTL="$SCRIPT_DIR/planctl.py"
WORKDIR="$(mktemp -d)"
trap 'rm -rf "$WORKDIR"' EXIT

P() { python3 "$PLANCTL" --root "$WORKDIR" "$@"; }

pass=0
fail=0
check() {
  local desc="$1" got="$2" want="$3"
  if [ "$got" = "$want" ]; then
    pass=$((pass + 1))
  else
    fail=$((fail + 1))
    echo "FAIL: $desc — expected [$want], got [$got]"
  fi
}
expect_die() {
  local desc="$1"; shift
  if "$@" >/tmp/planctl-smoke-out.$$ 2>&1; then
    fail=$((fail + 1))
    echo "FAIL: $desc — expected rejection"
  else
    pass=$((pass + 1))
  fi
}

mkdir -p "$WORKDIR/packages/contracts" "$WORKDIR/apps/service" "$WORKDIR/docs/architecture" "$WORKDIR/docs/implementation"
git -C "$WORKDIR" init -q
git -C "$WORKDIR" config user.email t@example.com
git -C "$WORKDIR" config user.name t
printf 'baseline\n' > "$WORKDIR/packages/contracts/command.ts"
git -C "$WORKDIR" add packages/contracts/command.ts
git -C "$WORKDIR" commit -qm baseline

# Draft creation does not capture a baseline or occupy the current slot.
P create --slug demo-plan --name "Demo plan" --goal "exercise plan tracking" --owner tester \
  --doc-mode required --doc-coverage all \
  --doc-target "docs/architecture/**:sync architecture" \
  --doc-target "docs/implementation/**:sync implementation" >/dev/null
SCHEMA_VERSIONS="$(python3 -c "import glob,json;paths=['$WORKDIR/plans/index.json','$WORKDIR/plans/demo-plan/plan.json','$WORKDIR/plans/demo-plan/status.json',glob.glob('$WORKDIR/plans/demo-plan/events/*.json')[0]];print(' / '.join(str(json.load(open(p))['schemaVersion']) for p in paths))")"
check "all stored artifacts start at schema version one" "$SCHEMA_VERSIONS" "1 / 1 / 1 / 1"
INDEX_DRAFT="$(python3 -c "import json;d=json.load(open('$WORKDIR/plans/index.json'));e=d['plans'][0];print(str(d['currentPlanSlug'])+' / '+str(e['baselineCommit'])+' / '+e['state'])")"
check "draft has no current slot or baseline" "$INDEX_DRAFT" "None / None / draft"

P add-phase --plan demo-plan --id ph1 --title "Phase one" --purpose "prove plan tracking" >/dev/null
expect_die "item requires file-impact declaration" \
  P add-item --plan demo-plan --phase ph1 --id invalid --title Invalid --purpose invalid --verify-kind test
expect_die "item requires verification kind" \
  P add-item --plan demo-plan --phase ph1 --id invalid --title Invalid --purpose invalid --file x:create

P add-item --plan demo-plan --phase ph1 --id i1 --title Contract --purpose "modify contract" \
  --verify-kind test --file packages/contracts/command.ts:modify >/dev/null
P add-item --plan demo-plan --phase ph1 --id i2 --title Gateway --purpose "create gateway" \
  --depends-on i1 --verify-kind test --file apps/service/gateway.ts:modify >/dev/null
P add-item --plan demo-plan --phase ph1 --id i3 --title Review --purpose "review behavior" \
  --depends-on i2 --verify-kind llm-review --no-file-impact >/dev/null
P add-item --plan demo-plan --phase ph1 --id i4 --title Marker --purpose "create marker" \
  --depends-on i3 --verify-kind test --file marker.txt:create >/dev/null

# Activation is human-only and rejects pre-existing dirty work.
touch "$WORKDIR/preexisting.txt"
expect_die "dirty activation is rejected" \
  P transition --plan demo-plan --state active --reason approved --actor-type human
rm "$WORKDIR/preexisting.txt"
expect_die "activation is human-only" \
  P transition --plan demo-plan --state active --reason approved
P transition --plan demo-plan --state active --reason approved --actor-type human >/dev/null
CURRENT="$(python3 -c "import json;d=json.load(open('$WORKDIR/plans/index.json'));e=d['plans'][0];print(d['currentPlanSlug']+' / '+e['state']+' / '+str(bool(e['baselineCommit'])))")"
check "activation owns slot and captures baseline" "$CURRENT" "demo-plan / active / True"

# Dependencies are enforced for done, not merely displayed as readiness.
expect_die "child cannot pass before dependency" \
  P verify --item i2 --result pass --evidence premature --verified-by script

printf 'updated\n' > "$WORKDIR/packages/contracts/command.ts"
P verify --item i1 --result pass --evidence "contract test passed" --verified-by script >/dev/null

# Off-plan changes are current-plan local and clear only when this plan claims them.
touch "$WORKDIR/apps/service/sneaky.ts"
OFF_BEFORE="$(P show | python3 -c "import json,sys;print(json.load(sys.stdin)['changeCoverage']['unexpected'])")"
check "off-plan file is detected" "$OFF_BEFORE" "1"
P update-item --item i1 --status done --evidence "contract test passed" --verified-by script \
  --file apps/service/sneaky.ts:create >/dev/null
OFF_AFTER="$(P show | python3 -c "import json,sys;print(json.load(sys.stdin)['changeCoverage']['unexpected'])")"
check "current item declaration clears off-plan file" "$OFF_AFTER" "0"

# Exact action semantics: expected modify does not accept observed create.
touch "$WORKDIR/apps/service/gateway.ts"
P verify --item i2 --result pass --evidence "gateway test passed" --verified-by script >/dev/null
MISMATCH="$(P show | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['changeCoverage']['mismatched'])")"
check "create does not satisfy modify" "$MISMATCH" "1"

P verify --item i3 --result pass --evidence "reviewed" --verified-by llm >/dev/null
P verify --item i4 --result pass --evidence "marker test passed" --verified-by script >/dev/null
PLANNED_ISSUES="$(P show | python3 -c "import json,sys;d=json.load(sys.stdin);print(sum(i['type']=='planned-file-mismatch' for i in d['derivedIssues']))")"
check "done-item mismatch and pending file surface as issues" "$PLANNED_ISSUES" "2"
PLANNED_NEXT="$(P show | python3 -c "import json,sys;d=json.load(sys.stdin);print(sum(n['type']=='issue' and n['id'].startswith('derived-planned-file-mismatch-') for n in d['nextActions']))")"
check "planned-file issues appear in nextActions" "$PLANNED_NEXT" "2"
expect_die "completion rejects mismatch and pending file" \
  P transition --state completed --reason done --actor-type human

# Correct the declaration and create the pending file.
P update-item --item i2 --status done --evidence "gateway test passed" --verified-by script \
  --file apps/service/gateway.ts:create >/dev/null
touch "$WORKDIR/marker.txt"
PLANNED_CLEAR="$(P show | python3 -c "import json,sys;d=json.load(sys.stdin);print(sum(i['type']=='planned-file-mismatch' for i in d['derivedIssues']))")"
check "planned-file issues clear when observations match" "$PLANNED_CLEAR" "0"

# A paused plan keeps the current slot, so another draft cannot activate.
P create --slug rival-plan --name Rival --goal rival >/dev/null
P transition --state paused --reason waiting --actor-type human >/dev/null
PAUSED="$(python3 -c "import json;d=json.load(open('$WORKDIR/plans/index.json'));print(d['currentPlanSlug']+' / '+d['plans'][0]['state'])")"
check "paused plan retains current slot" "$PAUSED" "demo-plan / paused"
expect_die "draft cannot activate while a plan is paused" \
  P transition --plan rival-plan --state active --reason try --actor-type human
expect_die "paused plan is read-only" \
  P add-issue --title blocked --detail blocked --next-action resume
P transition --state active --reason resume --actor-type human >/dev/null

# Documentation targets are exact completion gates.
touch "$WORKDIR/docs/architecture/overview.md"
DOC_PARTIAL="$(P show | python3 -c "import json,sys;print(json.load(sys.stdin)['documentationImpact']['status'])")"
check "partial documentation coverage fails" "$DOC_PARTIAL" "fail"
touch "$WORKDIR/docs/implementation/plan.md"
DOC_FULL="$(P show | python3 -c "import json,sys;print(json.load(sys.stdin)['documentationImpact']['status'])")"
check "full documentation coverage passes" "$DOC_FULL" "pass"

P transition --state completed --reason "all verified" --actor-type human >/dev/null
FINAL="$(python3 -c "import json;d=json.load(open('$WORKDIR/plans/index.json'));print(str(d['currentPlanSlug'])+' / '+d['plans'][0]['state'])")"
check "completion releases current slot" "$FINAL" "None / completed"

# Terminal status is frozen and terminal plans are immutable.
FROZEN_AT="$(python3 -c "import json;print(json.load(open('$WORKDIR/plans/demo-plan/status.json'))['generatedAt'])")"
printf 'later change\n' >> "$WORKDIR/packages/contracts/command.ts"
SHOW_AT="$(P show --plan demo-plan | python3 -c "import json,sys;print(json.load(sys.stdin)['generatedAt'])")"
check "completed status is frozen" "$SHOW_AT" "$FROZEN_AT"
expect_die "completed plan cannot gain phases" \
  P add-phase --plan demo-plan --id after --title After --purpose invalid

EVENTS="$(P history --plan demo-plan | python3 -c "import json,sys;print(len(json.load(sys.stdin)['events']) > 5)")"
check "history command reads audit events" "$EVENTS" "True"
P validate >/dev/null
pass=$((pass + 1))

# Switch is terminal replacement, and the repository lock prevents lost updates.
SWITCHDIR="$WORKDIR/switch-repo"
mkdir -p "$SWITCHDIR"
git -C "$SWITCHDIR" init -q
git -C "$SWITCHDIR" config user.email t@example.com
git -C "$SWITCHDIR" config user.name t
git -C "$SWITCHDIR" commit --allow-empty -qm baseline
P2() { python3 "$PLANCTL" --root "$SWITCHDIR" "$@"; }
P2 create --slug old-plan --name Old --goal old --activate --actor-type human >/dev/null
P2 create --slug new-plan --name New --goal new >/dev/null
P2 switch --to new-plan --reason replacement --actor-type human >/dev/null
SWITCHED="$(python3 -c "import json;d=json.load(open('$SWITCHDIR/plans/index.json'));m={e['slug']:e for e in d['plans']};print(d['currentPlanSlug']+' / '+m['old-plan']['state']+' / '+m['old-plan']['replacedBy'])")"
check "switch terminates old plan and activates draft" "$SWITCHED" "new-plan / cancelled / new-plan"

P2 create --slug draft-one --name One --goal one >/dev/null &
PID_ONE=$!
P2 create --slug draft-two --name Two --goal two >/dev/null &
PID_TWO=$!
wait "$PID_ONE"
wait "$PID_TWO"
PLAN_COUNT="$(P2 validate | python3 -c "import json,sys;print(json.load(sys.stdin)['plans'])")"
check "locked concurrent creates preserve both updates" "$PLAN_COUNT" "4"

DASHBOARD="$SCRIPT_DIR/../assets/dashboard.html"
GRAPH_CONTAINER="$(grep -c 'id="plan-graph"' "$DASHBOARD")"
GRAPH_RENDERER="$(grep -c 'function renderPlanGraph' "$DASHBOARD")"
check "dashboard includes Plan DAG container" "$GRAPH_CONTAINER" "1"
check "dashboard includes Plan DAG renderer" "$GRAPH_RENDERER" "1"

echo ""
echo "passed: $pass, failed: $fail"
[ "$fail" -eq 0 ]
