"""Active-scope amendment operations and independent review."""

from __future__ import annotations

from .storage import *
from .git import *
from .domain import *
from .projection import *
from .commands import upsert_module, upsert_dependency
from .execution import sync_execution_attempt


def parse_operation(value: str) -> dict:
    try:
        operation = json.loads(value)
    except json.JSONDecodeError as exc:
        die(f"invalid --operation JSON: {exc}")
    if not isinstance(operation, dict) or not operation.get("op"):
        die("each --operation must be a JSON object with op")
    required = {
        "add-phase": {"id", "title", "purpose"},
        "add-item": {"phaseId", "id", "title", "purpose", "verifyKind"},
        "add-file": {"itemId", "moduleId", "reason", "path", "action"},
        "remove-file": {"itemId", "path"},
        "upsert-module": {"id", "name", "description", "pathPatterns", "reason", "evidence"},
        "upsert-dependency": {"moduleId", "dependsOn", "reason", "evidence"},
        "set-documentation-impact": {"value"},
    }
    if operation["op"] not in required:
        die(f"unsupported amendment operation: {operation['op']}")
    missing = sorted(key for key in required[operation["op"]] if key not in operation)
    if missing:
        die(f"amendment operation {operation['op']} is missing: {', '.join(missing)}")
    if operation["op"] == "add-file":
        if operation.get("action") not in FILE_ACTIONS or ((operation.get("action") == "move") != bool(operation.get("from"))):
            die("add-file has an invalid action/from combination")
    return operation


def apply_operation(plan: dict, project_map: dict, plan_slug: str, operation: dict) -> bool:
    op, map_changed = operation["op"], False
    if op == "add-phase":
        if any(p["id"] == operation.get("id") for p in plan["phases"]):
            die(f"duplicate phase: {operation.get('id')}")
        plan["phases"].append({"id": operation["id"], "title": operation["title"], "purpose": operation["purpose"], "items": []})
    elif op == "add-item":
        phase = find_phase(plan, operation["phaseId"])
        if operation["id"] in item_map(plan):
            die(f"duplicate item: {operation['id']}")
        changes = operation.get("changeSets", [])
        no_file = operation.get("noFileImpact") is True
        if bool(changes) == no_file:
            die("amended item needs changeSets or noFileImpact, exclusively")
        item = {
            "id": operation["id"], "title": operation["title"], "purpose": operation["purpose"],
            "dependsOn": operation.get("dependsOn", []), "status": "not-started", "verifyKind": operation["verifyKind"],
            "reason": None, "noFileImpact": no_file, "changeSets": changes, "verificationAttempts": [],
            "executionAttempts": [], "execution": None, "completedBy": None, "updatedAt": now(),
        }
        phase["items"].append(item)
    elif op == "add-file":
        _, item = find_item(plan, operation["itemId"])
        module_id = operation.get("moduleId", "_unmapped")
        for existing_set in item["changeSets"]:
            existing_set["files"] = [file for file in existing_set["files"] if file["path"] != operation["path"]]
        item["changeSets"] = [change_set for change_set in item["changeSets"] if change_set["files"]]
        change_set = next((c for c in item["changeSets"] if c["moduleId"] == module_id and c["reason"] == operation["reason"]), None)
        if not change_set:
            change_set = {"moduleId": module_id, "reason": operation["reason"], "files": []}
            item["changeSets"].append(change_set)
        file = {"path": operation["path"], "action": operation["action"], "from": operation.get("from")}
        existing = next((f for f in change_set["files"] if f["path"] == file["path"]), None)
        existing.update(file) if existing else change_set["files"].append(file)
        item["noFileImpact"] = False
    elif op == "remove-file":
        _, item = find_item(plan, operation["itemId"])
        found = any(file["path"] == operation["path"] for change_set in item["changeSets"] for file in change_set["files"])
        if not found:
            die(f"cannot remove undeclared file: {operation['path']}")
        for change_set in item["changeSets"]:
            change_set["files"] = [file for file in change_set["files"] if file["path"] != operation["path"]]
        item["changeSets"] = [change_set for change_set in item["changeSets"] if change_set["files"]]
        item["noFileImpact"] = operation.get("noFileImpact") is True
    elif op == "upsert-module":
        upsert_module(project_map, plan_slug, operation)
        map_changed = True
    elif op == "upsert-dependency":
        upsert_dependency(project_map, plan_slug, operation["moduleId"], operation["dependsOn"], operation["reason"], operation["evidence"])
        map_changed = True
    elif op == "set-documentation-impact":
        plan["documentationImpact"] = operation["value"]
    else:
        die(f"unsupported amendment operation: {op}")
    return map_changed


def apply_amendment(root: Path, plan: dict, project_map: dict, amendment: dict, actor: str | None) -> None:
    before = {"planRevision": plan["revision"], "projectMapRevision": project_map["revision"]}
    map_changed = False
    for operation in amendment["operations"]:
        map_changed = apply_operation(plan, project_map, plan["slug"], operation) or map_changed
    running = next((item for item in all_items(plan) if item["status"] == "in-progress"), None)
    if running and running.get("execution"):
        snapshots = running["execution"].setdefault("plannedSnapshots", [])
        captured = {snapshot["path"] for snapshot in snapshots}
        for file in flatten_changes(running):
            for path in [file["path"], file.get("from")]:
                if path and path not in captured:
                    snapshots.append(path_snapshot(root, path))
                    captured.add(path)
        sync_execution_attempt(running)
    bump_plan_revision(plan)
    if map_changed:
        project_map["revision"] += 1
        project_map["updatedAt"] = now()
    amendment.update({"status": "applied", "appliedBy": actor, "appliedAt": now(), "before": before,
                      "after": {"planRevision": plan["revision"], "projectMapRevision": project_map["revision"]}})


def cmd_propose_amendment(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    require_state(entry, {"active"}, "propose-amendment")
    require_agent(args, "propose-amendment")
    operations = [parse_operation(value) for value in args.operation]
    if args.kind == "temporary" and not args.cleanup_item:
        die("temporary amendment requires --cleanup-item")
    adds_cleanup = any(op.get("op") == "add-item" and op.get("id") == args.cleanup_item for op in operations)
    if args.cleanup_item and args.cleanup_item not in item_map(plan) and not adds_cleanup:
        die("cleanup item must already exist or be added by this amendment")
    preview_plan, preview_map = copy.deepcopy(plan), copy.deepcopy(load_project_map(root))
    for operation in operations:
        apply_operation(preview_plan, preview_map, plan["slug"], operation)
    preview_errors = validate_project_map(preview_map) + validate_plan(entry, preview_plan, preview_map)
    if preview_errors:
        die("invalid amendment: " + "; ".join(preview_errors))
    amendment = {
        "id": f"amend-{uuid.uuid4().hex[:8]}", "kind": args.kind, "reason": args.reason,
        "operations": operations, "evidence": args.evidence, "proposedBy": args.actor, "proposedAt": now(),
        "cleanupItemId": args.cleanup_item, "status": "pending-review" if plan["reviewPolicy"] == "single" else "applied",
        "reviews": [], "before": None, "after": None, "appliedBy": None, "appliedAt": None,
    }
    plan["amendments"].append(amendment)
    project_map = load_project_map(root)
    if plan["reviewPolicy"] == "none":
        apply_amendment(root, plan, project_map, amendment, args.actor)
        errors = validate_project_map(project_map) + validate_plan(entry, plan, project_map)
        if errors:
            die("applied amendment is invalid: " + "; ".join(errors))
    event(root, entry["slug"], "amendment-proposed", args.actor, args.actor_type, {"amendment": amendment})
    return save_plan(root, index, entry, plan, project_map)


def cmd_review_amendment(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    require_state(entry, {"active"}, "review-amendment")
    require_agent(args, "review-amendment")
    amendment = next((a for a in plan["amendments"] if a["id"] == args.amendment), None)
    if not amendment or amendment["status"] != "pending-review":
        die("unknown or non-pending amendment")
    if args.actor == amendment["proposedBy"]:
        die("amendment proposer cannot review it")
    if args.result == "fail" and not args.reason:
        die("failed amendment review requires --reason")
    project_map = load_project_map(root)
    review = {
        "id": f"review-{uuid.uuid4().hex[:8]}", "targetType": "amendment", "targetId": amendment["id"],
        "targetRevision": plan["revision"], "projectMapRevision": project_map["revision"], "reviewer": args.actor,
        "result": "passed" if args.result == "pass" else "failed", "evidence": args.evidence,
        "reason": args.reason, "reviewedAt": now(),
    }
    amendment["reviews"].append(review)
    plan["reviews"].append(review)
    if args.result == "pass":
        apply_amendment(root, plan, project_map, amendment, args.actor)
        errors = validate_project_map(project_map) + validate_plan(entry, plan, project_map)
        if errors:
            die("applied amendment is invalid: " + "; ".join(errors))
    else:
        amendment["status"] = "rejected"
    event(root, entry["slug"], "amendment-reviewed", args.actor, args.actor_type, {"review": review, "status": amendment["status"]})
    return save_plan(root, index, entry, plan, project_map)
