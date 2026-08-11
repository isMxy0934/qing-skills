#!/usr/bin/env bash
# V2 regression: review policies, project map, immutable amendments/evidence,
# execution attribution, handoff, terminal freezing, and safe V1 migration.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PLANCTL="$SCRIPT_DIR/planctl.py"
TEST_ROOT="$(mktemp -d)"
trap 'rm -rf "$TEST_ROOT"' EXIT

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
  if "$@" >"$TEST_ROOT/expected-failure.out" 2>&1; then
    fail=$((fail + 1))
    echo "FAIL: $desc — expected rejection"
  else
    pass=$((pass + 1))
  fi
}
new_repo() {
  local root="$1"
  mkdir -p "$root"
  git -C "$root" init -q
  git -C "$root" config user.email test@example.com
  git -C "$root" config user.name test
  printf 'baseline\n' >"$root/baseline.txt"
  git -C "$root" add baseline.txt
  git -C "$root" commit -qm baseline
}

###############################################################################
# single: stale reviews, map, amendments, attribution, resume, frozen terminal.
###############################################################################
V2="$TEST_ROOT/v2-single"
new_repo "$V2"
printf '# Existing instructions\n' >"$V2/AGENTS.md"
git -C "$V2" add AGENTS.md
git -C "$V2" commit -qm agents
P() { python3 "$PLANCTL" --root "$V2" "$@"; }

P create --slug demo-plan --name "Demo plan" --goal "Exercise V2" \
  --review-policy single --doc-mode none --doc-reason "No public contract changes" \
  --actor planner-agent --actor-type agent >/dev/null
check "new store uses qing-plans" "$(test -f "$V2/qing-plans/index.json" && test ! -e "$V2/plans" && echo yes)" "yes"
check "no runtime code is written into the repository" \
  "$(find "$V2/qing-plans" \( -name '*.py' -o -name '*.pyc' -o -name 'qing_plan' -o -name '.runtime-version' \) | wc -l | tr -d ' ')" "0"
check "dashboard moved inside qing-plans" "$(test -f "$V2/qing-plans/dashboard.html" && test ! -e "$V2/plan-dashboard.html" && echo yes)" "yes"
check "AGENTS.md is left untouched" "$(grep -c 'qing-plans:start' "$V2/AGENTS.md" || true)" "0"
check "all root artifacts use schema V2" "$(python3 -c "import json;print(json.load(open('$V2/qing-plans/index.json'))['schemaVersion'],json.load(open('$V2/qing-plans/project-map.json'))['schemaVersion'])")" "2 2"
check "resume discovers the only unfinished draft" "$(P resume | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["plan"]["slug"],d["nextAction"]["type"])')" "demo-plan plan-empty"
expect_die "empty plan cannot activate" P transition --plan demo-plan --state active --reason approved --actor-type human

P upsert-module --plan demo-plan --id runtime --name Runtime --description "Plan state" \
  --path-pattern 'src/runtime/**' --reason "Track plan state" --evidence "runtime ownership" \
  --actor planner-agent --actor-type agent >/dev/null
P add-phase --plan demo-plan --id phase-1 --title Foundation --purpose "Build runtime" \
  --actor planner-agent --actor-type agent >/dev/null
expect_die "file item requires module and reason" \
  P add-item --plan demo-plan --phase phase-1 --id invalid --title Invalid --purpose Invalid \
    --verify-kind test --file src/runtime/main.py:create --actor planner-agent --actor-type agent
P add-item --plan demo-plan --phase phase-1 --id i1 --title Runtime --purpose "Change runtime" \
  --verify-kind test --module runtime --change-reason "Create portable runtime" \
  --file src/runtime/main.py:create --actor planner-agent --actor-type agent >/dev/null
check "unfinished reviewed-policy draft requests review" "$(P resume | python3 -c 'import json,sys;print(json.load(sys.stdin)["nextAction"]["type"])')" "review-plan"
P review-plan --plan demo-plan --result pass --evidence "Plan is coherent" \
  --actor reviewer-agent --actor-type agent >/dev/null
P upsert-module --plan demo-plan --id dashboard --name Dashboard --description "Read projections" \
  --path-pattern 'ui/**' --reason "Present review state" --evidence "dashboard contract" \
  --actor planner-agent --actor-type agent >/dev/null
expect_die "map edit makes prior plan review stale" \
  P transition --plan demo-plan --state active --reason approved --actor-type human
P upsert-dependency --plan demo-plan --module dashboard --depends-on runtime \
  --reason "Dashboard reads status" --evidence "status contract" \
  --actor planner-agent --actor-type agent >/dev/null
P review-plan --plan demo-plan --result pass --evidence "Current plan and map reviewed" \
  --actor reviewer-agent --actor-type agent >/dev/null
touch "$V2/dirty.txt"
expect_die "activation rejects dirty user files" P transition --plan demo-plan --state active --reason approved --actor-type human
rm "$V2/dirty.txt"
P transition --plan demo-plan --state active --reason approved --actor-type human >/dev/null
check "single review activates current plan" "$(python3 -c "import json;d=json.load(open('$V2/qing-plans/index.json'));print(d['currentPlanSlug'],d['plans'][0]['state'])")" "demo-plan active"

status_hash_before="$(shasum -a 256 "$V2/qing-plans/demo-plan/status.json" | cut -d' ' -f1)"
P show >/dev/null
P resume >/dev/null
status_hash_after="$(shasum -a 256 "$V2/qing-plans/demo-plan/status.json" | cut -d' ' -f1)"
check "show and resume are read-only" "$status_hash_after" "$status_hash_before"

P update-item --item i1 --status in-progress --actor worker-agent --actor-type agent >/dev/null
check "in-progress captures start snapshot" "$(python3 -c "import json;d=json.load(open('$V2/qing-plans/demo-plan/plan.json'));e=d['phases'][0]['items'][0]['execution'];print(bool(e['startHead']),e['plannedSnapshots'][0]['exists'])")" "True False"
P propose-amendment --kind corrective --reason "Add generated manifest" --evidence "Runtime needs discovery" \
  --operation '{"op":"add-file","itemId":"i1","moduleId":"runtime","reason":"Expose runtime manifest","path":"src/runtime/manifest.json","action":"create"}' \
  --actor worker-agent --actor-type agent >/dev/null
AMENDMENT="$(python3 -c "import json;print(json.load(open('$V2/qing-plans/demo-plan/plan.json'))['amendments'][0]['id'])")"
check "single amendment waits for independent review" "$(python3 -c "import json;print(json.load(open('$V2/qing-plans/demo-plan/plan.json'))['amendments'][0]['status'])")" "pending-review"
check "resume prioritizes amendment gate" "$(P resume | python3 -c 'import json,sys;print(json.load(sys.stdin)["nextAction"]["type"])')" "amendment-gate"
expect_die "amendment proposer cannot self-review" P review-amendment --amendment "$AMENDMENT" --result pass --evidence self --actor worker-agent --actor-type agent
P review-amendment --amendment "$AMENDMENT" --result pass --evidence "Bounded correction" \
  --actor amendment-reviewer --actor-type agent >/dev/null
check "applied amendment records before and after revisions" "$(python3 -c "import json; a=json.load(open('$V2/qing-plans/demo-plan/plan.json'))['amendments'][0];print(a['status'],a['before']['planRevision'] < a['after']['planRevision'])")" "applied True"

mkdir -p "$V2/src/runtime"
printf 'print("ok")\n' >"$V2/src/runtime/main.py"
printf '{}\n' >"$V2/src/runtime/manifest.json"
plan_hash_before="$(shasum -a 256 "$V2/qing-plans/demo-plan/plan.json" | cut -d' ' -f1)"
P refresh-status >/dev/null
check "explicit status refresh observes Git without changing plan" \
  "$(P show | python3 -c 'import json,sys;print(json.load(sys.stdin)["changeCoverage"]["observed"])')/$(shasum -a 256 "$V2/qing-plans/demo-plan/plan.json" | cut -d' ' -f1)" \
  "2/$plan_hash_before"
expect_die "verification source must match kind" P verify --item i1 --result pass --evidence ok --verified-by llm
P verify --item i1 --result not-run --evidence "test scheduled" --verified-by script --actor worker-agent --actor-type agent >/dev/null
P verify --item i1 --result fail --evidence "one transient failure" --reason "fixture race" \
  --verified-by script --actor worker-agent --actor-type agent >/dev/null
check "resume prioritizes failed work" "$(P resume | python3 -c 'import json,sys;print(json.load(sys.stdin)["nextAction"]["type"])')" "address-item"
P update-item --item i1 --status in-progress --actor worker-agent --actor-type agent >/dev/null
P verify --item i1 --result pass --evidence "runtime tests passed" --verified-by script \
  --actor worker-agent --actor-type agent >/dev/null
check "verification and execution retries are append-only" "$(python3 -c "import json; i=json.load(open('$V2/qing-plans/demo-plan/plan.json'))['phases'][0]['items'][0];print(len(i['verificationAttempts']),len(i['executionAttempts']),i['status'])")" "3 2 done"
check "retry history preserves the attempt that created each file" \
  "$(python3 -c "import json;i=json.load(open('$V2/qing-plans/demo-plan/plan.json'))['phases'][0]['items'][0];print('|'.join(','.join(o['observedAction'] for o in a['observedFiles']) for a in i['executionAttempts']))")" \
  "create,create|unchanged,unchanged"
check "module relations derive upstream/downstream" "$(P show | python3 -c 'import json,sys;d=json.load(sys.stdin);m={x["id"]:x for x in d["projectMap"]["modules"]};print(m["dashboard"]["upstream"],m["runtime"]["downstream"])')" "['runtime'] ['dashboard']"
check "resume reaches completion checks" "$(P resume | python3 -c 'import json,sys;print(json.load(sys.stdin)["nextAction"]["type"])')" "completion-check"
P checkpoint --reason "Ready to complete" --next-action "Run completion transition" \
  --actor worker-agent --actor-type agent >/dev/null
check "dirty code checkpoint is local-only" "$(P resume | python3 -c 'import json,sys;print(json.load(sys.stdin)["handoff"]["portability"])')" "local-only"
git -C "$V2" add AGENTS.md qing-plans src
git -C "$V2" commit -qm "portable checkpoint"
git init --bare -q "$TEST_ROOT/v2-remote.git"
git -C "$V2" remote add origin "$TEST_ROOT/v2-remote.git"
git -C "$V2" push -qu origin HEAD
check "committed code and plan checkpoint become portable" "$(P resume | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["handoff"]["portability"],len(d["handoff"]["currentDirtyPaths"]))')" "portable 0"
P transition --state completed --reason "All verified" --actor-type human >/dev/null
check "terminal freeze retains final observed file/module impact" \
  "$(P show --plan demo-plan | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["changeCoverage"]["observed"],d["summary"]["changedModules"],d["nextActions"][0]["type"])')" \
  "2 1 terminal"
FROZEN="$(shasum -a 256 "$V2/qing-plans/demo-plan/status.json" | cut -d' ' -f1)"
printf '# later\n' >>"$V2/src/runtime/main.py"
P show --plan demo-plan >/dev/null
check "terminal status stays frozen" "$(shasum -a 256 "$V2/qing-plans/demo-plan/status.json" | cut -d' ' -f1)" "$FROZEN"
expect_die "terminal plan is immutable" P add-issue --plan demo-plan --title Later --detail Later --next-action Later
P validate >/dev/null

###############################################################################
# none: automatic temporary amendment and cleanup completion gate.
###############################################################################
NONE="$TEST_ROOT/v2-none"
new_repo "$NONE"
N() { python3 "$PLANCTL" --root "$NONE" "$@"; }
N create --slug quick-plan --name Quick --goal "Test none" --review-policy none \
  --doc-mode none --doc-reason "No docs" --actor planner --actor-type agent >/dev/null
N upsert-module --plan quick-plan --id core --name Core --description Core --path-pattern 'core/**' \
  --reason "Own quick-plan files" --evidence "test fixture" --actor planner --actor-type agent >/dev/null
N add-phase --plan quick-plan --id p1 --title Work --purpose Work --actor planner --actor-type agent >/dev/null
N add-item --plan quick-plan --phase p1 --id main --title Main --purpose Main --verify-kind test \
  --module core --change-reason Main --file core/main.txt:create --actor planner --actor-type agent >/dev/null
N add-item --plan quick-plan --phase p1 --id cleanup --title Cleanup --purpose Cleanup --depends-on main \
  --verify-kind manual --no-file-impact --actor planner --actor-type agent >/dev/null
N transition --plan quick-plan --state active --reason approved --actor-type human >/dev/null
N propose-amendment --kind temporary --reason "Temporary marker" --evidence "Needed during rollout" \
  --cleanup-item cleanup --operation '{"op":"add-file","itemId":"main","moduleId":"core","reason":"Temporary marker","path":"core/temp.txt","action":"create"}' \
  --actor worker --actor-type agent >/dev/null
check "none applies valid amendment immediately" "$(python3 -c "import json;print(json.load(open('$NONE/qing-plans/quick-plan/plan.json'))['amendments'][0]['status'])")" "applied"
N update-item --item main --status in-progress --actor worker --actor-type agent >/dev/null
mkdir -p "$NONE/core"; touch "$NONE/core/main.txt" "$NONE/core/temp.txt"
N verify --item main --result pass --evidence passed --verified-by script --actor worker --actor-type agent >/dev/null
expect_die "temporary cleanup blocks completion" N transition --state completed --reason done --actor-type human
N update-item --item cleanup --status in-progress --actor worker --actor-type agent >/dev/null
N verify --item cleanup --result pass --evidence "marker cleanup confirmed" --verified-by human --actor user-confirmation --actor-type human >/dev/null
N transition --state completed --reason done --actor-type human >/dev/null
check "none plan completes after cleanup" "$(N show --plan quick-plan | python3 -c 'import json,sys;print(json.load(sys.stdin)["plan"]["state"])')" "completed"

###############################################################################
# V1: read-only discovery, dry run, verified atomic migration, both-dir rule.
###############################################################################
LEGACY="$TEST_ROOT/legacy"
new_repo "$LEGACY"
mkdir -p "$LEGACY/plans/old-plan/events" "$LEGACY/plans/active-plan/events"
python3 - "$LEGACY" <<'PY'
import json, subprocess, sys
from pathlib import Path
root = Path(sys.argv[1]); stamp = "2026-01-01T00:00:00Z"
head = subprocess.check_output(["git", "-C", str(root), "rev-parse", "HEAD"], text=True).strip()
entry = {"slug":"old-plan","name":"Old plan","state":"completed","path":"old-plan/plan.json","createdAt":stamp,"updatedAt":stamp,"activatedAt":stamp,"baselineCommit":head,"replacedBy":None}
active_entry = {"slug":"active-plan","name":"Active plan","state":"active","path":"active-plan/plan.json","createdAt":stamp,"updatedAt":stamp,"activatedAt":stamp,"baselineCommit":head,"replacedBy":None}
index = {"schemaVersion":1,"revision":7,"currentPlanSlug":"active-plan","updatedAt":stamp,"plans":[entry,active_entry]}
item = {"id":"i1","title":"Old item","purpose":"Modify baseline","dependsOn":[],"status":"done","verifyKind":"test","verifiedBy":"script","completedBy":"worker","evidence":"old tests passed","reason":None,"noFileImpact":False,"plannedFiles":[{"path":"baseline.txt","action":"modify","from":None}],"updatedAt":stamp}
review = {"status":"passed","reviewer":"reviewer","evidence":"old review","reason":None,"reviewedAt":stamp}
plan = {"schemaVersion":1,"slug":"old-plan","goal":"Legacy goal","owner":"owner","planner":"planner","phaseReviewGatesEnabled":True,"planReview":review,"createdAt":stamp,"updatedAt":stamp,"currentPhaseId":"p1","documentationImpact":{"mode":"none","coverage":"all","reason":"none","targets":[]},"phases":[{"id":"p1","title":"Old phase","purpose":"Old","phaseReview":review,"items":[item]}],"checkpoint":{"currentItemId":None,"lastCompletedItemId":"i1","stopReason":None,"updatedAt":stamp},"issues":[]}
status = {"schemaVersion":1,"generatedAt":stamp,"plan":{"slug":"old-plan","state":"completed"},"changeCoverage":{"planned":1,"observed":1,"pending":0,"mismatched":0,"unexpected":0},"documentationImpact":{"status":"skipped"},"derivedIssues":[]}
event = {"schemaVersion":1,"eventId":"legacy-event","occurredAt":stamp,"type":"item-verified","planSlug":"old-plan","actor":"worker","actorType":"agent","details":{}}
active_item = {"id":"next","title":"Continue work","purpose":"Resume after migration","dependsOn":[],"status":"not-started","verifyKind":"manual","verifiedBy":"unverified","completedBy":None,"evidence":None,"reason":None,"noFileImpact":True,"plannedFiles":[],"updatedAt":stamp}
active_plan = {**plan,"slug":"active-plan","goal":"Continue legacy work","currentPhaseId":"p1","phases":[{"id":"p1","title":"Continue","purpose":"Resume","phaseReview":{"status":"not-ready","reviewer":None,"evidence":None,"reason":None,"reviewedAt":None},"items":[active_item]}],"checkpoint":{"currentItemId":None,"lastCompletedItemId":None,"stopReason":"moved computers","updatedAt":stamp}}
active_event = {**event,"eventId":"active-event","planSlug":"active-plan","type":"plan-transitioned"}
for path, data in [(root/'plans/index.json',index),(root/'plans/old-plan/plan.json',plan),(root/'plans/old-plan/status.json',status),(root/'plans/old-plan/events/legacy.json',event),(root/'plans/active-plan/plan.json',active_plan),(root/'plans/active-plan/events/legacy.json',active_event)]:
    path.write_text(json.dumps(data), encoding='utf-8')
PY
git -C "$LEGACY" add plans
git -C "$LEGACY" commit -qm legacy
L() { python3 "$PLANCTL" --root "$LEGACY" "$@"; }
check "legacy validate is read-only V1" "$(L validate | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["store"],d["readOnly"])')" "plans True"
legacy_before="$(git -C "$LEGACY" status --porcelain)"
L show --plan old-plan >/dev/null; L history --plan old-plan >/dev/null; L resume --plan old-plan >/dev/null
check "legacy reads create no qing store" "$(test ! -e "$LEGACY/qing-plans" && [ "$(git -C "$LEGACY" status --porcelain)" = "$legacy_before" ] && echo yes)" "yes"
expect_die "legacy mutation is rejected" L add-issue --plan old-plan --title X --detail X --next-action X
check "dry run reports counts without writes" "$(L migrate-store --dry-run | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["dryRun"],d["plans"],d["events"])')" "True 2 2"
check "dry run still creates no qing store" "$(test ! -e "$LEGACY/qing-plans" && echo yes)" "yes"
L migrate-store >/dev/null
check "migration preserves legacy source" "$(test -f "$LEGACY/plans/index.json" && test -f "$LEGACY/qing-plans/migration.json" && echo yes)" "yes"
check "migrated store validates in the both-directory state" "$(L validate | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["store"],d["legacySafeToDelete"])')" "qing-plans True"
check "migration installs the viewer without any runtime" "$(test -f "$LEGACY/qing-plans/dashboard.html" && test ! -e "$LEGACY/qing-plans/planctl.py" && test ! -e "$LEGACY/qing-plans/qing_plan" && echo yes)" "yes"
check "active V1 plan gets a resumable V2 status" "$(L resume | python3 -c 'import json,sys;d=json.load(sys.stdin);print(d["plan"]["slug"],d["plan"]["state"],d["nextAction"]["type"])')" "active-plan active start-item"
check "legacy fields convert without recomputing terminal status" "$(python3 -c "import json;p=json.load(open('$LEGACY/qing-plans/old-plan/plan.json'));s=json.load(open('$LEGACY/qing-plans/old-plan/status.json'));print(p['schemaVersion'],p['phases'][0]['items'][0]['changeSets'][0]['moduleId'],len(p['reviews']),s['generatedAt'])")" "2 _unmapped 1 2026-01-01T00:00:00Z"
check "a migrated done item's frozen observation reads as matched, not pending" \
  "$(python3 -c "import json;o=json.load(open('$LEGACY/qing-plans/old-plan/status.json'))['phases'][0]['items'][0]['observations'][0];print(o['path'],o['observedAction'],o['observedState'])")" \
  "baseline.txt modify change-observed"
check "migrated terminal status includes readiness and the two-level graph projection" \
  "$(python3 -c "import json;s=json.load(open('$LEGACY/qing-plans/old-plan/status.json'));i=s['phases'][0]['items'][0];p=s['phaseGraph']['phases'][0];print(i['readiness'],i['blockedBy'],p['moduleIds'],p['fileCount'],[n['itemId'] for n in p['taskGraph']['nodes']])")" \
  "done [] ['_unmapped'] 1 ['i1']"
check "migration manifest contains source hashes" "$(python3 -c "import json;m=json.load(open('$LEGACY/qing-plans/migration.json'));print(m['state'],m['safeToDeleteLegacy'],len(m['sourceFiles'])>0)")" "verified True True"
python3 - "$LEGACY/qing-plans/migration.json" <<'PY'
import json,sys
p=sys.argv[1]; d=json.load(open(p)); d['state']='incomplete'; d['safeToDeleteLegacy']=False; open(p,'w').write(json.dumps(d))
PY
expect_die "both directories without verified manifest conflict" L validate
python3 - "$LEGACY/qing-plans/migration.json" <<'PY'
import json,sys
p=sys.argv[1]; d=json.load(open(p)); d['state']='verified'; d['safeToDeleteLegacy']=True; open(p,'w').write(json.dumps(d))
PY
rm -rf "$LEGACY/plans"
check "V2 remains valid after user deletes verified legacy store" "$(L validate | python3 -c 'import json,sys;print(json.load(sys.stdin)["valid"])')" "True"

###############################################################################
# Regression coverage for review-timing and graph-integrity fixes.
###############################################################################
REG="$TEST_ROOT/v2-regressions"
new_repo "$REG"
R() { python3 "$PLANCTL" --root "$REG" "$@"; }

R create --slug reg-plan --name "Regressions" --goal "Guard fixed defects" \
  --review-policy single --doc-mode none --doc-reason "No public contract changes" \
  --actor planner-agent --actor-type agent >/dev/null
R upsert-module --plan reg-plan --id mod-a --name A --description "Module A" \
  --path-pattern 'a/**' --reason r --evidence e --actor planner-agent --actor-type agent >/dev/null
R upsert-module --plan reg-plan --id mod-b --name B --description "Module B" \
  --path-pattern 'b/**' --reason r --evidence e --actor planner-agent --actor-type agent >/dev/null
R upsert-dependency --plan reg-plan --module mod-a --depends-on mod-b \
  --reason r --evidence e --actor planner-agent --actor-type agent >/dev/null
expect_die "a module dependency cycle is rejected before it is saved" \
  R upsert-dependency --plan reg-plan --module mod-b --depends-on mod-a --reason r --evidence e \
    --actor planner-agent --actor-type agent
check "the rejected cycle left no dependency behind" \
  "$(python3 -c "import json;d=json.load(open('$REG/qing-plans/project-map.json'));print(len(d['dependencies']))")" "1"

R add-phase --plan reg-plan --id phase-1 --title Phase --purpose x --actor planner-agent --actor-type agent >/dev/null
R add-item --plan reg-plan --phase phase-1 --id i1 --title Item --purpose x --module mod-a \
  --change-reason x --file a/f.txt:modify --verify-kind test --actor planner-agent --actor-type agent >/dev/null
R add-phase --plan reg-plan --id phase-2 --title Followup --purpose x --actor planner-agent --actor-type agent >/dev/null
R add-item --plan reg-plan --phase phase-2 --id i2 --title Followup --purpose x --depends-on i1 \
  --no-file-impact --verify-kind manual --actor planner-agent --actor-type agent >/dev/null
R review-plan --plan reg-plan --result pass --evidence ok --actor reviewer-agent --actor-type agent >/dev/null
R transition --plan reg-plan --state active --reason ok --actor-type human >/dev/null
check "phase graph derives phase flow, direct impact, and per-phase task boundaries" \
  "$(R show | python3 -c 'import json,sys;g=json.load(sys.stdin)["phaseGraph"];p={x["id"]:x for x in g["phases"]};incoming=p["phase-2"]["taskGraph"]["incomingDependencies"];print(p["phase-2"]["dependsOn"],p["phase-1"]["affects"],p["phase-1"]["moduleIds"],p["phase-1"]["fileCount"],[(e["dependsOn"],e["itemId"],e["fromPhaseId"]) for e in incoming])')" \
  "['phase-1'] ['phase-2'] ['mod-a'] 1 [('i1', 'i2', 'phase-1')]"
R propose-amendment --kind temporary --reason "Needs follow-up cleanup" --evidence "Scoped workaround" \
  --operation '{"op":"add-item","phaseId":"phase-1","id":"i1-cleanup","title":"Cleanup","purpose":"Undo the workaround","verifyKind":"manual","noFileImpact":true}' \
  --cleanup-item i1-cleanup --actor implementer-agent --actor-type agent >/dev/null
check "a pending temporary amendment naming its own not-yet-applied cleanup item is still valid" \
  "$(R validate | python3 -c 'import json,sys;print(json.load(sys.stdin)["valid"])')" "True"

check "AGENTS.md is never created by this skill" "$(test -e "$REG/AGENTS.md" && echo yes || echo no)" "no"
check "the store stays free of runtime code through a full plan lifecycle" \
  "$(find "$REG/qing-plans" \( -name '*.py' -o -name '*.pyc' -o -name 'qing_plan' -o -name '.runtime-version' \) | wc -l | tr -d ' ')" "0"
check "install-dashboard refreshes the viewer and nothing else" \
  "$(R install-dashboard | python3 -c 'import json,sys;print(",".join(sorted(p.rsplit("/",1)[-1] for p in json.load(sys.stdin)["installed"])))')" ".gitignore,dashboard.html"

DASHBOARD_FIXTURE="$TEST_ROOT/dashboard-fixture"
"$SCRIPT_DIR/create_dashboard_fixture.sh" "$DASHBOARD_FIXTURE" >/dev/null
check "dashboard fixture exercises scale, Phase flow, and per-Phase branch graphs" \
  "$(python3 "$PLANCTL" --root "$DASHBOARD_FIXTURE" show --plan dashboard-scale | python3 -c 'import json,sys;g=json.load(sys.stdin)["phaseGraph"];print(len(g["phases"]),len(g["dependencies"]),len(g["phases"][0]["taskGraph"]["nodes"]),len(g["phases"][0]["taskGraph"]["dependencies"]))')" \
  "12 11 4 4"
expect_die "dashboard fixture refuses to overwrite an existing store" \
  "$SCRIPT_DIR/create_dashboard_fixture.sh" "$DASHBOARD_FIXTURE"

mkdir -p "$REG/a"
printf 'work in progress\n' >"$REG/a/f.txt"
R update-item --plan reg-plan --item i1 --status in-progress --actor worker-agent --actor-type agent >/dev/null
R checkpoint --plan reg-plan --item i1 --reason "Stopping midway for the day" \
  --next-action "Finish i1, then verify" --actor worker-agent --actor-type agent >/dev/null
git -C "$REG" add -A
git -C "$REG" commit -qm "checkpoint: i1 in progress" >/dev/null
check "committing the checkpoint together with code raises no false HEAD-divergence warning" \
  "$(R resume | python3 -c 'import json,sys;w=json.load(sys.stdin)["handoff"]["warnings"];print(any("HEAD" in x for x in w))')" "False"

###############################################################################
# A repository with no store yet: clear guidance, and no leftover directory.
###############################################################################
FRESH="$TEST_ROOT/no-store-yet"
new_repo "$FRESH"
F() { python3 "$PLANCTL" --root "$FRESH" "$@"; }

expect_die "install-dashboard refuses to run before a store exists" F install-dashboard
check "a refusal names the command that creates the store" \
  "$(F validate 2>&1 >/dev/null | grep -c 'run `create`')" "1"
check "a command that writes nothing leaves no store directory behind" \
  "$(test -e "$FRESH/qing-plans" && echo leftover || echo clean)" "clean"
check "the repository stays clean after failed commands" "$(git -C "$FRESH" status --porcelain)" ""
F create --slug first-plan --name First --goal "Start the store" \
  --actor planner-agent --actor-type agent >/dev/null
check "create still builds the store and installs the viewer" \
  "$(test -f "$FRESH/qing-plans/index.json" && test -f "$FRESH/qing-plans/dashboard.html" && echo yes)" "yes"

python3 -m py_compile "$SCRIPT_DIR/planctl.py" "$SCRIPT_DIR"/qing_plan/*.py
check "source package compiles" "$?" "0"

echo "track-ai-plans V2 smoke tests: $pass passed, $fail failed"
test "$fail" -eq 0
