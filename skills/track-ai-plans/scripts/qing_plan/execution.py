"""Item execution, verification, checkpoints, issues, and lifecycle."""

from __future__ import annotations

from . import storage as st
from .storage import *
from .git import *
from .domain import *
from .projection import *
from .commands import install_assets


def capture_execution_start(root: Path, item: dict) -> dict:
    files = flatten_changes(item)
    snapshots = [path_snapshot(root, f["path"]) for f in files]
    for file in files:
        if file.get("from"):
            snapshots.append(path_snapshot(root, file["from"]))
    return {"startHead": git_head(root), "startedAt": now(), "plannedSnapshots": snapshots,
            "endHead": None, "endedAt": None, "observedFiles": []}


def capture_execution_end(root: Path, item: dict) -> None:
    execution = item.get("execution")
    if not execution:
        die("item must enter in-progress before completion")
    before = {snapshot["path"]: snapshot for snapshot in execution.get("plannedSnapshots", [])}
    observations = []
    for file in flatten_changes(item):
        previous = before.get(file["path"], {"exists": False, "sha256": None})
        current = path_snapshot(root, file["path"])
        if not previous["exists"] and current["exists"]:
            action = "create"
        elif previous["exists"] and not current["exists"]:
            action = "delete"
        elif previous.get("sha256") != current.get("sha256"):
            action = "modify"
        else:
            action = "unchanged"
        if file["action"] == "move":
            source_before = before.get(file.get("from"), {"exists": False})
            source_now = path_snapshot(root, file["from"])
            if source_before.get("exists") and not source_now["exists"] and current["exists"]:
                action = "move"
        observations.append({"path": file["path"], "plannedAction": file["action"], "observedAction": action,
                             "beforeSha256": previous.get("sha256"), "afterSha256": current.get("sha256"),
                             "from": file.get("from")})
    execution.update({"endHead": git_head(root), "endedAt": now(), "observedFiles": observations})


def sync_execution_attempt(item: dict) -> None:
    attempts = item.setdefault("executionAttempts", [])
    if attempts and item.get("execution"):
        attempts[-1] = copy.deepcopy(item["execution"])


def update_checkpoint_for_item(root: Path, plan: dict, project_map: dict, item: dict, actor: str | None) -> None:
    dirty = git_dirty_paths(root)
    action = next((i for i in all_items(plan) if i["status"] == "in-progress"), None)
    plan["checkpoint"] = {
        "itemId": action["id"] if action else None,
        "lastCompletedItemId": item["id"] if item["status"] == "done" else plan.get("checkpoint", {}).get("lastCompletedItemId"),
        "planRevision": plan["revision"], "projectMapRevision": project_map["revision"],
        "branch": git_branch(root), "headCommit": git_head(root), "stopReason": item.get("reason"),
        "nextAction": None, "createdBy": actor, "createdAt": now(),
        "handoff": {"readiness": "local-only", "dirtyPaths": dirty,
                    "note": "The checkpoint mutation itself must be committed before cross-device handoff"},
    }


def set_item_state(root: Path, plan: dict, project_map: dict, item: dict, state: str,
                   reason: str | None, actor: str | None) -> None:
    allowed = {
        "not-started": {"in-progress", "blocked"},
        "in-progress": {"done", "failed", "blocked"},
        "failed": {"in-progress"},
        "blocked": {"in-progress"},
        "done": set(),
    }
    if state not in allowed.get(item["status"], set()):
        die(f"invalid item transition: {item['status']} -> {state}")
    if state in {"in-progress", "done"} and not dependencies_done(plan, item):
        die("item dependencies are not done")
    if state == "in-progress":
        running = [i["id"] for i in all_items(plan) if i["status"] == "in-progress" and i["id"] != item["id"]]
        if running:
            die(f"another item is in progress: {running[0]}")
        if item["status"] not in {"not-started", "failed", "blocked"}:
            die(f"cannot start item from {item['status']}")
        item["execution"] = capture_execution_start(root, item)
        item.setdefault("executionAttempts", []).append(item["execution"])
    elif state == "done":
        if item["status"] != "in-progress":
            die("item must be in-progress before done")
        capture_execution_end(root, item)
        sync_execution_attempt(item)
        item["completedBy"] = actor
    elif state in {"failed", "blocked"} and not reason:
        die(f"{state} requires --reason")
    elif state in {"failed", "blocked"} and item["status"] == "in-progress" and item.get("execution"):
        capture_execution_end(root, item)
        sync_execution_attempt(item)
    item["status"] = state
    item["reason"] = reason if state in {"failed", "blocked"} else None
    item["updatedAt"] = now()
    update_checkpoint_for_item(root, plan, project_map, item, actor)


def cmd_update_item(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    require_state(entry, {"active"}, "update-item")
    _, item = find_item(plan, args.item)
    if args.status == "done":
        die("use verify --result pass to complete an item")
    project_map = load_project_map(root)
    before = {"status": item["status"], "reason": item.get("reason")}
    set_item_state(root, plan, project_map, item, args.status, args.reason, args.actor)
    event(root, entry["slug"], "item-updated", args.actor, args.actor_type,
          {"itemId": item["id"], "before": before, "after": {"status": item["status"], "reason": item.get("reason")}})
    return save_plan(root, index, entry, plan, project_map)


def cmd_verify(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    require_state(entry, {"active"}, "verify")
    _, item = find_item(plan, args.item)
    required_source = VERIFY_SOURCE_FOR_KIND[item["verifyKind"]]
    if args.verified_by != required_source:
        die(f"verifyKind={item['verifyKind']} requires --verified-by {required_source}")
    if args.result == "fail" and not args.reason:
        die("failed verification requires --reason")
    attempt = {
        "id": f"verify-{uuid.uuid4().hex[:8]}", "kind": item["verifyKind"], "source": args.verified_by,
        "result": args.result, "evidence": args.evidence, "reason": args.reason, "actor": args.actor,
        "headCommit": git_head(root), "timestamp": now(),
    }
    item["verificationAttempts"].append(attempt)
    project_map = load_project_map(root)
    if args.result == "pass":
        set_item_state(root, plan, project_map, item, "done", None, args.actor)
    elif args.result == "fail":
        set_item_state(root, plan, project_map, item, "failed", args.reason, args.actor)
    event(root, entry["slug"], "item-verified", args.actor, args.actor_type, {"itemId": item["id"], "attempt": attempt})
    return save_plan(root, index, entry, plan, project_map)


def cmd_checkpoint(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    require_state(entry, {"active"}, "checkpoint")
    if args.item:
        find_item(plan, args.item)
    project_map = load_project_map(root)
    dirty = git_dirty_paths(root)
    plan["checkpoint"] = {
        "itemId": args.item, "lastCompletedItemId": plan.get("checkpoint", {}).get("lastCompletedItemId"),
        "planRevision": plan["revision"], "projectMapRevision": project_map["revision"],
        "branch": git_branch(root), "headCommit": git_head(root), "stopReason": args.reason,
        "nextAction": args.next_action, "createdBy": args.actor, "createdAt": now(),
        "handoff": {"readiness": "local-only", "dirtyPaths": dirty,
                    "note": "The checkpoint mutation itself must be committed before cross-device handoff"},
    }
    event(root, entry["slug"], "checkpoint-created", args.actor, args.actor_type, {"checkpoint": plan["checkpoint"]})
    return save_plan(root, index, entry, plan, project_map)


def cmd_add_issue(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    require_state(entry, {"active"}, "add-issue")
    if args.item:
        find_item(plan, args.item)
    issue = {"id": f"issue-{uuid.uuid4().hex[:8]}", "itemId": args.item, "title": args.title,
             "detail": args.detail, "severity": args.severity, "status": "open", "nextAction": args.next_action,
             "createdAt": now(), "resolvedAt": None, "resolution": None}
    plan["issues"].append(issue)
    event(root, entry["slug"], "issue-opened", args.actor, args.actor_type, issue)
    return save_plan(root, index, entry, plan)


def cmd_resolve_issue(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    require_state(entry, {"active"}, "resolve-issue")
    issue = next((i for i in plan["issues"] if i["id"] == args.issue), None)
    if not issue or issue["status"] != "open":
        die("unknown or resolved issue")
    issue.update({"status": "resolved", "resolution": args.resolution, "resolvedAt": now()})
    event(root, entry["slug"], "issue-resolved", args.actor, args.actor_type, {"issueId": args.issue, "resolution": args.resolution})
    return save_plan(root, index, entry, plan)


def completion_problems(status: dict, plan: dict) -> list[str]:
    problems = []
    if not plan.get("phases") or not all_items(plan):
        problems.append("plan has no executable items")
    remaining = [i["id"] for i in all_items(plan) if i["status"] != "done"]
    if remaining:
        problems.append(f"remaining items={remaining}")
    open_issues = [i["id"] for i in plan["issues"] if i["status"] == "open"]
    if open_issues:
        problems.append(f"open issues={open_issues}")
    pending_amendments = [a["id"] for a in plan["amendments"] if a["status"] == "pending-review"]
    if pending_amendments:
        problems.append(f"pending amendments={pending_amendments}")
    temp_cleanup = [a["cleanupItemId"] for a in plan["amendments"] if a["kind"] == "temporary" and a["status"] == "applied" and
                    item_map(plan).get(a["cleanupItemId"], {}).get("status") != "done"]
    if temp_cleanup:
        problems.append(f"temporary cleanup incomplete={temp_cleanup}")
    if status["changeCoverage"]["unexpected"]:
        problems.append("off-plan changes exist")
    bad = [f"{d['itemId']}:{d['observation']['path']}" for d in status["derivedIssues"]]
    if bad:
        problems.append(f"planned file checks failed={bad}")
    if status["documentationImpact"].get("completionBlocked"):
        problems.append("documentation impact incomplete")
    return problems


def activation_review_ready(plan: dict, project_map: dict) -> bool:
    if plan["reviewPolicy"] == "none":
        return True
    review = matching_plan_review(plan, project_map)
    return bool(review and review["result"] == "passed")


def cmd_transition(args: argparse.Namespace, root: Path) -> dict:
    require_human(args, f"transition to {args.state}")
    index, entry, plan = selected_plan(args, root)
    old = entry["state"]
    if old in TERMINAL_STATES or args.state == old:
        die(f"invalid transition from {old}")
    allowed = {"draft": {"active", "cancelled"}, "active": {"paused", "completed", "cancelled"}, "paused": {"active", "cancelled"}}
    if args.state not in allowed.get(old, set()):
        die(f"invalid transition: {old} -> {args.state}")
    project_map = load_project_map(root)
    if args.state == "active" and old == "draft":
        if index.get("currentPlanSlug"):
            die(f"current plan already exists: {index['currentPlanSlug']}")
        map_errors = validate_project_map(project_map)
        if map_errors:
            die("project map is invalid; run `validate` and fix it before activation: " + "; ".join(map_errors))
        if not plan.get("phases") or not all_items(plan):
            die("cannot activate an empty plan")
        if not activation_review_ready(plan, project_map):
            die("current plan/map revision needs an independent passed review")
        entry["baselineCommit"] = capture_activation_baseline(root)
        entry["activatedAt"] = now()
        index["currentPlanSlug"] = entry["slug"]
    elif args.state == "active":
        if index.get("currentPlanSlug") != entry["slug"]:
            die("paused plan lost current slot")
    elif args.state == "paused":
        if index.get("currentPlanSlug") != entry["slug"]:
            die("only current plan can pause")
        plan["checkpoint"]["stopReason"] = args.reason
    elif args.state == "completed":
        status = status_projection(entry, plan, root, project_map)
        problems = completion_problems(status, plan)
        if problems:
            die("cannot complete; " + "; ".join(problems))
        index["currentPlanSlug"] = None
    elif args.state == "cancelled" and old in CURRENT_STATES:
        if index.get("currentPlanSlug") != entry["slug"]:
            die("plan does not own current slot")
        index["currentPlanSlug"] = None
    entry["state"] = args.state
    event(root, entry["slug"], "plan-transitioned", args.actor, args.actor_type,
          {"fromState": old, "toState": args.state, "reason": args.reason})
    return save_plan(root, index, entry, plan, project_map)


def cmd_switch(args: argparse.Namespace, root: Path) -> dict:
    require_human(args, "switch")
    index = load_index(root)
    old_slug = index.get("currentPlanSlug")
    if not old_slug:
        die("switch requires a current plan")
    old_entry, new_entry = find_entry(index, old_slug), find_entry(index, args.to)
    if new_entry["state"] != "draft":
        die("switch target must be draft")
    old_plan, new_plan = read_json(plan_path(root, old_slug)), read_json(plan_path(root, args.to))
    project_map = load_project_map(root)
    map_errors = validate_project_map(project_map)
    if map_errors:
        die("project map is invalid; run `validate` and fix it before switching: " + "; ".join(map_errors))
    if not activation_review_ready(new_plan, project_map):
        die("switch target needs review for current plan/map revision")
    if not all_items(new_plan):
        die("switch target is empty")
    baseline = capture_activation_baseline(root)
    old_entry.update({"state": "cancelled", "replacedBy": args.to, "updatedAt": now()})
    old_plan["checkpoint"]["stopReason"] = args.reason
    new_entry.update({"state": "active", "baselineCommit": baseline, "activatedAt": now(), "updatedAt": now()})
    index["currentPlanSlug"] = args.to
    atomic_json(plan_path(root, old_slug), old_plan)
    atomic_json(plan_path(root, args.to), new_plan)
    save_index(root, index)
    event(root, old_slug, "plan-replaced", args.actor, args.actor_type, {"replacedBy": args.to, "reason": args.reason})
    event(root, args.to, "plan-activated", args.actor, args.actor_type, {"replaces": old_slug, "reason": args.reason})
    render_status(root, old_entry, old_plan, project_map)
    return render_status(root, new_entry, new_plan, project_map)


def cmd_validate(args: argparse.Namespace, root: Path) -> dict:
    if st._USING_LEGACY:
        errors = validate_legacy_store(root)
        if errors:
            die("; ".join(errors))
        index = load_index(root)
        return {"valid": True, "store": "plans", "schemaVersion": 1, "readOnly": True,
                "plans": len(index["plans"]), "currentPlanSlug": index.get("currentPlanSlug"),
                "nextAction": "run migrate-store --dry-run"}
    index = load_index(root)
    errors = validate_store(root, index)
    if errors:
        die("; ".join(errors))
    return {"valid": True, "store": "qing-plans", "schemaVersion": 2, "plans": len(index["plans"]),
            "currentPlanSlug": index.get("currentPlanSlug"), "revision": index["revision"],
            "legacySafeToDelete": bool((root / "plans").exists() and verified_migration(root))}


def legacy_show(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    path = status_path(root, entry["slug"])
    if path.exists():
        result = read_json(path)
    else:
        result = {"schemaVersion": 1, "plan": {"slug": entry["slug"], "name": entry.get("name"), "goal": plan.get("goal"), "state": entry.get("state")}}
    result["legacyStore"] = {"path": "plans", "readOnly": True, "nextAction": "migrate-store --dry-run"}
    return result


def cmd_show(args: argparse.Namespace, root: Path) -> dict:
    if st._USING_LEGACY:
        return legacy_show(args, root)
    _, entry, plan = selected_plan(args, root)
    if entry["state"] in TERMINAL_STATES:
        return read_json(status_path(root, entry["slug"]))
    return status_projection(entry, plan, root, load_project_map(root))


def cmd_changes(args: argparse.Namespace, root: Path) -> dict:
    status = cmd_show(args, root)
    return {"changeCoverage": status.get("changeCoverage"), "documentationImpact": status.get("documentationImpact"),
            "moduleImpact": status.get("projectMap")}


def cmd_history(args: argparse.Namespace, root: Path) -> dict:
    _, entry, _ = selected_plan(args, root)
    if args.limit is not None and args.limit < 0:
        die("--limit must be non-negative")
    events = [read_json(path) for path in sorted((store_dir(root) / entry["slug"] / "events").glob("*.json"))]
    if args.limit is not None:
        events = events[-args.limit:]
    return {"planSlug": entry["slug"], "store": store_dir(root).name, "events": events}


def cmd_resume(args: argparse.Namespace, root: Path) -> dict:
    if st._USING_LEGACY:
        index = load_index(root)
        slug = getattr(args, "plan", None) or index.get("currentPlanSlug")
        current = legacy_show(args, root).get("plan") if slug else None
        return {"store": "plans", "readOnly": True, "current": current,
                "unfinishedPlans": [entry["slug"] for entry in index["plans"] if entry.get("state") not in TERMINAL_STATES],
                "nextAction": {"type": "migrate", "message": "Run migrate-store --dry-run before continuing mutations"}}
    index = load_index(root)
    slug = getattr(args, "plan", None) or index.get("currentPlanSlug")
    if not slug:
        drafts = sorted((entry for entry in index["plans"] if entry.get("state") == "draft"),
                        key=lambda entry: (entry.get("updatedAt") or "", entry.get("slug") or ""), reverse=True)
        if not drafts:
            return {"store": "qing-plans", "plan": None, "unfinishedPlans": [],
                    "nextAction": {"type": "no-unfinished-plan", "message": "No current or draft plan exists"}}
        if len(drafts) > 1:
            return {"store": "qing-plans", "plan": None,
                    "unfinishedPlans": [{"slug": entry["slug"], "name": entry["name"], "updatedAt": entry["updatedAt"]} for entry in drafts],
                    "nextAction": {"type": "select-draft", "message": "Choose one unfinished draft with --plan"}}
        slug = drafts[0]["slug"]
    entry = find_entry(index, slug)
    plan = read_json(plan_path(root, slug))
    project_map = load_project_map(root)
    status = read_json(status_path(root, entry["slug"])) if entry["state"] in TERMINAL_STATES else status_projection(entry, plan, root, project_map)
    return {"store": "qing-plans", "plan": status["plan"], "summary": status["summary"],
            "handoff": status["handoff"], "nextAction": status["nextActions"][0],
            "openIssues": [i for i in status["issues"] if i["status"] == "open"] + status["derivedIssues"]}


def cmd_install_dashboard(args: argparse.Namespace, root: Path) -> dict:
    # Refresh only. `create` installs the viewer with the first plan, so an empty store
    # directory here would be a dashboard with no data for it to read.
    if not index_path(root).exists():
        die("no plan store to refresh; `create` installs the dashboard with the first plan")
    return {"installed": install_assets(root, overwrite=True)}


def cmd_refresh_status(args: argparse.Namespace, root: Path) -> dict:
    _, entry, plan = selected_plan(args, root)
    if entry["state"] in TERMINAL_STATES:
        die("terminal status is frozen and cannot be refreshed")
    return render_status(root, entry, plan, load_project_map(root))
