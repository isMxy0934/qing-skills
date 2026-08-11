"""Read-only status, handoff, coverage, and module projections."""

from __future__ import annotations

from .storage import *
from .git import *
from .domain import *


def compute_change_coverage(plan: dict, change_map: dict[str, dict]) -> dict:
    covered, item_observations = set(), {}
    for item in all_items(plan):
        observations = []
        for expected in flatten_changes(item):
            covered.add(expected["path"])
            observed = change_map.get(expected["path"])
            if observed is None:
                state = "pending"
            elif observed["action"] != expected["action"]:
                state = "action-mismatch"
            elif expected["action"] == "move" and observed.get("from") != expected.get("from"):
                state = "action-mismatch"
            else:
                state = "change-observed"
            observations.append({
                "path": expected["path"], "moduleId": expected.get("moduleId"), "reason": expected.get("reason"),
                "plannedAction": expected["action"], "plannedFrom": expected.get("from"),
                "observedAction": observed.get("action") if observed else None,
                "observedFrom": observed.get("from") if observed else None, "observedState": state,
            })
        item_observations[item["id"]] = observations
    doc_patterns = [target["pattern"] for target in (plan.get("documentationImpact") or {}).get("targets", [])]
    off_plan = [
        {"path": path, "action": info["action"]}
        for path, info in sorted(change_map.items())
        if path not in covered and not any(fnmatch.fnmatch(path, pattern) for pattern in doc_patterns)
    ]
    observations = [value for values in item_observations.values() for value in values]
    return {
        "planned": len(observations), "observed": sum(v["observedState"] == "change-observed" for v in observations),
        "pending": sum(v["observedState"] == "pending" for v in observations),
        "mismatched": sum(v["observedState"] == "action-mismatch" for v in observations),
        "unexpected": len(off_plan), "offPlanChanges": off_plan, "items": item_observations,
    }


def compute_documentation_impact(plan: dict, changes: dict[str, dict], has_baseline: bool) -> dict:
    impact = plan.get("documentationImpact") or {"mode": "none", "reason": "not declared"}
    if impact.get("mode") == "none":
        return {"status": "skipped", **impact}
    if not has_baseline:
        return {"status": "skipped", **impact, "message": "plan is not active"}
    matched, missing = [], []
    for target in impact.get("targets", []):
        paths = [path for path in changes if fnmatch.fnmatch(path, target["pattern"])]
        (matched if paths else missing).append({"pattern": target["pattern"], "matchedPaths": paths} if paths else target["pattern"])
    ok = not missing if impact.get("coverage") == "all" else bool(matched)
    return {
        **impact, "status": "pass" if ok else "fail", "matchedTargets": len(matched),
        "totalTargets": len(impact.get("targets", [])), "missingTargets": missing, "completionBlocked": not ok,
    }


def module_relations(project_map: dict, module_id: str) -> tuple[list[str], list[str]]:
    upstream = sorted({d["dependsOn"] for d in project_map.get("dependencies", []) if d["moduleId"] == module_id})
    downstream = sorted({d["moduleId"] for d in project_map.get("dependencies", []) if d["dependsOn"] == module_id})
    return upstream, downstream


def project_map_projection(plan: dict, project_map: dict) -> dict:
    direct_ids = {change.get("moduleId", "_unmapped") for item in all_items(plan) for change in item.get("changeSets", [])}
    if any(item.get("noFileImpact") is True for item in all_items(plan)):
        direct_ids.add("_cross-cutting")
    direct = sorted(direct_ids)
    affected = set()
    for module_id in direct:
        upstream, downstream = module_relations(project_map, module_id)
        affected.update(upstream + downstream)
    affected.difference_update(direct)
    modules = []
    for module in project_map.get("modules", []):
        upstream, downstream = module_relations(project_map, module["id"])
        modules.append({**module, "upstream": upstream, "downstream": downstream,
                        "impact": "changed" if module["id"] in direct else "affected" if module["id"] in affected else "unchanged"})
    warnings = []
    normal = [m for m in project_map.get("modules", []) if not m["id"].startswith("_")]
    for item in all_items(plan):
        for file in flatten_changes(item):
            if file.get("moduleId") == "_unmapped":
                warnings.append({"type": "unmapped", "itemId": item["id"], "path": file["path"]})
            matches = [m["id"] for m in normal if any(fnmatch.fnmatch(file["path"], p) for p in m.get("pathPatterns", []))]
            if len(matches) > 1:
                warnings.append({"type": "ambiguous", "itemId": item["id"], "path": file["path"], "modules": matches})
            elif matches and file.get("moduleId") not in matches:
                warnings.append({"type": "module-mismatch", "itemId": item["id"], "path": file["path"], "matchedModule": matches[0]})
    return {"revision": project_map.get("revision", 0), "modules": modules,
            "dependencies": project_map.get("dependencies", []), "directModules": direct,
            "affectedModules": sorted(affected), "warnings": warnings}


def phase_graph_projection(plan: dict) -> dict:
    """Project phase flow plus the task graph owned by each phase."""
    phases = plan.get("phases", [])
    items = {
        item["id"]: item
        for phase in phases
        for item in phase.get("items", [])
    }
    item_phase = {
        item["id"]: phase["id"]
        for phase in phases
        for item in phase.get("items", [])
    }
    dependencies: set[tuple[str, str]] = set()
    for phase in phases:
        for item in phase.get("items", []):
            for dependency in item.get("dependsOn", []):
                upstream = item_phase.get(dependency)
                if upstream and upstream != phase["id"]:
                    dependencies.add((phase["id"], upstream))

    upstream_by_phase = {phase["id"]: set() for phase in phases}
    downstream_by_phase = {phase["id"]: set() for phase in phases}
    for phase_id, depends_on in dependencies:
        upstream_by_phase[phase_id].add(depends_on)
        downstream_by_phase[depends_on].add(phase_id)

    projected = []
    for order, phase in enumerate(phases):
        phase_items = phase.get("items", [])
        files = [file for item in phase_items for file in flatten_changes(item)]
        modules = {file.get("moduleId") for file in files if file.get("moduleId")}
        if any(item.get("noFileImpact") is True for item in phase_items):
            modules.add("_cross-cutting")
        internal_dependencies, incoming_dependencies, outgoing_dependencies = [], [], []
        for item in phase_items:
            for dependency in item.get("dependsOn", []):
                edge = {"itemId": item["id"], "dependsOn": dependency}
                dependency_phase = item_phase.get(dependency)
                if dependency_phase == phase["id"]:
                    internal_dependencies.append(edge)
                else:
                    incoming_dependencies.append({**edge, "fromPhaseId": dependency_phase})
            for consumer in items.values():
                if item["id"] not in consumer.get("dependsOn", []):
                    continue
                consumer_phase = item_phase.get(consumer["id"])
                if consumer_phase != phase["id"]:
                    outgoing_dependencies.append({
                        "itemId": item["id"], "consumerId": consumer["id"], "toPhaseId": consumer_phase,
                    })
        projected.append({
            "id": phase["id"], "title": phase.get("title"), "order": order,
            "itemIds": [item["id"] for item in phase_items],
            "completedItems": sum(item.get("status") == "done" for item in phase_items),
            "totalItems": len(phase_items), "moduleIds": sorted(modules), "fileCount": len(files),
            "dependsOn": sorted(upstream_by_phase[phase["id"]]),
            "affects": sorted(downstream_by_phase[phase["id"]]),
            "taskGraph": {
                "nodes": [
                    {"itemId": item["id"], "title": item.get("title"), "order": item_order,
                     "status": item.get("status")}
                    for item_order, item in enumerate(phase_items)
                ],
                "dependencies": sorted(internal_dependencies, key=lambda edge: (edge["itemId"], edge["dependsOn"])),
                "incomingDependencies": sorted(
                    incoming_dependencies,
                    key=lambda edge: (edge["itemId"], edge["dependsOn"]),
                ),
                "outgoingDependencies": sorted(
                    outgoing_dependencies,
                    key=lambda edge: (edge["itemId"], edge["consumerId"]),
                ),
            },
        })
    return {
        "phases": projected,
        "dependencies": [
            {"phaseId": phase_id, "dependsOn": depends_on}
            for phase_id, depends_on in sorted(dependencies)
        ],
    }


def dependencies_done(plan: dict, item: dict) -> bool:
    items = item_map(plan)
    return all(items.get(dep, {}).get("status") == "done" for dep in item.get("dependsOn", []))


def item_readiness(item: dict, items: dict[str, dict]) -> tuple[str, list[str]]:
    if item["status"] != "not-started":
        return item["status"], []
    blockers = [dep for dep in item.get("dependsOn", []) if items.get(dep, {}).get("status") != "done"]
    return ("blocked", blockers) if blockers else ("ready", [])


def next_action(entry: dict, plan: dict, project_map: dict | None = None) -> dict:
    if entry["state"] in TERMINAL_STATES:
        return {"type": "terminal", "message": f"Plan is {entry['state']} and frozen"}
    if entry["state"] == "draft":
        if not plan.get("phases") or not all_items(plan):
            return {"type": "plan-empty", "message": "Complete the draft before review or activation"}
        if plan.get("reviewPolicy") == "single" and (project_map is None or not matching_plan_review(plan, project_map)
                                                       or matching_plan_review(plan, project_map).get("result") != "passed"):
            return {"type": "review-plan", "message": "Request one independent review for the current plan/map revision"}
        return {"type": "activate-plan", "message": "Ask the user to authorize activation"}
    if entry["state"] == "paused":
        return {"type": "resume-required", "message": "Plan is paused; ask the user before resuming"}
    pending = next((a for a in plan.get("amendments", []) if a.get("status") == "pending-review"), None)
    if pending:
        return {"type": "amendment-gate", "id": pending["id"], "message": "Review or apply the pending amendment"}
    running = next((i for i in all_items(plan) if i["status"] == "in-progress"), None)
    if running:
        return {"type": "continue-item", "id": running["id"], "message": running["title"]}
    stopped = next((i for i in all_items(plan) if i["status"] in {"failed", "blocked"}), None)
    if stopped:
        return {"type": "address-item", "id": stopped["id"], "message": stopped.get("reason") or stopped["title"]}
    items = item_map(plan)
    ready = next((i for i in all_items(plan) if item_readiness(i, items)[0] == "ready"), None)
    if ready:
        return {"type": "start-item", "id": ready["id"], "message": ready["title"]}
    if all_items(plan) and all(i["status"] == "done" for i in all_items(plan)):
        return {"type": "completion-check", "message": "Run completion checks"}
    return {"type": "plan-empty", "message": "Add executable items before activation"}


def handoff_projection(root: Path, entry: dict, plan: dict, project_map: dict) -> dict:
    checkpoint = plan.get("checkpoint") or {}
    current_head = git_head(root) if entry.get("baselineCommit") else None
    current_branch = git_branch(root) if entry.get("baselineCommit") else None
    warnings = []
    if checkpoint.get("branch") and current_branch != checkpoint["branch"]:
        warnings.append(f"branch changed: {checkpoint['branch']} -> {current_branch}")
    if checkpoint.get("headCommit") and current_head and checkpoint["headCommit"] != current_head:
        # headCommit is recorded before the checkpoint's own JSON is committed, so the
        # expected next state is HEAD landing on a descendant (the checkpoint+code commit).
        # Only a non-ancestor relationship (reset, rebase, force-push, stale checkout)
        # signals a real problem.
        if not git_is_ancestor(root, checkpoint["headCommit"], current_head):
            warnings.append("HEAD has diverged from the checkpoint commit (not a descendant of it); inspect commits before continuing")
    dirty_paths = handoff_dirty_paths(root) if entry.get("baselineCommit") else []
    push = git_push_state(root) if entry.get("baselineCommit") else {"status": "unknown"}
    if push.get("status") == "no-upstream":
        warnings.append("branch has no upstream; another computer may not be able to fetch this checkpoint")
    elif push.get("status") == "unpushed":
        warnings.append(f"branch has {push.get('ahead')} unpushed commit(s)")
    if (push.get("behind") or 0) > 0:
        warnings.append(f"branch is {push.get('behind')} commit(s) behind its upstream")
    portable = "portable" if entry.get("baselineCommit") and not dirty_paths and push.get("status") == "pushed" else \
        "local-only" if entry.get("baselineCommit") else "unknown"
    return {
        **checkpoint, "currentBranch": current_branch, "currentHead": current_head,
        "currentPlanRevision": plan.get("revision"), "currentProjectMapRevision": project_map.get("revision"),
        "portability": portable, "currentDirtyPaths": dirty_paths, "push": push, "warnings": warnings,
        "nextAction": next_action(entry, plan, project_map),
    }


def status_projection(entry: dict, plan: dict, root: Path, project_map: dict) -> dict:
    # Terminal transitions call this exactly once to freeze the final observed tree.
    # Later reads use status.json and never recompute it.
    changes = git_change_map(root, entry.get("baselineCommit")) if entry.get("baselineCommit") else {}
    coverage = compute_change_coverage(plan, changes)
    items = item_map(plan)
    phases = []
    for phase in plan.get("phases", []):
        projected_items = []
        for item in phase.get("items", []):
            readiness, blockers = item_readiness(item, items)
            projected_items.append({**item, "readiness": readiness, "blockedBy": blockers,
                                    "observations": coverage["items"].get(item["id"], [])})
        phases.append({**phase, "items": projected_items})
    done = sum(item["status"] == "done" for item in items.values())
    open_issues = [issue for issue in plan.get("issues", []) if issue.get("status") == "open"]
    derived = []
    for item in all_items(plan):
        if item["status"] == "done":
            for obs in coverage["items"].get(item["id"], []):
                if obs["observedState"] != "change-observed":
                    derived.append({"type": "planned-file-mismatch", "severity": "critical", "itemId": item["id"], "observation": obs})
            attempts = item.get("executionAttempts") or ([item["execution"]] if item.get("execution") else [])
            attempt_observations = [observed for attempt in attempts for observed in attempt.get("observedFiles", [])]
            for planned in flatten_changes(item):
                matches = [observed for observed in attempt_observations if observed.get("path") == planned["path"]]
                if not any(observed.get("observedAction") == planned.get("action") for observed in matches):
                    derived.append({"type": "item-attribution-mismatch", "severity": "critical", "itemId": item["id"],
                                    "observation": matches[-1] if matches else {"path": planned["path"], "plannedAction": planned["action"], "observedAction": None}})
    map_view = project_map_projection(plan, project_map)
    action = next_action(entry, plan, project_map)
    return {
        "schemaVersion": SCHEMA_VERSION, "generatedAt": now(),
        "plan": {"slug": entry["slug"], "name": entry["name"], "goal": plan["goal"], "state": entry["state"],
                 "revision": plan.get("revision"), "reviewPolicy": plan.get("reviewPolicy"), "baselineCommit": entry.get("baselineCommit")},
        "summary": {"completedItems": done, "totalItems": len(items), "openIssues": len(open_issues) + len(derived),
                    "changedModules": len(map_view["directModules"]), "affectedModules": len(map_view["affectedModules"])},
        "handoff": handoff_projection(root, entry, plan, project_map), "phases": phases,
        "phaseGraph": phase_graph_projection(plan),
        "changeCoverage": coverage, "documentationImpact": compute_documentation_impact(plan, changes, bool(entry.get("baselineCommit"))),
        "projectMap": map_view, "reviews": plan.get("reviews", []), "amendments": plan.get("amendments", []),
        "issues": plan.get("issues", []), "derivedIssues": derived, "nextActions": [action],
    }


def render_status(root: Path, entry: dict, plan: dict, project_map: dict) -> dict:
    status = status_projection(entry, plan, root, project_map)
    atomic_json(status_path(root, entry["slug"]), status)
    return status


def save_plan(root: Path, index: dict, entry: dict, plan: dict, project_map: dict | None = None) -> dict:
    timestamp = now()
    plan["updatedAt"] = timestamp
    entry["updatedAt"] = timestamp
    atomic_json(plan_path(root, entry["slug"]), plan)
    if project_map is not None:
        atomic_json(map_path(root), project_map)
    save_index(root, index)
    return render_status(root, entry, plan, project_map or load_project_map(root))
