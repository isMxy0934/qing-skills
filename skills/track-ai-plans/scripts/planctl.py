#!/usr/bin/env python3
"""Deterministic state manager for the track-ai-plans skill."""

from __future__ import annotations

import argparse
import contextlib
import datetime as dt
import fnmatch
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
from pathlib import Path

try:
    import fcntl
except ImportError:  # pragma: no cover - The skill currently targets Codex's Unix runtimes.
    fcntl = None


SCHEMA_VERSION = 1
INDEX_SCHEMA_VERSION = SCHEMA_VERSION
PLAN_SCHEMA_VERSION = SCHEMA_VERSION
PLAN_STATES = {"draft", "active", "paused", "completed", "cancelled"}
CURRENT_STATES = {"active", "paused"}
TERMINAL_STATES = {"completed", "cancelled"}
ITEM_STATES = {"not-started", "in-progress", "done", "failed", "blocked"}
FILE_ACTIONS = {"create", "modify", "delete", "move"}
VERIFY_SOURCES = {"script", "llm", "human"}
VERIFY_KINDS = {"test", "llm-review", "manual"}
DOC_MODES = {"required", "none"}
DOC_COVERAGE = {"all", "any"}
MUTATING_COMMANDS = {
    "create",
    "set-documentation-impact",
    "add-phase",
    "add-item",
    "update-item",
    "verify",
    "checkpoint",
    "add-issue",
    "resolve-issue",
    "transition",
    "switch",
    "install-dashboard",
    "show",
    "changes",
}


class PlanError(Exception):
    pass


def now() -> str:
    return dt.datetime.now(dt.timezone.utc).isoformat().replace("+00:00", "Z")


def die(message: str) -> None:
    raise PlanError(message)


def read_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        die(f"missing file: {path}")
    except json.JSONDecodeError as exc:
        die(f"invalid JSON in {path}: {exc}")


def atomic_json(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, temp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
        os.replace(temp_name, path)
    finally:
        if os.path.exists(temp_name):
            os.unlink(temp_name)


def plans_dir(root: Path) -> Path:
    return root / "plans"


def index_path(root: Path) -> Path:
    return plans_dir(root) / "index.json"


def plan_path(root: Path, slug: str) -> Path:
    return plans_dir(root) / slug / "plan.json"


def status_path(root: Path, slug: str) -> Path:
    return plans_dir(root) / slug / "status.json"


def empty_index() -> dict:
    return {
        "schemaVersion": INDEX_SCHEMA_VERSION,
        "revision": 0,
        "currentPlanSlug": None,
        "updatedAt": now(),
        "plans": [],
    }


def load_index(root: Path, *, allow_missing: bool = False) -> dict:
    path = index_path(root)
    if not path.exists():
        if allow_missing:
            return empty_index()
        die(f"missing file: {path}")
    index = read_json(path)
    if index.get("schemaVersion") != INDEX_SCHEMA_VERSION:
        die(f"unsupported index schemaVersion: {index.get('schemaVersion')}")
    return index


def find_entry(index: dict, slug: str) -> dict:
    entry = next((value for value in index.get("plans", []) if value.get("slug") == slug), None)
    if entry is None:
        die(f"unknown plan: {slug}")
    return entry


def load_plan_content(root: Path, slug: str) -> dict:
    return read_json(plan_path(root, slug))


def selected_plan(args: argparse.Namespace, root: Path) -> tuple[dict, dict, dict]:
    index = load_index(root)
    slug = getattr(args, "plan", None) or index.get("currentPlanSlug")
    if not slug:
        die("there is no current plan; pass --plan")
    entry = find_entry(index, slug)
    return index, entry, load_plan_content(root, slug)


def save_index(root: Path, index: dict) -> None:
    index["revision"] = int(index.get("revision", 0)) + 1
    index["updatedAt"] = now()
    atomic_json(index_path(root), index)


def save_plan_content(root: Path, index: dict, entry: dict, plan: dict, *, render: bool = True) -> dict:
    timestamp = now()
    plan["updatedAt"] = timestamp
    entry["updatedAt"] = timestamp
    atomic_json(plan_path(root, entry["slug"]), plan)
    save_index(root, index)
    if render:
        return render_status(root, entry, plan)
    return status_projection(entry, plan, root)


@contextlib.contextmanager
def repository_lock(root: Path):
    if fcntl is None:
        die("plan mutations require fcntl-based locking on this platform")
    lock_path = plans_dir(root) / ".planctl.lock"
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with lock_path.open("a+", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def event(root: Path, slug: str, event_type: str, actor: str, actor_type: str, details: dict) -> None:
    timestamp = now()
    token = uuid.uuid4().hex[:8]
    safe_time = timestamp.replace(":", "-")
    payload = {
        "schemaVersion": SCHEMA_VERSION,
        "eventId": f"{safe_time}-{event_type}-{token}",
        "occurredAt": timestamp,
        "type": event_type,
        "planSlug": slug,
        "actor": actor,
        "actorType": actor_type,
        "details": details,
    }
    path = plans_dir(root) / slug / "events" / f"{payload['eventId']}.json"
    atomic_json(path, payload)


def all_items(plan: dict) -> list[dict]:
    return [item for phase in plan.get("phases", []) for item in phase.get("items", [])]


def item_map(plan: dict) -> dict[str, dict]:
    return {item["id"]: item for item in all_items(plan)}


def find_item(plan: dict, item_id: str) -> tuple[dict, dict]:
    for phase in plan.get("phases", []):
        for item in phase.get("items", []):
            if item.get("id") == item_id:
                return phase, item
    die(f"unknown item: {item_id}")


def dependencies_done(plan: dict, item: dict) -> bool:
    items = item_map(plan)
    return all(dep in items and items[dep]["status"] == "done" for dep in item.get("dependsOn", []))


def item_readiness(item: dict, items: dict[str, dict]) -> tuple[str, list[str]]:
    status = item["status"]
    if status in {"done", "failed", "in-progress", "blocked"}:
        return status, []
    blockers = [dep for dep in item.get("dependsOn", []) if items.get(dep, {}).get("status") != "done"]
    if blockers:
        return "blocked", blockers
    return "ready", []


def require_state(entry: dict, allowed: set[str], action: str) -> None:
    if entry.get("state") not in allowed:
        die(f"{action} requires plan state in {sorted(allowed)}, found {entry.get('state')}")


def require_human(args: argparse.Namespace, action: str) -> None:
    if args.actor_type != "human":
        die(f"{action} requires --actor-type human — surface this decision to the user")


def run_git(root: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def require_git_root(root: Path) -> None:
    result = run_git(root, ["rev-parse", "--show-toplevel"])
    if result.returncode != 0:
        die("ROOT must be a git repository with at least one commit")
    reported = Path(result.stdout.strip()).resolve()
    if reported != root.resolve():
        die(f"--root must be the git top-level: {reported}")


def git_head(root: Path) -> str:
    result = run_git(root, ["rev-parse", "HEAD"])
    if result.returncode != 0:
        die("cannot activate a plan before the repository has an initial commit")
    return result.stdout.strip()


def is_tool_storage_path(path: str) -> bool:
    return path == "plans" or path.startswith("plans/") or path == "plan-dashboard.html"


def git_dirty_paths(root: Path) -> list[str]:
    result = run_git(root, ["status", "--porcelain=v1", "--untracked-files=all"])
    if result.returncode != 0:
        die(f"git status failed: {result.stderr.strip()}")
    dirty = []
    for line in result.stdout.splitlines():
        if not line:
            continue
        raw = line[3:]
        path = raw.split(" -> ", 1)[-1]
        if not is_tool_storage_path(path):
            dirty.append(path)
    return sorted(set(dirty))


def capture_activation_baseline(root: Path) -> str:
    require_git_root(root)
    dirty = git_dirty_paths(root)
    if dirty:
        die("cannot activate with a dirty working tree outside plans/: " + ", ".join(dirty))
    return git_head(root)


def parse_name_status(output: str) -> dict[str, dict]:
    changes: dict[str, dict] = {}
    for line in output.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        code = parts[0]
        if code.startswith("R") and len(parts) >= 3:
            changes[parts[2]] = {"action": "move", "from": parts[1]}
        elif code.startswith("C") and len(parts) >= 3:
            changes[parts[2]] = {"action": "create", "from": parts[1]}
        elif len(parts) >= 2:
            action = {"A": "create", "M": "modify", "D": "delete"}.get(code[0], "modify")
            changes[parts[1]] = {"action": action, "from": None}
    return changes


def git_change_map(root: Path, baseline: str | None) -> dict[str, dict]:
    if not baseline:
        return {}
    require_git_root(root)
    combined = run_git(root, ["diff", "--find-renames", "--name-status", baseline])
    if combined.returncode != 0:
        die(f"git diff failed for baseline {baseline}: {combined.stderr.strip()}")
    changes = parse_name_status(combined.stdout)
    untracked = run_git(root, ["ls-files", "--others", "--exclude-standard"])
    if untracked.returncode != 0:
        die(f"git untracked-file scan failed: {untracked.stderr.strip()}")
    for path in untracked.stdout.splitlines():
        path = path.strip()
        if path:
            changes[path] = {"action": "create", "from": None}
    return {path: info for path, info in changes.items() if not is_tool_storage_path(path)}


def path_matches(pattern: str, path: str) -> bool:
    return fnmatch.fnmatch(path, pattern)


def compute_change_coverage(plan: dict, change_map: dict[str, dict]) -> dict:
    covered_paths: set[str] = set()
    item_observations: dict[str, list[dict]] = {}
    for item in all_items(plan):
        observations = []
        for entry in item.get("plannedFiles", []):
            path = entry["path"]
            covered_paths.add(path)
            change = change_map.get(path)
            if change is None:
                state = "pending"
            elif change["action"] != entry["action"]:
                state = "action-mismatch"
            elif entry["action"] == "move" and change.get("from") != entry.get("from"):
                state = "action-mismatch"
            else:
                state = "change-observed"
            observations.append({
                "path": path,
                "plannedAction": entry["action"],
                "plannedFrom": entry.get("from"),
                "observedAction": change["action"] if change else None,
                "observedFrom": change.get("from") if change else None,
                "observedState": state,
            })
        item_observations[item["id"]] = observations
    doc_patterns = [target["pattern"] for target in (plan.get("documentationImpact") or {}).get("targets", [])]
    off_plan = sorted(
        (
            {"path": path, "action": info["action"]}
            for path, info in change_map.items()
            if path not in covered_paths and not any(path_matches(pattern, path) for pattern in doc_patterns)
        ),
        key=lambda entry: entry["path"],
    )
    observations = [obs for values in item_observations.values() for obs in values]
    return {
        "planned": len(observations),
        "observed": sum(obs["observedState"] == "change-observed" for obs in observations),
        "pending": sum(obs["observedState"] == "pending" for obs in observations),
        "mismatched": sum(obs["observedState"] == "action-mismatch" for obs in observations),
        "unexpected": len(off_plan),
        "offPlanChanges": off_plan,
        "items": item_observations,
    }


def compute_documentation_impact(plan: dict, change_map: dict[str, dict], has_baseline: bool) -> dict:
    doc_impact = plan.get("documentationImpact")
    if not doc_impact or doc_impact.get("mode", "none") == "none":
        return {"status": "skipped", "mode": (doc_impact or {}).get("mode", "none")}
    if not has_baseline:
        return {"status": "skipped", "mode": doc_impact["mode"], "message": "Plan 尚未激活,没有 Git 基线"}
    changed_paths = list(change_map)
    matched, missing = [], []
    for target in doc_impact.get("targets", []):
        pattern = target["pattern"]
        hits = [path for path in changed_paths if path_matches(pattern, path)]
        (matched if hits else missing).append(pattern if not hits else {"pattern": pattern, "matchedPaths": hits})
    coverage = doc_impact.get("coverage", "all")
    ok = not missing if coverage == "all" else bool(matched)
    return {
        "status": "pass" if ok else "fail",
        "mode": doc_impact["mode"],
        "coverage": coverage,
        "matchedTargets": len(matched),
        "totalTargets": len(doc_impact.get("targets", [])),
        "missingTargets": missing,
        "completionBlocked": not ok,
        "message": "所有声明的文档范围都已覆盖" if ok else f"缺少覆盖: {', '.join(missing)}",
    }


def validate_plan(entry: dict, plan: dict) -> list[str]:
    slug = entry.get("slug", "<unknown>")
    errors = []
    for key in ["schemaVersion", "slug", "goal", "phases", "checkpoint", "issues"]:
        if key not in plan:
            errors.append(f"{slug}: missing {key}")
    if plan.get("schemaVersion") != PLAN_SCHEMA_VERSION:
        errors.append(f"{slug}: unsupported plan schemaVersion")
    if plan.get("slug") != slug:
        errors.append(f"{slug}: plan.json slug does not match registry")
    phase_ids = [phase.get("id") for phase in plan.get("phases", [])]
    if len(phase_ids) != len(set(phase_ids)):
        errors.append(f"{slug}: duplicate phase id")
    items = all_items(plan)
    ids = [item.get("id") for item in items]
    if len(ids) != len(set(ids)):
        errors.append(f"{slug}: duplicate item id")
    known = set(ids)
    graph = {}
    for item in items:
        item_id = item.get("id")
        graph[item_id] = item.get("dependsOn", [])
        if item.get("status") not in ITEM_STATES:
            errors.append(f"{slug}/{item_id}: invalid item status")
        if item.get("verifyKind") not in VERIFY_KINDS:
            errors.append(f"{slug}/{item_id}: verifyKind is required")
        files = item.get("plannedFiles", [])
        no_file_impact = item.get("noFileImpact") is True
        if bool(files) == no_file_impact:
            errors.append(f"{slug}/{item_id}: declare plannedFiles or noFileImpact=true, exclusively")
        if item.get("status") == "done":
            if not item.get("evidence"):
                errors.append(f"{slug}/{item_id}: done item has no evidence")
            if item.get("verifiedBy") not in VERIFY_SOURCES:
                errors.append(f"{slug}/{item_id}: done item must declare verifiedBy")
        if item.get("status") in {"failed", "blocked"} and not item.get("reason"):
            errors.append(f"{slug}/{item_id}: {item.get('status')} item has no reason")
        for file_entry in files:
            if file_entry.get("action") not in FILE_ACTIONS:
                errors.append(f"{slug}/{item_id}: invalid file action for {file_entry.get('path')}")
            if file_entry.get("action") == "move" and not file_entry.get("from"):
                errors.append(f"{slug}/{item_id}: move has no source path")
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
    doc_impact = plan.get("documentationImpact")
    if doc_impact:
        if doc_impact.get("mode") not in DOC_MODES:
            errors.append(f"{slug}: invalid documentationImpact.mode")
        if doc_impact.get("mode") == "none" and not doc_impact.get("reason"):
            errors.append(f"{slug}: documentationImpact.mode=none requires reason")
        if doc_impact.get("mode") == "required":
            if doc_impact.get("coverage") not in DOC_COVERAGE:
                errors.append(f"{slug}: invalid documentationImpact.coverage")
            if not doc_impact.get("targets"):
                errors.append(f"{slug}: required documentationImpact needs targets")
    return errors


def validate_store(root: Path, index: dict) -> list[str]:
    errors = []
    if index.get("schemaVersion") != INDEX_SCHEMA_VERSION:
        errors.append("index: unsupported schemaVersion")
    entries = index.get("plans")
    if not isinstance(entries, list):
        return ["index: plans must be a list"]
    slugs = [entry.get("slug") for entry in entries]
    if len(slugs) != len(set(slugs)):
        errors.append("index: duplicate plan slug")
    current = index.get("currentPlanSlug")
    current_entries = [entry for entry in entries if entry.get("state") in CURRENT_STATES]
    if current is None and current_entries:
        errors.append("index: active/paused plan exists without currentPlanSlug")
    if current is not None:
        matches = [entry for entry in current_entries if entry.get("slug") == current]
        if len(matches) != 1 or len(current_entries) != 1:
            errors.append("index: currentPlanSlug must identify the only active/paused plan")
    for entry in entries:
        slug = entry.get("slug")
        if entry.get("state") not in PLAN_STATES:
            errors.append(f"{slug}: invalid registry state")
        if entry.get("path") != f"{slug}/plan.json":
            errors.append(f"{slug}: invalid registry path")
        if entry.get("state") in CURRENT_STATES | {"completed"} and not entry.get("baselineCommit"):
            errors.append(f"{slug}: state {entry.get('state')} requires baselineCommit")
        path = plan_path(root, slug)
        if not path.exists():
            errors.append(f"{slug}: missing plan.json")
            continue
        errors.extend(validate_plan(entry, read_json(path)))
        if entry.get("state") in TERMINAL_STATES:
            frozen_path = status_path(root, slug)
            if not frozen_path.exists():
                errors.append(f"{slug}: terminal plan is missing frozen status.json")
            else:
                frozen = read_json(frozen_path)
                if frozen.get("plan", {}).get("state") != entry.get("state"):
                    errors.append(f"{slug}: frozen status state does not match registry")
    registered = set(slugs)
    if plans_dir(root).exists():
        for path in plans_dir(root).glob("*/plan.json"):
            if path.parent.name not in registered:
                errors.append(f"orphan plan directory: {path.parent.name}")
    return errors


def derived_execution(entry: dict, plan: dict) -> dict:
    checkpoint = plan["checkpoint"]
    state = entry["state"]
    current_id = checkpoint.get("currentItemId")
    current_item = item_map(plan).get(current_id) if current_id else None
    if state == "completed":
        execution_state = "completed"
    elif state == "paused" or (current_item and current_item.get("status") in {"failed", "blocked"}):
        execution_state = "stopped"
    elif current_item and current_item.get("status") == "in-progress":
        execution_state = "running"
    else:
        execution_state = "idle"
    return {"state": execution_state, **checkpoint}


def planned_file_failures(phases: list[dict]) -> list[dict]:
    """Return unsatisfied file observations for items already asserted done.

    This is the shared source for both early derived issues and the completion
    gate, so the dashboard cannot report a clean state that completion rejects.
    """
    failures = []
    for phase in phases:
        for item in phase.get("items", []):
            if item.get("status") != "done":
                continue
            for observation in item.get("changeObservations", []):
                if observation.get("observedState") != "change-observed":
                    failures.append({
                        "itemId": item["id"],
                        "itemTitle": item["title"],
                        "observation": observation,
                    })
    return failures


def status_projection(entry: dict, plan: dict, root: Path) -> dict:
    baseline = entry.get("baselineCommit")
    change_map = git_change_map(root, baseline)
    coverage = compute_change_coverage(plan, change_map)
    doc_check = compute_documentation_impact(plan, change_map, bool(baseline))
    items = all_items(plan)
    items_by_id = item_map(plan)
    readiness_counts = {"ready": 0, "blocked": 0, "in-progress": 0, "done": 0, "failed": 0}
    verified_counts = {source: 0 for source in (*VERIFY_SOURCES, "unverified")}
    enriched_phases = []
    for phase in plan.get("phases", []):
        enriched_items = []
        for item in phase.get("items", []):
            readiness, blocked_by = item_readiness(item, items_by_id)
            readiness_counts[readiness] = readiness_counts.get(readiness, 0) + 1
            verified_counts[item.get("verifiedBy", "unverified")] += 1
            enriched_items.append({
                **item,
                "readiness": readiness,
                "blockedBy": blocked_by,
                "changeObservations": coverage["items"].get(item["id"], []),
            })
        counts = {state: sum(item["status"] == state for item in phase.get("items", [])) for state in ITEM_STATES}
        enriched_phases.append({**phase, "items": enriched_items, "counts": {"total": len(phase.get("items", [])), "status": counts}})
    open_issues = [issue for issue in plan.get("issues", []) if issue.get("status") == "open"]
    derived_issues = []
    failures_by_item: dict[str, dict] = {}
    for failure in planned_file_failures(enriched_phases):
        group = failures_by_item.setdefault(failure["itemId"], {
            "itemTitle": failure["itemTitle"],
            "observations": [],
        })
        group["observations"].append(failure["observation"])
    for item_id, group in failures_by_item.items():
        details = []
        for observation in group["observations"]:
            observed = observation.get("observedAction") or "none"
            details.append(
                f"{observation['path']}: planned={observation['plannedAction']}, "
                f"observed={observed}, state={observation['observedState']}"
            )
        derived_issues.append({
            "id": f"derived-planned-file-mismatch-{item_id}",
            "type": "planned-file-mismatch",
            "severity": "critical",
            "status": "open",
            "title": f"已完成 Item {item_id} 的计划文件未满足",
            "detail": "; ".join(details),
            "nextAction": "完成缺失改动、修正实际动作,或用 update-item --file 更新错误声明。",
        })
    for change in coverage["offPlanChanges"]:
        derived_issues.append({
            "id": f"derived-off-plan-{change['path']}",
            "type": "off-plan-change",
            "severity": "warning",
            "status": "open",
            "title": f"{change['path']} 未登记在当前 Plan",
            "detail": f"Git 检测到 {change['action']} 改动,但当前 Plan 没有声明这个路径。",
            "nextAction": "登记到正确的 item,或者撤回该改动。",
        })
    if doc_check.get("status") == "fail":
        derived_issues.append({
            "id": "derived-documentation-impact-missing",
            "type": "documentation-impact-missing",
            "severity": "critical",
            "status": "open",
            "title": "声明的文档范围还没有出现变更",
            "detail": doc_check.get("message", ""),
            "nextAction": "更新声明范围内的文档,然后重新核对。",
        })
    next_actions = []
    for phase in enriched_phases:
        for item in phase["items"]:
            if item["readiness"] in {"failed", "blocked", "ready"} or item["status"] == "in-progress":
                next_actions.append({"type": "item", "id": item["id"], "title": item["title"], "reason": item["readiness"]})
    for issue in [*open_issues, *derived_issues]:
        next_actions.append({"type": "issue", "id": issue["id"], "title": issue["title"], "reason": issue.get("nextAction", "")})
    return {
        "schemaVersion": SCHEMA_VERSION,
        "generatedAt": now(),
        "plan": {
            "slug": entry["slug"],
            "name": entry["name"],
            "goal": plan["goal"],
            "state": entry["state"],
            "owner": plan.get("owner"),
            "currentPhaseId": plan.get("currentPhaseId"),
            "baselineCommit": baseline,
            "replacedBy": entry.get("replacedBy"),
            "updatedAt": entry["updatedAt"],
        },
        "execution": derived_execution(entry, plan),
        "summary": {
            "total": len(items),
            "status": {state: sum(item["status"] == state for item in items) for state in ITEM_STATES},
            "readiness": readiness_counts,
            "verifiedBy": verified_counts,
            "openIssues": len(open_issues) + len(derived_issues),
        },
        "changeCoverage": {key: value for key, value in coverage.items() if key != "items"},
        "documentationImpact": doc_check,
        "phases": enriched_phases,
        "issues": plan.get("issues", []),
        "derivedIssues": derived_issues,
        "nextActions": next_actions,
    }


def render_status(root: Path, entry: dict, plan: dict) -> dict:
    status = status_projection(entry, plan, root)
    atomic_json(status_path(root, entry["slug"]), status)
    return status


def parse_file_arg(value: str) -> dict:
    parts = value.split(":")
    if len(parts) == 1:
        return {"path": parts[0], "action": "create", "from": None}
    if len(parts) == 2:
        path, action = parts
        if action not in FILE_ACTIONS:
            die(f"invalid action in --file '{value}'")
        return {"path": path, "action": action, "from": None}
    if len(parts) == 3:
        path, action, source = parts
        if action != "move" or not source:
            die(f"invalid move in --file '{value}'")
        return {"path": path, "action": "move", "from": source}
    die(f"invalid --file '{value}'")


def parse_doc_target_arg(value: str) -> dict:
    if ":" not in value:
        die(f"--doc-target must be 'pattern:purpose', got '{value}'")
    pattern, purpose = value.split(":", 1)
    return {"pattern": pattern, "purpose": purpose}


def build_doc_impact(mode: str | None, coverage: str, reason: str | None, targets: list[str] | None) -> dict | None:
    if not mode:
        return None
    if mode == "required" and not targets:
        die("documentationImpact.mode=required needs at least one target")
    if mode == "none" and not reason:
        die("documentationImpact.mode=none needs a reason")
    return {
        "mode": mode,
        "coverage": coverage,
        "reason": reason,
        "targets": [parse_doc_target_arg(value) for value in (targets or [])],
    }


def cmd_create(args: argparse.Namespace, root: Path) -> dict:
    index = load_index(root, allow_missing=True)
    if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,62}[a-z0-9]", args.slug):
        die("slug must use 3-64 lowercase letters, digits, and hyphens")
    if any(entry["slug"] == args.slug for entry in index["plans"]):
        die(f"plan already exists: {args.slug}")
    baseline = None
    state = "draft"
    if args.activate:
        require_human(args, "create --activate")
        if index.get("currentPlanSlug"):
            die(f"current plan already exists: {index['currentPlanSlug']}")
        baseline = capture_activation_baseline(root)
        state = "active"
    timestamp = now()
    entry = {
        "slug": args.slug,
        "name": args.name,
        "state": state,
        "path": f"{args.slug}/plan.json",
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "activatedAt": timestamp if state == "active" else None,
        "baselineCommit": baseline,
        "replacedBy": None,
    }
    plan = {
        "schemaVersion": PLAN_SCHEMA_VERSION,
        "slug": args.slug,
        "goal": args.goal,
        "owner": args.owner,
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "currentPhaseId": None,
        "documentationImpact": build_doc_impact(args.doc_mode, args.doc_coverage, args.doc_reason, args.doc_target),
        "phases": [],
        "checkpoint": {"currentItemId": None, "lastCompletedItemId": None, "stopReason": None, "updatedAt": timestamp},
        "issues": [],
    }
    atomic_json(plan_path(root, args.slug), plan)
    index["plans"].append(entry)
    if state == "active":
        index["currentPlanSlug"] = args.slug
    save_index(root, index)
    event(root, args.slug, "plan-created", args.actor, args.actor_type, {"state": state, "goal": args.goal})
    return render_status(root, entry, plan)


def cmd_set_documentation_impact(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    require_state(entry, {"draft", "active"}, "set-documentation-impact")
    plan["documentationImpact"] = build_doc_impact(args.mode, args.coverage, args.reason, args.target)
    event(root, entry["slug"], "documentation-impact-set", args.actor, args.actor_type, plan["documentationImpact"])
    return save_plan_content(root, index, entry, plan)


def cmd_add_phase(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    require_state(entry, {"draft", "active"}, "add-phase")
    if any(phase["id"] == args.id for phase in plan["phases"]):
        die(f"phase already exists: {args.id}")
    plan["phases"].append({"id": args.id, "title": args.title, "purpose": args.purpose, "items": []})
    if plan["currentPhaseId"] is None:
        plan["currentPhaseId"] = args.id
    event(root, entry["slug"], "phase-added", args.actor, args.actor_type, {"phaseId": args.id})
    return save_plan_content(root, index, entry, plan)


def cmd_add_item(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    require_state(entry, {"draft", "active"}, "add-item")
    if args.id in item_map(plan):
        die(f"item already exists: {args.id}")
    phase = next((value for value in plan["phases"] if value["id"] == args.phase), None)
    if phase is None:
        die(f"unknown phase: {args.phase}")
    dependencies = [value for value in args.depends_on.split(",") if value]
    missing = [dep for dep in dependencies if dep not in item_map(plan)]
    if missing:
        die(f"unknown dependencies: {', '.join(missing)}")
    if bool(args.file) == bool(args.no_file_impact):
        die("add-item requires --file or --no-file-impact, exclusively")
    item = {
        "id": args.id,
        "title": args.title,
        "purpose": args.purpose,
        "dependsOn": dependencies,
        "status": "not-started",
        "verifyKind": args.verify_kind,
        "verifiedBy": "unverified",
        "evidence": None,
        "reason": None,
        "noFileImpact": args.no_file_impact,
        "plannedFiles": [parse_file_arg(value) for value in (args.file or [])],
        "updatedAt": now(),
    }
    phase["items"].append(item)
    event(root, entry["slug"], "item-added", args.actor, args.actor_type, {"phaseId": args.phase, "itemId": args.id})
    return save_plan_content(root, index, entry, plan)


def set_item_state(plan: dict, phase: dict, item: dict, state: str, evidence: str | None, reason: str | None, verified_by: str | None) -> None:
    if state in {"in-progress", "done"} and not dependencies_done(plan, item):
        die("item dependencies are not done")
    if state == "in-progress":
        running = [value["id"] for value in all_items(plan) if value["status"] == "in-progress" and value["id"] != item["id"]]
        if running:
            die(f"another item is already in progress: {running[0]}")
    if state == "done":
        if not evidence or not verified_by:
            die("done items require --evidence and --verified-by")
    if state in {"failed", "blocked"} and not reason:
        die(f"{state} items require --reason")
    item["status"] = state
    item["evidence"] = evidence
    item["verifiedBy"] = verified_by or "unverified"
    item["reason"] = reason if state in {"failed", "blocked"} else None
    item["updatedAt"] = now()
    plan["currentPhaseId"] = phase["id"]
    checkpoint = plan["checkpoint"]
    checkpoint["updatedAt"] = now()
    if state == "in-progress":
        checkpoint.update({"currentItemId": item["id"], "stopReason": None})
    elif state == "done":
        checkpoint.update({"currentItemId": None, "lastCompletedItemId": item["id"], "stopReason": None})
    elif state in {"failed", "blocked"}:
        checkpoint.update({"currentItemId": item["id"], "stopReason": reason})
    elif checkpoint.get("currentItemId") == item["id"]:
        checkpoint.update({"currentItemId": None, "stopReason": None})


def cmd_update_item(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    require_state(entry, {"active"}, "update-item")
    phase, item = find_item(plan, args.item)
    set_item_state(plan, phase, item, args.status, args.evidence, args.reason, args.verified_by)
    for value in args.file or []:
        new_entry = parse_file_arg(value)
        existing = next((current for current in item["plannedFiles"] if current["path"] == new_entry["path"]), None)
        if existing:
            existing.update(new_entry)
        else:
            item["plannedFiles"].append(new_entry)
        item["noFileImpact"] = False
    event(root, entry["slug"], "item-updated", args.actor, args.actor_type, {"itemId": args.item, "status": args.status})
    return save_plan_content(root, index, entry, plan)


def cmd_verify(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    require_state(entry, {"active"}, "verify")
    phase, item = find_item(plan, args.item)
    if args.result == "not-run":
        event(root, entry["slug"], "item-verification-not-run", args.actor, args.actor_type, {"itemId": args.item, "evidence": args.evidence})
        return save_plan_content(root, index, entry, plan)
    state = "done" if args.result == "pass" else "failed"
    set_item_state(plan, phase, item, state, args.evidence, args.reason, args.verified_by)
    event(root, entry["slug"], "item-verified", args.actor, args.actor_type, {"itemId": args.item, "result": args.result, "evidence": args.evidence})
    return save_plan_content(root, index, entry, plan)


def cmd_checkpoint(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    require_state(entry, {"active"}, "checkpoint")
    if args.item:
        find_item(plan, args.item)
    plan["checkpoint"].update({"currentItemId": args.item, "stopReason": args.reason, "updatedAt": now()})
    event(root, entry["slug"], "execution-stopped", args.actor, args.actor_type, {"itemId": args.item, "reason": args.reason})
    return save_plan_content(root, index, entry, plan)


def cmd_add_issue(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    require_state(entry, {"active"}, "add-issue")
    if args.item:
        find_item(plan, args.item)
    issue = {
        "id": f"issue-{uuid.uuid4().hex[:8]}",
        "itemId": args.item,
        "title": args.title,
        "detail": args.detail,
        "severity": args.severity,
        "status": "open",
        "nextAction": args.next_action,
        "createdAt": now(),
        "resolvedAt": None,
        "resolution": None,
    }
    plan["issues"].append(issue)
    event(root, entry["slug"], "issue-opened", args.actor, args.actor_type, issue)
    return save_plan_content(root, index, entry, plan)


def cmd_resolve_issue(args: argparse.Namespace, root: Path) -> dict:
    index, entry, plan = selected_plan(args, root)
    require_state(entry, {"active"}, "resolve-issue")
    issue = next((value for value in plan["issues"] if value["id"] == args.issue), None)
    if issue is None:
        die(f"unknown issue: {args.issue}")
    if issue["status"] == "resolved":
        die(f"issue is already resolved: {args.issue}")
    issue.update({"status": "resolved", "resolvedAt": now(), "resolution": args.resolution})
    event(root, entry["slug"], "issue-resolved", args.actor, args.actor_type, {"issueId": args.issue, "resolution": args.resolution})
    return save_plan_content(root, index, entry, plan)


def completion_problems(status: dict, plan: dict) -> list[str]:
    problems = []
    remaining = [item["id"] for item in all_items(plan) if item["status"] != "done"]
    if remaining:
        problems.append(f"remaining items={remaining}")
    open_issues = [issue["id"] for issue in plan["issues"] if issue["status"] == "open"]
    if open_issues:
        problems.append(f"open issues={open_issues}")
    if status["changeCoverage"]["unexpected"]:
        problems.append(f"unexpected changes={[c['path'] for c in status['changeCoverage']['offPlanChanges']]}")
    bad_files = [
        f"{failure['itemId']}:{failure['observation']['path']}:{failure['observation']['observedState']}"
        for failure in planned_file_failures(status["phases"])
    ]
    if bad_files:
        problems.append(f"planned file checks failed={bad_files}")
    if status["documentationImpact"].get("completionBlocked"):
        problems.append(f"documentation impact missing={status['documentationImpact'].get('missingTargets', [])}")
    return problems


def cmd_transition(args: argparse.Namespace, root: Path) -> dict:
    require_human(args, f"transition to {args.state}")
    index, entry, plan = selected_plan(args, root)
    old_state = entry["state"]
    if old_state in TERMINAL_STATES:
        die(f"terminal plan is immutable: {old_state}")
    if args.state == old_state:
        die(f"plan is already {old_state}")
    allowed = {
        "draft": {"active", "cancelled"},
        "active": {"paused", "completed", "cancelled"},
        "paused": {"active", "cancelled"},
    }
    if args.state not in allowed.get(old_state, set()):
        die(f"invalid transition: {old_state} -> {args.state}")
    if args.state == "active" and old_state == "draft":
        if index.get("currentPlanSlug"):
            die(f"current plan already exists: {index['currentPlanSlug']}")
        entry["baselineCommit"] = capture_activation_baseline(root)
        entry["activatedAt"] = now()
        index["currentPlanSlug"] = entry["slug"]
    elif args.state == "active" and old_state == "paused":
        if index.get("currentPlanSlug") != entry["slug"]:
            die("paused plan lost the current-plan slot")
        plan["checkpoint"]["stopReason"] = None
    elif args.state == "paused":
        if index.get("currentPlanSlug") != entry["slug"]:
            die("only the current active plan can be paused")
        plan["checkpoint"]["stopReason"] = args.reason
    elif args.state == "completed":
        if old_state != "active" or index.get("currentPlanSlug") != entry["slug"]:
            die("only the current active plan can be completed")
        preview = status_projection(entry, plan, root)
        problems = completion_problems(preview, plan)
        if problems:
            die("cannot complete; " + "; ".join(problems))
        index["currentPlanSlug"] = None
        plan["checkpoint"].update({"currentItemId": None, "stopReason": None, "updatedAt": now()})
    elif args.state == "cancelled":
        if old_state in CURRENT_STATES:
            if index.get("currentPlanSlug") != entry["slug"]:
                die("active/paused plan does not own the current-plan slot")
            index["currentPlanSlug"] = None
        plan["checkpoint"]["stopReason"] = args.reason
    entry["state"] = args.state
    event(root, entry["slug"], "plan-transitioned", args.actor, args.actor_type, {"fromState": old_state, "toState": args.state, "reason": args.reason})
    return save_plan_content(root, index, entry, plan)


def cmd_switch(args: argparse.Namespace, root: Path) -> dict:
    require_human(args, "switch")
    index = load_index(root)
    old_slug = index.get("currentPlanSlug")
    if not old_slug:
        die("switch requires a current active/paused plan")
    old_entry = find_entry(index, old_slug)
    new_entry = find_entry(index, args.to)
    if new_entry["state"] != "draft":
        die("switch target must be draft")
    baseline = capture_activation_baseline(root)
    old_plan = load_plan_content(root, old_slug)
    new_plan = load_plan_content(root, args.to)
    old_entry.update({"state": "cancelled", "replacedBy": args.to, "updatedAt": now()})
    old_plan["checkpoint"].update({"stopReason": args.reason, "updatedAt": now()})
    new_entry.update({"state": "active", "baselineCommit": baseline, "activatedAt": now(), "updatedAt": now()})
    index["currentPlanSlug"] = args.to
    atomic_json(plan_path(root, old_slug), old_plan)
    atomic_json(plan_path(root, args.to), new_plan)
    save_index(root, index)
    event(root, old_slug, "plan-replaced", args.actor, args.actor_type, {"replacedBy": args.to, "reason": args.reason})
    event(root, args.to, "plan-activated", args.actor, args.actor_type, {"replaces": old_slug, "reason": args.reason})
    render_status(root, old_entry, old_plan)
    return render_status(root, new_entry, new_plan)


def cmd_validate(args: argparse.Namespace, root: Path) -> dict:
    index = load_index(root)
    errors = validate_store(root, index)
    if errors:
        die("; ".join(errors))
    return {"valid": True, "plans": len(index["plans"]), "currentPlanSlug": index.get("currentPlanSlug"), "revision": index["revision"]}


def cmd_show(args: argparse.Namespace, root: Path) -> dict:
    _, entry, plan = selected_plan(args, root)
    if entry["state"] in TERMINAL_STATES:
        frozen_path = status_path(root, entry["slug"])
        if not frozen_path.exists():
            die(f"terminal plan is missing frozen status: {entry['slug']}")
        return read_json(frozen_path)
    return render_status(root, entry, plan)


def cmd_changes(args: argparse.Namespace, root: Path) -> dict:
    status = cmd_show(args, root)
    return {"changeCoverage": status["changeCoverage"], "documentationImpact": status["documentationImpact"]}


def cmd_history(args: argparse.Namespace, root: Path) -> dict:
    _, entry, _ = selected_plan(args, root)
    if args.limit is not None and args.limit < 0:
        die("--limit must be non-negative")
    paths = sorted((plans_dir(root) / entry["slug"] / "events").glob("*.json"))
    events = [read_json(path) for path in paths]
    if args.limit is not None:
        events = events[-args.limit:]
    return {"planSlug": entry["slug"], "events": events}


def cmd_install_dashboard(args: argparse.Namespace, root: Path) -> dict:
    source = Path(__file__).resolve().parents[1] / "assets" / "dashboard.html"
    target = root / "plan-dashboard.html"
    shutil.copyfile(source, target)
    return {"installed": str(target)}


def add_plan_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--plan", help="plan slug; defaults to currentPlanSlug")


def add_actor_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--actor", default=os.environ.get("USER", "codex"))
    parser.add_argument("--actor-type", choices=["human", "agent"], default="agent")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="git repository root")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("--slug", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--goal", required=True)
    create.add_argument("--owner", default=os.environ.get("USER", "codex"))
    create.add_argument("--activate", action="store_true")
    create.add_argument("--doc-mode", choices=sorted(DOC_MODES))
    create.add_argument("--doc-coverage", choices=sorted(DOC_COVERAGE), default="all")
    create.add_argument("--doc-reason")
    create.add_argument("--doc-target", action="append")
    add_actor_option(create)
    create.set_defaults(handler=cmd_create)

    doc = sub.add_parser("set-documentation-impact")
    add_plan_option(doc)
    doc.add_argument("--mode", required=True, choices=sorted(DOC_MODES))
    doc.add_argument("--coverage", choices=sorted(DOC_COVERAGE), default="all")
    doc.add_argument("--reason")
    doc.add_argument("--target", action="append")
    add_actor_option(doc)
    doc.set_defaults(handler=cmd_set_documentation_impact)

    phase = sub.add_parser("add-phase")
    add_plan_option(phase)
    phase.add_argument("--id", required=True)
    phase.add_argument("--title", required=True)
    phase.add_argument("--purpose", required=True)
    add_actor_option(phase)
    phase.set_defaults(handler=cmd_add_phase)

    item = sub.add_parser("add-item")
    add_plan_option(item)
    item.add_argument("--phase", required=True)
    item.add_argument("--id", required=True)
    item.add_argument("--title", required=True)
    item.add_argument("--purpose", required=True)
    item.add_argument("--depends-on", default="")
    item.add_argument("--file", action="append")
    item.add_argument("--no-file-impact", action="store_true")
    item.add_argument("--verify-kind", required=True, choices=sorted(VERIFY_KINDS))
    add_actor_option(item)
    item.set_defaults(handler=cmd_add_item)

    update = sub.add_parser("update-item")
    add_plan_option(update)
    update.add_argument("--item", required=True)
    update.add_argument("--status", required=True, choices=sorted(ITEM_STATES))
    update.add_argument("--evidence")
    update.add_argument("--reason")
    update.add_argument("--verified-by", choices=sorted(VERIFY_SOURCES))
    update.add_argument("--file", action="append")
    add_actor_option(update)
    update.set_defaults(handler=cmd_update_item)

    verify = sub.add_parser("verify")
    add_plan_option(verify)
    verify.add_argument("--item", required=True)
    verify.add_argument("--result", required=True, choices=["pass", "fail", "not-run"])
    verify.add_argument("--evidence", required=True)
    verify.add_argument("--reason")
    verify.add_argument("--verified-by", choices=sorted(VERIFY_SOURCES))
    add_actor_option(verify)
    verify.set_defaults(handler=cmd_verify)

    checkpoint = sub.add_parser("checkpoint")
    add_plan_option(checkpoint)
    checkpoint.add_argument("--item")
    checkpoint.add_argument("--reason", required=True)
    add_actor_option(checkpoint)
    checkpoint.set_defaults(handler=cmd_checkpoint)

    issue = sub.add_parser("add-issue")
    add_plan_option(issue)
    issue.add_argument("--item")
    issue.add_argument("--title", required=True)
    issue.add_argument("--detail", required=True)
    issue.add_argument("--next-action", required=True)
    issue.add_argument("--severity", choices=["warning", "critical"], default="warning")
    add_actor_option(issue)
    issue.set_defaults(handler=cmd_add_issue)

    resolve = sub.add_parser("resolve-issue")
    add_plan_option(resolve)
    resolve.add_argument("--issue", required=True)
    resolve.add_argument("--resolution", required=True)
    add_actor_option(resolve)
    resolve.set_defaults(handler=cmd_resolve_issue)

    transition = sub.add_parser("transition")
    add_plan_option(transition)
    transition.add_argument("--state", required=True, choices=["active", "paused", "completed", "cancelled"])
    transition.add_argument("--reason", required=True)
    add_actor_option(transition)
    transition.set_defaults(handler=cmd_transition)

    switch = sub.add_parser("switch")
    switch.add_argument("--to", required=True)
    switch.add_argument("--reason", required=True)
    add_actor_option(switch)
    switch.set_defaults(handler=cmd_switch)

    validate = sub.add_parser("validate")
    validate.set_defaults(handler=cmd_validate)

    show = sub.add_parser("show")
    add_plan_option(show)
    show.set_defaults(handler=cmd_show)

    changes = sub.add_parser("changes")
    add_plan_option(changes)
    changes.set_defaults(handler=cmd_changes)

    history = sub.add_parser("history")
    add_plan_option(history)
    history.add_argument("--limit", type=int)
    history.set_defaults(handler=cmd_history)

    install = sub.add_parser("install-dashboard")
    install.set_defaults(handler=cmd_install_dashboard)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    try:
        if args.command in MUTATING_COMMANDS:
            with repository_lock(root):
                result = args.handler(args, root)
        else:
            result = args.handler(args, root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except PlanError as exc:
        print(f"planctl: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
