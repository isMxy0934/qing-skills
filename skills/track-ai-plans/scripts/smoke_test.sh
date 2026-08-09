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
expect_die "plan creation requires a planner subagent" \
  P create --slug human-plan --name Human --goal invalid --actor human-planner --actor-type human
expect_die "plan creation requires an explicit planner identity" \
  P create --slug unnamed-plan --name Unnamed --goal invalid
P create --slug demo-plan --name "Demo plan" --goal "exercise plan tracking" --owner tester \
  --actor planner-agent --actor-type agent \
  --doc-mode required --doc-coverage all \
  --doc-target "docs/architecture/**:sync architecture" \
  --doc-target "docs/implementation/**:sync implementation" >/dev/null
SCHEMA_VERSIONS="$(python3 -c "import glob,json;paths=['$WORKDIR/plans/index.json','$WORKDIR/plans/demo-plan/plan.json','$WORKDIR/plans/demo-plan/status.json',glob.glob('$WORKDIR/plans/demo-plan/events/*.json')[0]];print(' / '.join(str(json.load(open(p))['schemaVersion']) for p in paths))")"
check "all stored artifacts start at schema version one" "$SCHEMA_VERSIONS" "1 / 1 / 1 / 1"
INDEX_DRAFT="$(python3 -c "import json;d=json.load(open('$WORKDIR/plans/index.json'));e=d['plans'][0];print(str(d['currentPlanSlug'])+' / '+str(e['baselineCommit'])+' / '+e['state'])")"
check "draft has no current slot or baseline" "$INDEX_DRAFT" "None / None / draft"
check "create installs the dashboard automatically" "$(test -f "$WORKDIR/plan-dashboard.html" && echo yes || echo no)" "yes"
PLAN_REVIEW_PENDING="$(python3 -c "import json;d=json.load(open('$WORKDIR/plans/demo-plan/plan.json'));print(d['planner']+' / '+d['planReview']['status'])")"
check "draft records its planner and starts pending review" "$PLAN_REVIEW_PENDING" "planner-agent / pending"
python3 -c "import json; p='$WORKDIR/plans/demo-plan/plan.json'; d=json.load(open(p)); d.pop('phaseReviewGatesEnabled'); open(p, 'w').write(json.dumps(d))"
expect_die "new drafts require phase-review gate metadata" \
  P validate
python3 -c "import json; p='$WORKDIR/plans/demo-plan/plan.json'; d=json.load(open(p)); d['phaseReviewGatesEnabled']=True; open(p, 'w').write(json.dumps(d))"

expect_die "only recorded planner can edit a draft" \
  P add-phase --plan demo-plan --id unauthorized --title Unauthorized --purpose invalid --actor other-agent --actor-type agent
P add-phase --plan demo-plan --id ph1 --title "Phase one" --purpose "prove plan tracking" --actor planner-agent --actor-type agent >/dev/null
P add-phase --plan demo-plan --id ph2 --title "Phase two" --purpose "prove phase-review gate" --actor planner-agent --actor-type agent >/dev/null
expect_die "item requires file-impact declaration" \
  P add-item --plan demo-plan --phase ph1 --id invalid --title Invalid --purpose invalid --verify-kind test --actor planner-agent --actor-type agent
expect_die "item requires verification kind" \
  P add-item --plan demo-plan --phase ph1 --id invalid --title Invalid --purpose invalid --file x:create --actor planner-agent --actor-type agent

P add-item --plan demo-plan --phase ph1 --id i1 --title Contract --purpose "modify contract" \
  --verify-kind test --file packages/contracts/command.ts:modify --actor planner-agent --actor-type agent >/dev/null
P add-item --plan demo-plan --phase ph1 --id i2 --title Gateway --purpose "create gateway" \
  --depends-on i1 --verify-kind test --file apps/service/gateway.ts:modify --actor planner-agent --actor-type agent >/dev/null
P add-item --plan demo-plan --phase ph1 --id i3 --title Review --purpose "review behavior" \
  --depends-on i2 --verify-kind llm-review --no-file-impact --actor planner-agent --actor-type agent >/dev/null
P add-item --plan demo-plan --phase ph2 --id i4 --title Marker --purpose "create marker" \
  --depends-on i3 --verify-kind test --file marker.txt:create --actor planner-agent --actor-type agent >/dev/null

# Activation is human-only and rejects pre-existing dirty work.
touch "$WORKDIR/preexisting.txt"
expect_die "dirty activation is rejected" \
  P transition --plan demo-plan --state active --reason approved --actor-type human
rm "$WORKDIR/preexisting.txt"
expect_die "activation is human-only" \
  P transition --plan demo-plan --state active --reason approved
expect_die "activation requires a passed independent plan review" \
  P transition --plan demo-plan --state active --reason approved --actor-type human
expect_die "planner cannot review their own plan" \
  P review-plan --plan demo-plan --result pass --evidence self-review --actor planner-agent --actor-type agent
expect_die "plan review requires an agent subagent" \
  P review-plan --plan demo-plan --result pass --evidence human-review --actor human-reviewer --actor-type human
expect_die "failed plan review requires a reason" \
  P review-plan --plan demo-plan --result fail --evidence findings --actor reviewer-agent --actor-type agent
P review-plan --plan demo-plan --result fail --evidence findings --reason "missing phase boundary" --actor reviewer-agent --actor-type agent >/dev/null
PLAN_REVIEW_FAILED="$(python3 -c "import json;d=json.load(open('$WORKDIR/plans/demo-plan/plan.json'))['planReview'];print(d['status']+' / '+d['reviewer']+' / '+d['reason'])")"
check "independent reviewer can record a failed review" "$PLAN_REVIEW_FAILED" "failed / reviewer-agent / missing phase boundary"
P review-plan --plan demo-plan --result pass --evidence "complete draft" --actor reviewer-agent --actor-type agent >/dev/null
P set-documentation-impact --plan demo-plan --mode required --coverage all \
  --target "docs/architecture/**:sync architecture" --target "docs/implementation/**:sync implementation" \
  --actor planner-agent --actor-type agent >/dev/null
PLAN_REVIEW_RESET="$(python3 -c "import json;d=json.load(open('$WORKDIR/plans/demo-plan/plan.json'))['planReview'];print(d['status']+' / '+str(d['reviewer']))")"
check "draft structure change invalidates completed review" "$PLAN_REVIEW_RESET" "pending / None"
expect_die "invalidated review blocks activation" \
  P transition --plan demo-plan --state active --reason approved --actor-type human
P review-plan --plan demo-plan --result pass --evidence "re-reviewed complete draft" --actor reviewer-agent --actor-type agent >/dev/null
P transition --plan demo-plan --state active --reason approved --actor-type human >/dev/null
CURRENT="$(python3 -c "import json;d=json.load(open('$WORKDIR/plans/index.json'));e=d['plans'][0];print(d['currentPlanSlug']+' / '+e['state']+' / '+str(bool(e['baselineCommit'])))")"
check "activation owns slot and captures baseline" "$CURRENT" "demo-plan / active / True"

# Dependencies are enforced for done, not merely displayed as readiness.
expect_die "child cannot pass before dependency" \
  P verify --item i2 --result pass --evidence premature --verified-by script

printf 'updated\n' > "$WORKDIR/packages/contracts/command.ts"
P verify --item i1 --result pass --evidence "contract test passed" --verified-by script --actor implementer-agent --actor-type agent >/dev/null

# Off-plan changes are current-plan local and clear only when this plan claims them.
touch "$WORKDIR/apps/service/sneaky.ts"
OFF_BEFORE="$(P show | python3 -c "import json,sys;print(json.load(sys.stdin)['changeCoverage']['unexpected'])")"
check "off-plan file is detected" "$OFF_BEFORE" "1"
P update-item --item i1 --status done --evidence "contract test passed" --verified-by script \
  --file apps/service/sneaky.ts:create --actor implementer-agent --actor-type agent >/dev/null
OFF_AFTER="$(P show | python3 -c "import json,sys;print(json.load(sys.stdin)['changeCoverage']['unexpected'])")"
check "current item declaration clears off-plan file" "$OFF_AFTER" "0"

# Exact action semantics: expected modify does not accept observed create.
touch "$WORKDIR/apps/service/gateway.ts"
P verify --item i2 --result pass --evidence "gateway test passed" --verified-by script --actor implementer-agent --actor-type agent >/dev/null
MISMATCH="$(P show | python3 -c "import json,sys;d=json.load(sys.stdin);print(d['changeCoverage']['mismatched'])")"
check "create does not satisfy modify" "$MISMATCH" "1"

P verify --item i3 --result pass --evidence "reviewed" --verified-by llm --actor implementer-agent --actor-type agent >/dev/null
PHASE_ONE_PENDING="$(P show | python3 -c "import json,sys;d=json.load(sys.stdin);p=d['phases'][0];print(p['phaseReview']['status']+' / '+p['executionGate']['status'])")"
check "completed phase requests independent review" "$PHASE_ONE_PENDING" "pending / open"
expect_die "unreviewed phase blocks subsequent phase" \
  P update-item --item i4 --status in-progress --actor implementer-agent --actor-type agent
expect_die "phase reviewer cannot review their own completed item" \
  P review-phase --phase ph1 --result pass --evidence self-review --actor implementer-agent --actor-type agent
expect_die "failed phase review requires a reason" \
  P review-phase --phase ph1 --result fail --evidence findings --actor phase-reviewer-agent --actor-type agent
P review-phase --phase ph1 --result fail --evidence findings --reason "need boundary check" --actor phase-reviewer-agent --actor-type agent >/dev/null
PHASE_ONE_FAILED="$(P show | python3 -c "import json,sys;print(json.load(sys.stdin)['phases'][0]['phaseReview']['status'])")"
check "failed phase review keeps the phase gate closed" "$PHASE_ONE_FAILED" "failed"
expect_die "failed phase review still blocks subsequent phase" \
  P update-item --item i4 --status in-progress --actor implementer-agent --actor-type agent
P review-phase --phase ph1 --result pass --evidence "boundary checked" --actor phase-reviewer-agent --actor-type agent >/dev/null
PHASE_TWO_GATE="$(P show | python3 -c "import json,sys;print(json.load(sys.stdin)['phases'][1]['executionGate']['status'])")"
check "passed phase review opens the subsequent phase gate" "$PHASE_TWO_GATE" "open"
P update-item --item i4 --status in-progress --actor implementer-agent --actor-type agent >/dev/null
P verify --item i4 --result pass --evidence "marker test passed" --verified-by script --actor implementer-agent --actor-type agent >/dev/null
expect_die "final phase cannot self-review" \
  P review-phase --phase ph2 --result pass --evidence self-review --actor implementer-agent --actor-type agent
P review-phase --phase ph2 --result pass --evidence "marker behavior checked" --actor phase-reviewer-agent --actor-type agent >/dev/null
PLANNED_ISSUES="$(P show | python3 -c "import json,sys;d=json.load(sys.stdin);print(sum(i['type']=='planned-file-mismatch' for i in d['derivedIssues']))")"
check "done-item mismatch and pending file surface as issues" "$PLANNED_ISSUES" "2"
PLANNED_NEXT="$(P show | python3 -c "import json,sys;d=json.load(sys.stdin);print(sum(n['type']=='issue' and n['id'].startswith('derived-planned-file-mismatch-') for n in d['nextActions']))")"
check "planned-file issues appear in nextActions" "$PLANNED_NEXT" "2"
expect_die "completion rejects mismatch and pending file" \
  P transition --state completed --reason done --actor-type human

# Correct the declaration and create the pending file.
P update-item --item i2 --status done --evidence "gateway test passed" --verified-by script \
  --file apps/service/gateway.ts:create --actor implementer-agent --actor-type agent >/dev/null
P review-phase --phase ph1 --result pass --evidence "corrected declaration rechecked" --actor phase-reviewer-agent --actor-type agent >/dev/null
touch "$WORKDIR/marker.txt"
PLANNED_CLEAR="$(P show | python3 -c "import json,sys;d=json.load(sys.stdin);print(sum(i['type']=='planned-file-mismatch' for i in d['derivedIssues']))")"
check "planned-file issues clear when observations match" "$PLANNED_CLEAR" "0"

# A later create must not clobber a dashboard the user or a newer skill version already placed.
echo "<!-- local marker -->" >> "$WORKDIR/plan-dashboard.html"

# A paused plan keeps the current slot, so another draft cannot activate.
P create --slug rival-plan --name Rival --goal rival --actor rival-planner --actor-type agent >/dev/null
check "create does not overwrite an existing dashboard" \
  "$(grep -c 'local marker' "$WORKDIR/plan-dashboard.html")" "1"
P install-dashboard >/dev/null
check "install-dashboard forces a refresh" \
  "$(grep -c 'local marker' "$WORKDIR/plan-dashboard.html")" "0"

# --root pointed at a single plan's own directory must be rejected, not
# silently accepted as if it were the repository root.
expect_die "--root inside a plan's own directory is rejected" \
  python3 "$PLANCTL" --root "$WORKDIR/plans/demo-plan" show

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

# A plan-peer-review-era active plan has planner metadata but no phase gate
# fields. It remains valid and treats its prior phases as passed, while new
# drafts above still require phaseReviewGatesEnabled.
LEGACYDIR="$WORKDIR/legacy-phase-gate-repo"
mkdir -p "$LEGACYDIR"
git -C "$LEGACYDIR" init -q
git -C "$LEGACYDIR" config user.email t@example.com
git -C "$LEGACYDIR" config user.name t
git -C "$LEGACYDIR" commit --allow-empty -qm baseline
P3() { python3 "$PLANCTL" --root "$LEGACYDIR" "$@"; }
P3 create --slug legacy-plan --name Legacy --goal legacy --actor legacy-planner --actor-type agent >/dev/null
P3 add-phase --plan legacy-plan --id legacy-1 --title One --purpose one --actor legacy-planner --actor-type agent >/dev/null
P3 add-phase --plan legacy-plan --id legacy-2 --title Two --purpose two --actor legacy-planner --actor-type agent >/dev/null
P3 add-item --plan legacy-plan --phase legacy-1 --id legacy-i1 --title One --purpose one --verify-kind manual --no-file-impact --actor legacy-planner --actor-type agent >/dev/null
P3 add-item --plan legacy-plan --phase legacy-2 --id legacy-i2 --title Two --purpose two --verify-kind manual --no-file-impact --actor legacy-planner --actor-type agent >/dev/null
P3 review-plan --plan legacy-plan --result pass --evidence reviewed --actor legacy-reviewer --actor-type agent >/dev/null
P3 transition --plan legacy-plan --state active --reason approved --actor-type human >/dev/null
python3 -c "import json; p='$LEGACYDIR/plans/legacy-plan/plan.json'; d=json.load(open(p)); d.pop('phaseReviewGatesEnabled'); [phase.pop('phaseReview') for phase in d['phases']]; [item.pop('completedBy') for phase in d['phases'] for item in phase['items']]; open(p, 'w').write(json.dumps(d))"
LEGACY_VALID="$(P3 validate | python3 -c "import json,sys;print(json.load(sys.stdin)['valid'])")"
check "legacy active plan without phase gates remains valid" "$LEGACY_VALID" "True"
P3 update-item --item legacy-i2 --status in-progress --actor legacy-worker --actor-type agent >/dev/null
LEGACY_GATE="$(P3 show | python3 -c "import json,sys;print(json.load(sys.stdin)['phases'][1]['executionGate']['status'])")"
check "legacy phase is interpreted as passed for a later phase gate" "$LEGACY_GATE" "open"

# Switch is terminal replacement, and the repository lock prevents lost updates.
SWITCHDIR="$WORKDIR/switch-repo"
mkdir -p "$SWITCHDIR"
git -C "$SWITCHDIR" init -q
git -C "$SWITCHDIR" config user.email t@example.com
git -C "$SWITCHDIR" config user.name t
git -C "$SWITCHDIR" commit --allow-empty -qm baseline
P2() { python3 "$PLANCTL" --root "$SWITCHDIR" "$@"; }
P2 create --slug old-plan --name Old --goal old --actor old-planner --actor-type agent >/dev/null
P2 review-plan --plan old-plan --result pass --evidence reviewed --actor old-reviewer --actor-type agent >/dev/null
P2 transition --plan old-plan --state active --reason approved --actor-type human >/dev/null
P2 create --slug unreviewed-plan --name Unreviewed --goal unreviewed --actor unreviewed-planner --actor-type agent >/dev/null
expect_die "switch rejects an unreviewed target draft" \
  P2 switch --to unreviewed-plan --reason replacement --actor-type human
P2 create --slug new-plan --name New --goal new --actor new-planner --actor-type agent >/dev/null
P2 review-plan --plan new-plan --result pass --evidence reviewed --actor new-reviewer --actor-type agent >/dev/null
P2 switch --to new-plan --reason replacement --actor-type human >/dev/null
SWITCHED="$(python3 -c "import json;d=json.load(open('$SWITCHDIR/plans/index.json'));m={e['slug']:e for e in d['plans']};print(d['currentPlanSlug']+' / '+m['old-plan']['state']+' / '+m['old-plan']['replacedBy'])")"
check "switch terminates old plan and activates draft" "$SWITCHED" "new-plan / cancelled / new-plan"

P2 create --slug draft-one --name One --goal one --actor draft-one-planner --actor-type agent >/dev/null &
PID_ONE=$!
P2 create --slug draft-two --name Two --goal two --actor draft-two-planner --actor-type agent >/dev/null &
PID_TWO=$!
wait "$PID_ONE"
wait "$PID_TWO"
PLAN_COUNT="$(P2 validate | python3 -c "import json,sys;print(json.load(sys.stdin)['plans'])")"
check "locked concurrent creates preserve both updates" "$PLAN_COUNT" "5"

DASHBOARD="$SCRIPT_DIR/../assets/dashboard.html"
GRAPH_CONTAINER="$(grep -c 'id="plan-graph"' "$DASHBOARD")"
GRAPH_RENDERER="$(grep -c 'function renderPlanGraph' "$DASHBOARD")"
check "dashboard includes Plan DAG container" "$GRAPH_CONTAINER" "1"
check "dashboard includes Plan DAG renderer" "$GRAPH_RENDERER" "1"
MOBILE_GRID_AREAS="$(grep -c 'grid-template-areas:\"main copy\"' "$DASHBOARD")"
MOBILE_DAG_HINT="$(grep -c '手机端可左右滑动查看完整依赖图' "$DASHBOARD")"
VIEW_MODE_EXCLUSIVE="$(grep -c 'listView.hidden=planView!==\"list\";graphView.hidden=planView!==\"graph\"' "$DASHBOARD")"
check "dashboard gives mobile task cards named layout areas" "$MOBILE_GRID_AREAS" "1"
check "dashboard explains mobile DAG scrolling" "$MOBILE_DAG_HINT" "1"
check "dashboard keeps list and DAG mutually exclusive" "$VIEW_MODE_EXCLUSIVE" "1"
REVIEW_CONTAINER="$(grep -c 'id="reviews"' "$DASHBOARD")"
REVIEW_RENDERER="$(grep -c 'function reviewCard' "$DASHBOARD")"
NEXT_ACTION_RENDERER="$(grep -c '(data.nextActions||\[\]).forEach' "$DASHBOARD")"
check "dashboard includes review gate container" "$REVIEW_CONTAINER" "1"
check "dashboard renders review gate status" "$REVIEW_RENDERER" "1"
check "dashboard renders next actions" "$NEXT_ACTION_RENDERER" "1"

echo ""
echo "passed: $pass, failed: $fail"
[ "$fail" -eq 0 ]
