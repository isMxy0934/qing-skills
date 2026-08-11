"""Plan domain helpers and schema validation."""

from __future__ import annotations

from .storage import *
from .git import *


def all_items(plan: dict) -> list[dict]:
    return [item for phase in plan.get("phases", []) for item in phase.get("items", [])]


def item_map(plan: dict) -> dict[str, dict]:
    return {item["id"]: item for item in all_items(plan)}


def find_phase(plan: dict, phase_id: str) -> dict:
    phase = next((phase for phase in plan.get("phases", []) if phase.get("id") == phase_id), None)
    if phase is None:
        die(f"unknown phase: {phase_id}")
    return phase


def find_item(plan: dict, item_id: str) -> tuple[dict, dict]:
    for phase in plan.get("phases", []):
        for item in phase.get("items", []):
            if item.get("id") == item_id:
                return phase, item
    die(f"unknown item: {item_id}")


def require_state(entry: dict, states: set[str], action: str) -> None:
    if entry.get("state") not in states:
        die(f"{action} requires state in {sorted(states)}, found {entry.get('state')}")


def require_human(args: argparse.Namespace, action: str) -> None:
    if args.actor_type != "human":
        die(f"{action} requires --actor-type human")


def require_agent(args: argparse.Namespace, action: str) -> None:
    if args.actor_type != "agent" or not (args.actor or "").strip():
        die(f"{action} requires --actor-type agent and a named --actor")


def flatten_changes(item: dict) -> list[dict]:
    files = []
    for change_set in item.get("changeSets", []):
        for file in change_set.get("files", []):
            files.append({**file, "moduleId": change_set.get("moduleId"), "reason": change_set.get("reason")})
    return files


def parse_file_arg(value: str) -> dict:
    parts = value.split(":", 2)
    if len(parts) < 2 or parts[1] not in FILE_ACTIONS:
        die("--file must be path:create|modify|delete or path:move:from-path")
    path, action = parts[:2]
    source = parts[2] if len(parts) == 3 else None
    if not path or (action == "move" and not source) or (action != "move" and source):
        die(f"invalid file declaration: {value}")
    return {"path": path, "action": action, "from": source}


def parse_doc_target(value: str) -> dict:
    if ":" not in value:
        die("documentation target must be pattern:purpose")
    pattern, purpose = value.split(":", 1)
    if not pattern or not purpose:
        die("documentation target needs pattern and purpose")
    return {"pattern": pattern, "purpose": purpose}


def matching_plan_review(plan: dict, project_map: dict) -> dict | None:
    matches = [r for r in plan.get("reviews", []) if r.get("targetType") == "plan" and
               r.get("targetRevision") == plan.get("revision") and r.get("projectMapRevision") == project_map.get("revision")]
    return matches[-1] if matches else None


def bump_plan_revision(plan: dict) -> None:
    plan["revision"] = int(plan.get("revision", 0)) + 1


def ensure_draft_editor(entry: dict, plan: dict, args: argparse.Namespace, action: str) -> None:
    require_state(entry, {"draft"}, action)
    require_agent(args, action)
    if args.actor != plan.get("planner"):
        die(f"only planner {plan.get('planner')} may edit the draft")


def module_dependency_cycle(project_map: dict) -> str | None:
    """Return the id of a module on a dependency cycle, or None if the graph is acyclic."""
    known = {module.get("id") for module in project_map.get("modules", [])}
    graph = {module_id: [] for module_id in known}
    for dep in project_map.get("dependencies", []):
        module_id, depends_on = dep.get("moduleId"), dep.get("dependsOn")
        if module_id in graph and depends_on in known:
            graph[module_id].append(depends_on)
    visiting, visited = set(), set()

    def visit(node: str) -> str | None:
        if node in visiting:
            return node
        if node in visited:
            return None
        visiting.add(node)
        for dependency in graph.get(node, []):
            found = visit(dependency)
            if found:
                return found
        visiting.remove(node)
        visited.add(node)
        return None

    for node in graph:
        found = visit(node)
        if found:
            return found
    return None


def validate_project_map(project_map: dict) -> list[str]:
    errors = []
    if project_map.get("schemaVersion") != SCHEMA_VERSION:
        errors.append("project-map: unsupported schemaVersion")
    ids = [module.get("id") for module in project_map.get("modules", [])]
    if len(ids) != len(set(ids)):
        errors.append("project-map: duplicate module id")
    for required in SYSTEM_MODULES:
        if required not in ids:
            errors.append(f"project-map: missing system module {required}")
    for module in project_map.get("modules", []):
        if not module.get("name") or not module.get("description") or not isinstance(module.get("pathPatterns"), list):
            errors.append(f"project-map: invalid module {module.get('id')}")
        if not module.get("reason") or not module.get("evidence"):
            errors.append(f"project-map: module {module.get('id')} needs reason and evidence")
    known = set(ids)
    seen = set()
    for dep in project_map.get("dependencies", []):
        key = (dep.get("moduleId"), dep.get("dependsOn"))
        if not key[0] or not key[1] or key[0] not in known or key[1] not in known or key[0] == key[1]:
            errors.append(f"project-map: invalid dependency {key}")
        if key in seen:
            errors.append(f"project-map: duplicate dependency {key}")
        seen.add(key)
    cycle_node = module_dependency_cycle(project_map)
    if cycle_node:
        errors.append(f"project-map: dependency cycle at {cycle_node}")
    return errors


def validate_plan(entry: dict, plan: dict, project_map: dict) -> list[str]:
    slug, errors = entry.get("slug", "<unknown>"), []
    for key in ("schemaVersion", "slug", "revision", "goal", "planner", "reviewPolicy", "phases", "reviews", "amendments", "checkpoint", "issues"):
        if key not in plan:
            errors.append(f"{slug}: missing {key}")
    if plan.get("schemaVersion") != SCHEMA_VERSION or plan.get("slug") != slug:
        errors.append(f"{slug}: invalid schemaVersion or slug")
    if plan.get("reviewPolicy") not in REVIEW_POLICIES:
        errors.append(f"{slug}: invalid reviewPolicy")
    phase_ids = [phase.get("id") for phase in plan.get("phases", [])]
    if len(phase_ids) != len(set(phase_ids)):
        errors.append(f"{slug}: duplicate phase id")
    items, module_ids = all_items(plan), {m["id"] for m in project_map.get("modules", [])}
    item_ids = [item.get("id") for item in items]
    if len(item_ids) != len(set(item_ids)):
        errors.append(f"{slug}: duplicate item id")
    known = set(item_ids)
    graph = {}
    for item in items:
        item_id = item.get("id")
        graph[item_id] = item.get("dependsOn", [])
        if item.get("status") not in ITEM_STATES or item.get("verifyKind") not in VERIFY_KINDS:
            errors.append(f"{slug}/{item_id}: invalid status or verifyKind")
        change_sets = item.get("changeSets", [])
        if bool(change_sets) == (item.get("noFileImpact") is True):
            errors.append(f"{slug}/{item_id}: declare changeSets or noFileImpact=true exclusively")
        item_paths = [file.get("path") for change_set in change_sets for file in change_set.get("files", [])]
        if len(item_paths) != len(set(item_paths)):
            errors.append(f"{slug}/{item_id}: duplicate file path across changeSets")
        for change_set in change_sets:
            if change_set.get("moduleId") not in module_ids or not change_set.get("reason") or not change_set.get("files"):
                errors.append(f"{slug}/{item_id}: invalid changeSet")
            for file in change_set.get("files", []):
                if file.get("action") not in FILE_ACTIONS or not file.get("path"):
                    errors.append(f"{slug}/{item_id}: invalid file declaration")
                if (file.get("action") == "move") != bool(file.get("from")):
                    errors.append(f"{slug}/{item_id}: invalid move source")
        if item.get("status") == "done" and not item.get("verificationAttempts"):
            errors.append(f"{slug}/{item_id}: done without verification history")
        if item.get("status") == "done" and not (item.get("execution") or {}).get("legacy"):
            execution = item.get("execution") or {}
            if not execution.get("startHead") or not execution.get("endHead") or not execution.get("endedAt"):
                errors.append(f"{slug}/{item_id}: done without complete execution attribution")
        if item.get("status") in {"failed", "blocked"} and not item.get("reason"):
            errors.append(f"{slug}/{item_id}: stopped without reason")
        for attempt in item.get("verificationAttempts", []):
            if attempt.get("kind") != item.get("verifyKind") or attempt.get("source") != VERIFY_SOURCE_FOR_KIND.get(item.get("verifyKind")):
                errors.append(f"{slug}/{item_id}: verification attempt kind/source mismatch")
            if attempt.get("result") not in {"pass", "fail", "not-run"} or not attempt.get("evidence") or not attempt.get("timestamp"):
                errors.append(f"{slug}/{item_id}: invalid verification attempt")
        for dep in item.get("dependsOn", []):
            if dep not in known:
                errors.append(f"{slug}/{item_id}: unknown dependency {dep}")
    visiting, visited = set(), set()

    def visit(node: str) -> None:
        if node in visiting:
            errors.append(f"{slug}: dependency cycle at {node}")
            return
        if node in visited:
            return
        visiting.add(node)
        for dep in graph.get(node, []):
            visit(dep)
        visiting.remove(node)
        visited.add(node)
    for node in graph:
        visit(node)
    for amendment in plan.get("amendments", []):
        if amendment.get("kind") not in AMENDMENT_KINDS or amendment.get("status") not in {"pending-review", "applied", "rejected"}:
            errors.append(f"{slug}: invalid amendment {amendment.get('id')}")
        if amendment.get("kind") == "temporary" and not amendment.get("cleanupItemId"):
            errors.append(f"{slug}: temporary amendment needs cleanupItemId")
        if amendment.get("kind") == "temporary" and amendment.get("cleanupItemId") not in known:
            # A pending amendment may name a cleanup item its own operations will create
            # once reviewed; that item legitimately does not exist in the plan yet.
            self_created = any(op.get("op") == "add-item" and op.get("id") == amendment.get("cleanupItemId")
                                for op in amendment.get("operations", []))
            if amendment.get("status") == "applied" or not self_created:
                errors.append(f"{slug}: temporary amendment has unknown cleanup item")
        if amendment.get("status") == "applied" and (not amendment.get("before") or not amendment.get("after")):
            errors.append(f"{slug}: applied amendment lacks before/after revisions")
    documentation = plan.get("documentationImpact")
    if documentation:
        if documentation.get("mode") not in DOC_MODES:
            errors.append(f"{slug}: invalid documentation mode")
        if documentation.get("mode") == "none" and not documentation.get("reason"):
            errors.append(f"{slug}: documentation mode none needs a reason")
        if documentation.get("mode") == "required":
            if documentation.get("coverage") not in DOC_COVERAGE or not documentation.get("targets"):
                errors.append(f"{slug}: required documentation needs coverage and targets")
            for target in documentation.get("targets", []):
                if not target.get("pattern") or not target.get("purpose"):
                    errors.append(f"{slug}: invalid documentation target")
    amendments = {amendment.get("id"): amendment for amendment in plan.get("amendments", [])}
    for review in plan.get("reviews", []):
        if review.get("targetType") not in {"plan", "amendment"} or review.get("result") not in {"passed", "failed"}:
            errors.append(f"{slug}: invalid review {review.get('id')}")
        if not review.get("reviewer") or not review.get("evidence") or not review.get("reviewedAt"):
            errors.append(f"{slug}: review lacks reviewer/evidence/time")
        if review.get("result") == "failed" and not review.get("reason"):
            errors.append(f"{slug}: failed review lacks reason")
        if not isinstance(review.get("targetRevision"), int) or not isinstance(review.get("projectMapRevision"), int):
            errors.append(f"{slug}: review lacks immutable revision binding")
        if review.get("targetType") == "plan" and review.get("reviewer") == plan.get("planner"):
            errors.append(f"{slug}: planner reviewed their own plan")
        target_amendment = amendments.get(review.get("targetId"))
        if review.get("targetType") == "amendment" and target_amendment and review.get("reviewer") == target_amendment.get("proposedBy"):
            errors.append(f"{slug}: amendment proposer reviewed their own amendment")
    return errors


def validate_migration_manifest(root: Path) -> list[str]:
    legacy = root / "plans"
    manifest_path = store_dir(root) / "migration.json"
    if not (legacy / "index.json").exists() and not manifest_path.exists():
        return []
    if not manifest_path.exists():
        return ["migration: both stores exist without migration.json"]
    manifest = read_json(manifest_path)
    if manifest.get("state") != "verified" or manifest.get("safeToDeleteLegacy") is not True:
        return ["migration: manifest is not verified"]
    if not (legacy / "index.json").exists():
        return []
    errors = []
    expected = {entry["path"]: entry["sha256"] for entry in manifest.get("sourceFiles", [])}
    actual_paths = sorted(path for path in legacy.rglob("*") if path.is_file() and path.name != ".planctl.lock")
    actual_names = {str(path.relative_to(legacy)) for path in actual_paths}
    if actual_names != set(expected):
        errors.append("migration: legacy file inventory differs from verified source")
    for path in actual_paths:
        relative = str(path.relative_to(legacy))
        if relative in expected and sha256_file(path) != expected[relative]:
            errors.append(f"migration: legacy hash changed for {relative}")
    return errors


def validate_store(root: Path, index: dict) -> list[str]:
    project_map = load_project_map(root)
    errors = validate_project_map(project_map) + validate_migration_manifest(root)
    if index.get("schemaVersion") != SCHEMA_VERSION or not isinstance(index.get("plans"), list):
        errors.append("index: invalid schemaVersion or plans")
        return errors
    slugs = [entry.get("slug") for entry in index["plans"]]
    if len(slugs) != len(set(slugs)):
        errors.append("index: duplicate plan slug")
    current_entries = [entry for entry in index["plans"] if entry.get("state") in CURRENT_STATES]
    current = index.get("currentPlanSlug")
    if len(current_entries) > 1 or (current_entries and current_entries[0].get("slug") != current) or (not current_entries and current is not None):
        errors.append("index: currentPlanSlug does not identify exactly one active/paused plan")
    for entry in index["plans"]:
        slug = entry.get("slug")
        if entry.get("state") not in PLAN_STATES or entry.get("path") != f"{slug}/plan.json":
            errors.append(f"{slug}: invalid registry entry")
        if entry.get("state") in CURRENT_STATES | {"completed"} and not entry.get("baselineCommit"):
            errors.append(f"{slug}: state requires baselineCommit")
        if not plan_path(root, slug).exists():
            errors.append(f"{slug}: missing plan.json")
            continue
        errors.extend(validate_plan(entry, read_json(plan_path(root, slug)), project_map))
        if entry.get("state") in TERMINAL_STATES:
            if not status_path(root, slug).exists():
                errors.append(f"{slug}: terminal plan missing frozen status")
            else:
                frozen = read_json(status_path(root, slug))
                if frozen.get("schemaVersion") != SCHEMA_VERSION or frozen.get("plan", {}).get("state") != entry.get("state"):
                    errors.append(f"{slug}: invalid frozen status")
        for event_path in sorted((store_dir(root) / slug / "events").glob("*.json")):
            stored_event = read_json(event_path)
            if stored_event.get("schemaVersion") != SCHEMA_VERSION or stored_event.get("planSlug") != slug:
                errors.append(f"{slug}: invalid event {event_path.name}")
    registered = set(slugs)
    for path in store_dir(root).glob("*/plan.json") if store_dir(root).exists() else []:
        if path.parent.name not in registered:
            errors.append(f"unregistered plan directory: {path.parent.name}")
    return errors


def validate_legacy_store(root: Path) -> list[str]:
    index = load_index(root)
    errors = []
    if index.get("schemaVersion") != LEGACY_SCHEMA_VERSION or not isinstance(index.get("plans"), list):
        return ["legacy index is invalid"]
    slugs = [entry.get("slug") for entry in index["plans"]]
    if len(slugs) != len(set(slugs)):
        errors.append("legacy index has duplicate slugs")
    for entry in index["plans"]:
        path = plan_path(root, entry.get("slug"))
        if not path.exists():
            errors.append(f"{entry.get('slug')}: missing legacy plan.json")
        elif read_json(path).get("schemaVersion") != LEGACY_SCHEMA_VERSION:
            errors.append(f"{entry.get('slug')}: unsupported legacy schema")
        if entry.get("state") in TERMINAL_STATES and not status_path(root, entry.get("slug")).exists():
            errors.append(f"{entry.get('slug')}: terminal plan missing status")
    return errors
