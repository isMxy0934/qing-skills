"""Validated, non-destructive migration from V1 plans/ to qing-plans/."""

from __future__ import annotations

from . import storage as st
from .storage import *
from .git import *
from .domain import *
from .projection import *
from .commands import install_store_assets


def convert_legacy_plan(old: dict, entry: dict) -> dict:
    review = old.get("planReview") or {}
    reviews = []
    if review.get("status") in {"passed", "failed"}:
        reviews.append({
            "id": f"legacy-plan-review-{uuid.uuid4().hex[:8]}", "targetType": "plan", "targetId": old.get("slug"),
            "targetRevision": 1, "projectMapRevision": 0, "reviewer": review.get("reviewer", "legacy-reviewer"),
            "result": review["status"], "evidence": review.get("evidence") or "migrated V1 review",
            "reason": review.get("reason"), "reviewedAt": review.get("reviewedAt") or old.get("updatedAt"), "legacy": True,
        })
    phases = []
    for old_phase in old.get("phases", []):
        items = []
        for old_item in old_phase.get("items", []):
            files = old_item.get("plannedFiles", [])
            attempts = []
            if old_item.get("evidence"):
                verify_kind = old_item.get("verifyKind", "manual")
                legacy_source = old_item.get("verifiedBy")
                attempts.append({
                    "id": f"legacy-verify-{uuid.uuid4().hex[:8]}", "kind": verify_kind,
                    "source": VERIFY_SOURCE_FOR_KIND.get(verify_kind, "human"), "legacySource": legacy_source,
                    "result": "pass" if old_item.get("status") == "done" else "not-run",
                    "evidence": old_item.get("evidence"), "reason": old_item.get("reason"), "actor": old_item.get("completedBy"),
                    "headCommit": entry.get("baselineCommit"), "timestamp": old_item.get("updatedAt"), "legacy": True,
                })
            items.append({
                "id": old_item.get("id"), "title": old_item.get("title"), "purpose": old_item.get("purpose"),
                "dependsOn": old_item.get("dependsOn", []), "status": old_item.get("status", "not-started"),
                "verifyKind": old_item.get("verifyKind", "manual"), "reason": old_item.get("reason"),
                "noFileImpact": old_item.get("noFileImpact") is True,
                "changeSets": [] if not files else [{"moduleId": "_unmapped", "reason": old_item.get("purpose") or "migrated V1 declaration", "files": files}],
                "verificationAttempts": attempts,
                "executionAttempts": [{"legacy": True, "attribution": "unknown"}] if old_item.get("status") == "done" else [],
                "execution": {"legacy": True, "attribution": "unknown"} if old_item.get("status") == "done" else None,
                "completedBy": old_item.get("completedBy"), "updatedAt": old_item.get("updatedAt") or old.get("updatedAt"),
            })
        phases.append({"id": old_phase.get("id"), "title": old_phase.get("title"), "purpose": old_phase.get("purpose"),
                       "items": items, "legacyPhaseReview": old_phase.get("phaseReview")})
    checkpoint = old.get("checkpoint") or {}
    return {
        "schemaVersion": 2, "slug": old.get("slug"), "goal": old.get("goal"), "owner": old.get("owner"),
        "planner": old.get("planner") or "legacy-planner", "reviewPolicy": "single", "revision": 1,
        "createdAt": old.get("createdAt"), "updatedAt": old.get("updatedAt"), "currentPhaseId": old.get("currentPhaseId"),
        "documentationImpact": old.get("documentationImpact"), "phases": phases, "reviews": reviews, "amendments": [],
        "checkpoint": {
            "itemId": checkpoint.get("currentItemId"), "lastCompletedItemId": checkpoint.get("lastCompletedItemId"),
            "planRevision": 1, "projectMapRevision": 0, "branch": None, "headCommit": entry.get("baselineCommit"),
            "stopReason": checkpoint.get("stopReason"), "nextAction": None, "createdBy": "legacy-migration",
            "createdAt": checkpoint.get("updatedAt"), "handoff": {"readiness": "unknown", "dirtyPaths": [], "legacy": True},
        },
        "issues": old.get("issues", []), "legacy": {"schemaVersion": 1, "phaseReviewGatesEnabled": old.get("phaseReviewGatesEnabled")},
    }


def migrated_item_observations(item: dict) -> list[dict]:
    # V1 required every declared file to match its planned action exactly before an item
    # could be marked done, but only ever persisted that as a global count, never per file
    # or per item. Restating "matched" for each file of a done item is not a new claim —
    # it is the fact V1's own completion rule already established — placed into the shape
    # the dashboard's Planned/Observed/Verified table expects. A non-done item (relevant
    # for a migrated cancelled plan) gets no observations, so its files honestly read as
    # not yet observed rather than falsely claiming a match V1 never verified.
    if item.get("status") != "done":
        return []
    return [
        {"path": file["path"], "moduleId": file.get("moduleId"), "reason": file.get("reason"),
         "plannedAction": file["action"], "plannedFrom": file.get("from"),
         "observedAction": file["action"], "observedFrom": file.get("from"), "observedState": "change-observed"}
        for file in flatten_changes(item)
    ]


def migrated_frozen_status(entry: dict, plan: dict, old_status: dict | None, project_map: dict) -> dict:
    items = all_items(plan)
    map_view = project_map_projection(plan, project_map)
    phases = [
        {**phase, "items": [{**item, "observations": migrated_item_observations(item)} for item in phase.get("items", [])]}
        for phase in plan.get("phases", [])
    ]
    return {
        "schemaVersion": 2, "generatedAt": (old_status or {}).get("generatedAt") or plan.get("updatedAt"),
        "plan": {"slug": entry["slug"], "name": entry.get("name"), "goal": plan.get("goal"), "state": entry["state"],
                 "revision": 1, "reviewPolicy": "single", "baselineCommit": entry.get("baselineCommit")},
        "summary": {"completedItems": sum(i["status"] == "done" for i in items), "totalItems": len(items),
                    "openIssues": sum(i.get("status") == "open" for i in plan["issues"]),
                    "changedModules": len(map_view["directModules"]), "affectedModules": len(map_view["affectedModules"])},
        "handoff": {**plan["checkpoint"], "portability": "unknown", "warnings": ["Migrated terminal snapshot; V1 attribution is preserved as unknown"],
                    "nextAction": {"type": "terminal", "message": entry["state"]}},
        "phases": phases, "changeCoverage": (old_status or {}).get("changeCoverage", {}),
        "documentationImpact": (old_status or {}).get("documentationImpact", {}),
        "projectMap": map_view, "reviews": plan["reviews"], "amendments": [],
        "issues": plan["issues"], "derivedIssues": (old_status or {}).get("derivedIssues", []), "nextActions": [],
        "legacyStatus": old_status,
    }


def migration_inventory(old: Path) -> dict:
    files = sorted(path for path in old.rglob("*") if path.is_file() and path.name != ".planctl.lock")
    index = read_json(old / "index.json")
    return {
        "plans": len(index.get("plans", [])),
        "events": sum(1 for path in files if path.parent.name == "events" and path.suffix == ".json"),
        "files": [{"path": str(path.relative_to(old)), "sha256": sha256_file(path)} for path in files],
    }


def cmd_migrate_store(args: argparse.Namespace, root: Path) -> dict:
    old, new = root / "plans", root / "qing-plans"
    if not (old / "index.json").exists():
        die("migration requires legacy plans/index.json")
    if new.exists():
        die("qing-plans already exists; resolve it before migration")
    legacy_errors = validate_legacy_store(root)
    if legacy_errors:
        die("legacy validation failed: " + "; ".join(legacy_errors))
    inventory = migration_inventory(old)
    if args.dry_run:
        return {"dryRun": True, "source": "plans", "target": "qing-plans", **inventory,
                "nextAction": "run migrate-store with a clean Git working tree"}
    require_git_root(root)
    dirty = migration_dirty_paths(root)
    if dirty:
        die("migration requires a clean Git working tree (except plans/.planctl.lock): " + ", ".join(dirty))
    stage = Path(tempfile.mkdtemp(prefix=".qing-plans-migrate-", dir=root))
    old_override, old_flag = st._STORE_OVERRIDE, st._USING_LEGACY
    try:
        old_index = read_json(old / "index.json")
        new_index = {**old_index, "schemaVersion": 2, "revision": int(old_index.get("revision", 0)) + 1, "updatedAt": now()}
        atomic_json(stage / "index.json", new_index)
        project_map = empty_project_map()
        atomic_json(stage / "project-map.json", project_map)
        for entry in new_index["plans"]:
            slug = entry["slug"]
            converted = convert_legacy_plan(read_json(old / slug / "plan.json"), entry)
            atomic_json(stage / slug / "plan.json", converted)
            for source in sorted((old / slug / "events").glob("*.json")):
                data = read_json(source)
                data["legacySchemaVersion"] = data.get("schemaVersion")
                data["schemaVersion"] = 2
                atomic_json(stage / slug / "events" / source.name, data)
            old_status_path = old / slug / "status.json"
            if entry["state"] in TERMINAL_STATES:
                old_status = read_json(old_status_path) if old_status_path.exists() else None
                atomic_json(stage / slug / "status.json", migrated_frozen_status(entry, converted, old_status, project_map))
        install_store_assets(stage, overwrite=True)
        manifest = {
            "schemaVersion": 2, "source": "plans", "target": "qing-plans", "state": "verified",
            "verifiedAt": now(), "safeToDeleteLegacy": True, "planCount": inventory["plans"],
            "eventCount": inventory["events"], "sourceFiles": inventory["files"],
        }
        atomic_json(stage / "migration.json", manifest)
        st._STORE_OVERRIDE, st._USING_LEGACY = stage, False
        for entry in new_index["plans"]:
            if entry["state"] not in TERMINAL_STATES:
                render_status(root, entry, read_json(stage / entry["slug"] / "plan.json"), project_map)
        errors = validate_store(root, new_index)
        if errors:
            die("staged V2 validation failed: " + "; ".join(errors))
        os.replace(stage, new)
        st._STORE_OVERRIDE = new
        for entry in new_index["plans"]:
            if entry["state"] not in TERMINAL_STATES:
                render_status(root, entry, read_json(new / entry["slug"] / "plan.json"), project_map)
        return {"migrated": True, "verified": True, "sourcePreserved": "plans", "target": "qing-plans",
                "planCount": inventory["plans"], "eventCount": inventory["events"], "safeToDeleteLegacy": True,
                "message": "qing-plans is complete and verified. You may now delete plans/ and the legacy root plan-dashboard.html, then run validate again."}
    finally:
        if stage.exists():
            shutil.rmtree(stage)
        if not new.exists():
            st._STORE_OVERRIDE, st._USING_LEGACY = old_override, old_flag
