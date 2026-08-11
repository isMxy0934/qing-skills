"""Store asset installation, draft commands, and project-map upserts."""

from __future__ import annotations

from . import storage as st
from .storage import *
from .git import *
from .domain import *
from .projection import *

STORE_GITIGNORE = ".planctl.lock\n"


def bundled_dashboard() -> Path:
    # This runtime only ever executes from the skill itself — it is never copied into a
    # repository — so the bundled viewer is at a fixed path relative to this package:
    # <skill>/scripts/qing_plan/commands.py -> <skill>/assets/dashboard.html.
    dashboard = Path(__file__).resolve().parent.parent.parent / "assets" / "dashboard.html"
    if not dashboard.exists():
        die(f"cannot locate the skill's bundled dashboard at {dashboard}")
    return dashboard


def install_store_assets(target_root: Path, *, overwrite: bool) -> list[str]:
    """Install the read-only viewer beside the data.

    A repository receives plan JSON plus `dashboard.html`, never the runtime: keeping one
    copy of the code in the skill removes the whole class of installed-copy version drift.
    """
    target_root.mkdir(parents=True, exist_ok=True)
    installed = []
    dashboard = target_root / "dashboard.html"
    if overwrite or not dashboard.exists():
        shutil.copyfile(bundled_dashboard(), dashboard)
        dashboard.chmod(0o644)
    installed.append(str(dashboard))
    gitignore = target_root / ".gitignore"
    if overwrite or not gitignore.exists():
        gitignore.write_text(STORE_GITIGNORE, encoding="utf-8")
    installed.append(str(gitignore))
    return installed


def install_assets(root: Path, *, overwrite: bool) -> list[str]:
    return install_store_assets(store_dir(root), overwrite=overwrite)


def new_checkpoint() -> dict:
    return {
        "itemId": None, "lastCompletedItemId": None, "planRevision": 1, "projectMapRevision": 0,
        "branch": None, "headCommit": None, "stopReason": None, "nextAction": None,
        "createdBy": None, "createdAt": None, "handoff": {"readiness": "unknown", "dirtyPaths": []},
    }


def new_item(item_id: str, title: str, purpose: str, depends_on: list[str], verify_kind: str,
             files: list[dict], module_id: str, reason: str, no_file_impact: bool) -> dict:
    return {
        "id": item_id, "title": title, "purpose": purpose, "dependsOn": depends_on,
        "status": "not-started", "verifyKind": verify_kind, "reason": None,
        "noFileImpact": no_file_impact,
        "changeSets": [] if no_file_impact else [{"moduleId": module_id, "reason": reason, "files": files}],
        "verificationAttempts": [], "executionAttempts": [], "execution": None,
        "completedBy": None, "updatedAt": now(),
    }


def cmd_create(args: argparse.Namespace, root: Path) -> dict:
    require_agent(args, "create")
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{2,63}", args.slug):
        die("slug must be 3-64 lowercase letters, digits, or hyphens")
    require_git_root(root)
    index = load_index(root, allow_missing=True)
    if any(entry.get("slug") == args.slug for entry in index["plans"]):
        die(f"plan already exists: {args.slug}")
    if args.doc_mode == "required" and not args.doc_target:
        die("required documentation impact needs --doc-target")
    if args.doc_mode == "none" and not args.doc_reason:
        die("doc-mode=none needs --doc-reason")
    if not map_path(root).exists():
        atomic_json(map_path(root), empty_project_map())
    project_map = load_project_map(root)
    timestamp = now()
    doc_impact = None
    if args.doc_mode:
        doc_impact = {"mode": args.doc_mode, "coverage": args.doc_coverage, "reason": args.doc_reason,
                      "targets": [parse_doc_target(v) for v in args.doc_target or []]}
    plan = {
        "schemaVersion": SCHEMA_VERSION, "slug": args.slug, "goal": args.goal, "owner": args.owner,
        "planner": args.actor, "reviewPolicy": args.review_policy, "revision": 1,
        "createdAt": timestamp, "updatedAt": timestamp, "currentPhaseId": None,
        "documentationImpact": doc_impact, "phases": [], "reviews": [], "amendments": [],
        "checkpoint": new_checkpoint(), "issues": [],
    }
    entry = {
        "slug": args.slug, "name": args.name, "state": "draft", "path": f"{args.slug}/plan.json",
        "createdAt": timestamp, "updatedAt": timestamp, "activatedAt": None,
        "baselineCommit": None, "replacedBy": None,
    }
    index["plans"].append(entry)
    atomic_json(plan_path(root, args.slug), plan)
    event(root, args.slug, "plan-created", args.actor, args.actor_type,
          {"goal": args.goal, "reviewPolicy": args.review_policy})
    save_index(root, index)
    install_assets(root, overwrite=False)
    return render_status(root, entry, plan, project_map)


def cmd_set_documentation_impact(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    ensure_draft_editor(entry, plan, args, "set-documentation-impact")
    if args.mode == "required" and not args.target:
        die("required documentation impact needs --target")
    if args.mode == "none" and not args.reason:
        die("mode=none needs --reason")
    before = plan.get("documentationImpact")
    plan["documentationImpact"] = {"mode": args.mode, "coverage": args.coverage, "reason": args.reason,
                                   "targets": [parse_doc_target(v) for v in args.target or []]}
    bump_plan_revision(plan)
    event(root, entry["slug"], "documentation-impact-changed", args.actor, args.actor_type,
          {"before": before, "after": plan["documentationImpact"]})
    return save_plan(root, index, entry, plan)


def cmd_add_phase(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    ensure_draft_editor(entry, plan, args, "add-phase")
    if any(phase.get("id") == args.id for phase in plan["phases"]):
        die(f"duplicate phase id: {args.id}")
    phase = {"id": args.id, "title": args.title, "purpose": args.purpose, "items": []}
    plan["phases"].append(phase)
    bump_plan_revision(plan)
    event(root, entry["slug"], "phase-added", args.actor, args.actor_type, {"after": phase})
    return save_plan(root, index, entry, plan)


def cmd_add_item(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    ensure_draft_editor(entry, plan, args, "add-item")
    phase = find_phase(plan, args.phase)
    if args.id in item_map(plan):
        die(f"duplicate item id: {args.id}")
    files = [parse_file_arg(value) for value in args.file or []]
    if bool(files) == bool(args.no_file_impact):
        die("declare --file or --no-file-impact, exclusively")
    if files and (not args.module or not args.change_reason):
        die("file changes require --module and --change-reason")
    project_map = load_project_map(root)
    module_id = args.module or "_cross-cutting"
    if module_id not in {m["id"] for m in project_map["modules"]}:
        die(f"unknown module: {module_id}")
    item = new_item(args.id, args.title, args.purpose,
                    [value.strip() for value in args.depends_on.split(",") if value.strip()], args.verify_kind,
                    files, module_id, args.change_reason or args.purpose, args.no_file_impact)
    phase["items"].append(item)
    bump_plan_revision(plan)
    errors = validate_plan(entry, plan, project_map)
    if errors:
        die("; ".join(errors))
    event(root, entry["slug"], "item-added", args.actor, args.actor_type, {"phaseId": args.phase, "after": item})
    return save_plan(root, index, entry, plan, project_map)


def cmd_review_plan(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    require_state(entry, {"draft"}, "review-plan")
    require_agent(args, "review-plan")
    if plan.get("reviewPolicy") == "none":
        die("review-plan is unnecessary when reviewPolicy=none")
    if args.actor == plan.get("planner"):
        die("planner cannot review their own plan")
    if args.result == "fail" and not args.reason:
        die("failed review requires --reason")
    project_map = load_project_map(root)
    review = {
        "id": f"review-{uuid.uuid4().hex[:8]}", "targetType": "plan", "targetId": plan["slug"],
        "targetRevision": plan["revision"], "projectMapRevision": project_map["revision"],
        "reviewer": args.actor, "result": "passed" if args.result == "pass" else "failed",
        "evidence": args.evidence, "reason": args.reason, "reviewedAt": now(),
    }
    plan["reviews"].append(review)
    event(root, entry["slug"], "plan-reviewed", args.actor, args.actor_type, review)
    return save_plan(root, index, entry, plan, project_map)


def upsert_module(project_map: dict, plan_slug: str, module: dict) -> dict:
    module_id = module.get("id")
    if not module_id or module_id.startswith("_"):
        die("custom module id is required and cannot start with _")
    if (not module.get("name") or not module.get("description") or not isinstance(module.get("pathPatterns"), list)
            or not module.get("reason") or not module.get("evidence")):
        die("module requires name, description, pathPatterns, reason, and evidence")
    existing = next((m for m in project_map["modules"] if m["id"] == module_id), None)
    value = {"id": module_id, "name": module["name"], "description": module["description"],
             "pathPatterns": module["pathPatterns"], "reason": module["reason"], "evidence": module["evidence"],
             "introducedByPlan": plan_slug,
             "updatedByPlan": plan_slug}
    if existing:
        value["introducedByPlan"] = existing.get("introducedByPlan") or plan_slug
        existing.update(value)
    else:
        project_map["modules"].append(value)
    return value


def upsert_dependency(project_map: dict, plan_slug: str, module_id: str, depends_on: str, reason: str, evidence: str) -> dict:
    known = {m["id"] for m in project_map["modules"]}
    if module_id not in known or depends_on not in known or module_id == depends_on:
        die("dependency endpoints must be distinct known modules")
    existing = next((d for d in project_map["dependencies"] if d["moduleId"] == module_id and d["dependsOn"] == depends_on), None)
    value = {"moduleId": module_id, "dependsOn": depends_on, "reason": reason, "evidence": evidence, "updatedByPlan": plan_slug}
    if existing:
        existing.update(value)
    else:
        project_map["dependencies"].append(value)
    return value


def cmd_upsert_module(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    ensure_draft_editor(entry, plan, args, "upsert-module")
    if index.get("currentPlanSlug") and index.get("currentPlanSlug") != entry["slug"]:
        die("the current plan owns project-map changes; amend it or wait until it is terminal")
    project_map = load_project_map(root)
    before = next((m.copy() for m in project_map["modules"] if m["id"] == args.id), None)
    after = upsert_module(project_map, entry["slug"], {"id": args.id, "name": args.name, "description": args.description,
                                                            "pathPatterns": args.path_pattern or [], "reason": args.reason,
                                                            "evidence": args.evidence})
    project_map["revision"] += 1
    project_map["updatedAt"] = now()
    bump_plan_revision(plan)
    event(root, entry["slug"], "project-module-upserted", args.actor, args.actor_type, {"before": before, "after": after})
    return save_plan(root, index, entry, plan, project_map)


def cmd_upsert_dependency(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    ensure_draft_editor(entry, plan, args, "upsert-dependency")
    if index.get("currentPlanSlug") and index.get("currentPlanSlug") != entry["slug"]:
        die("the current plan owns project-map changes; amend it or wait until it is terminal")
    project_map = load_project_map(root)
    before = next((d.copy() for d in project_map["dependencies"] if d["moduleId"] == args.module and d["dependsOn"] == args.depends_on), None)
    preview_map = copy.deepcopy(project_map)
    upsert_dependency(preview_map, entry["slug"], args.module, args.depends_on, args.reason, args.evidence)
    cycle_node = module_dependency_cycle(preview_map)
    if cycle_node:
        die(f"dependency would create a cycle at module {cycle_node}")
    after = upsert_dependency(project_map, entry["slug"], args.module, args.depends_on, args.reason, args.evidence)
    project_map["revision"] += 1
    project_map["updatedAt"] = now()
    bump_plan_revision(plan)
    event(root, entry["slug"], "project-dependency-upserted", args.actor, args.actor_type, {"before": before, "after": after})
    return save_plan(root, index, entry, plan, project_map)

