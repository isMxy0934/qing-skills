#!/usr/bin/env python3
"""Git-backed, resumable plan manager used by the track-ai-plans skill."""

from __future__ import annotations

import argparse
import copy
import contextlib
import datetime as dt
import fnmatch
import hashlib
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
except ImportError:  # pragma: no cover - qing-plans targets Unix Codex runtimes.
    fcntl = None


SCHEMA_VERSION = 2
LEGACY_SCHEMA_VERSION = 1
PLAN_STATES = {"draft", "active", "paused", "completed", "cancelled"}
CURRENT_STATES = {"active", "paused"}
TERMINAL_STATES = {"completed", "cancelled"}
ITEM_STATES = {"not-started", "in-progress", "done", "failed", "blocked"}
FILE_ACTIONS = {"create", "modify", "delete", "move"}
VERIFY_KINDS = {"test", "llm-review", "manual"}
VERIFY_SOURCES = {"script", "llm", "human"}
VERIFY_SOURCE_FOR_KIND = {"test": "script", "llm-review": "llm", "manual": "human"}
REVIEW_POLICIES = {"none", "single"}
AMENDMENT_KINDS = {"scope", "corrective", "temporary"}
DOC_MODES = {"required", "none"}
DOC_COVERAGE = {"all", "any"}
READ_ONLY_COMMANDS = {"validate", "show", "changes", "history", "resume"}
MUTATING_COMMANDS = {
    "create", "set-documentation-impact", "add-phase", "add-item", "review-plan",
    "upsert-module", "upsert-dependency", "propose-amendment", "review-amendment",
    "update-item", "verify", "checkpoint", "add-issue", "resolve-issue", "transition",
    "switch", "refresh-status", "install-dashboard", "migrate-store",
}
SYSTEM_MODULES = {
    "_unmapped": {"name": "Unmapped", "description": "Legacy or not-yet-classified paths", "pathPatterns": [],
                  "reason": "System fallback for incomplete classification", "evidence": "Qing Plans V2 schema"},
    "_cross-cutting": {"name": "Cross-cutting", "description": "Changes spanning several modules or no repository files", "pathPatterns": [],
                       "reason": "System bucket for cross-module or no-file work", "evidence": "Qing Plans V2 schema"},
}

_STORE_OVERRIDE: Path | None = None
_USING_LEGACY = False


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


def store_dir(root: Path) -> Path:
    return _STORE_OVERRIDE or root / "qing-plans"


def legacy_dir(root: Path) -> Path:
    return root / "plans"


def index_path(root: Path) -> Path:
    return store_dir(root) / "index.json"


def plan_path(root: Path, slug: str) -> Path:
    return store_dir(root) / slug / "plan.json"


def status_path(root: Path, slug: str) -> Path:
    return store_dir(root) / slug / "status.json"


def map_path(root: Path) -> Path:
    return store_dir(root) / "project-map.json"


def reject_root_inside_store(root: Path) -> None:
    if root.parent.name in {"plans", "qing-plans"} and (root / "plan.json").exists():
        die(f"--root ({root}) is a plan directory; use repository root {root.parent.parent}")


def verified_migration(root: Path) -> bool:
    path = root / "qing-plans" / "migration.json"
    if not path.exists():
        return False
    data = read_json(path)
    return data.get("state") == "verified" and data.get("safeToDeleteLegacy") is True


def select_store(root: Path, command: str) -> None:
    global _STORE_OVERRIDE, _USING_LEGACY
    new = root / "qing-plans"
    old = root / "plans"
    has_new, has_old = (new / "index.json").exists(), (old / "index.json").exists()
    _USING_LEGACY = False
    if old.exists() and has_old and new.exists() and not has_new:
        die("legacy plans/ exists beside an incomplete qing-plans/ directory; resolve the partial migration first")
    if has_new and has_old:
        if not verified_migration(root):
            die("both plans/ and qing-plans/ exist without a verified migration; refusing to choose an authority")
        _STORE_OVERRIDE = new
        return
    if has_new:
        _STORE_OVERRIDE = new
        return
    if has_old:
        if command == "migrate-store" or command in READ_ONLY_COMMANDS:
            _STORE_OVERRIDE = old
            _USING_LEGACY = True
            return
        die("legacy plans/ is read-only; run migrate-store --dry-run, then migrate-store")
    _STORE_OVERRIDE = new


def empty_index() -> dict:
    return {"schemaVersion": SCHEMA_VERSION, "revision": 0, "currentPlanSlug": None, "updatedAt": now(), "plans": []}


def empty_project_map() -> dict:
    timestamp = now()
    return {
        "schemaVersion": SCHEMA_VERSION,
        "revision": 0,
        "updatedAt": timestamp,
        "modules": [
            {"id": module_id, **value, "introducedByPlan": None, "updatedByPlan": None}
            for module_id, value in SYSTEM_MODULES.items()
        ],
        "dependencies": [],
    }


def load_index(root: Path, *, allow_missing: bool = False) -> dict:
    path = index_path(root)
    if not path.exists():
        if allow_missing:
            return empty_index()
        die(f"no plan store in {path.parent}; run `create` to start the first plan")
    data = read_json(path)
    expected = LEGACY_SCHEMA_VERSION if _USING_LEGACY else SCHEMA_VERSION
    if data.get("schemaVersion") != expected:
        die(f"unsupported index schemaVersion: {data.get('schemaVersion')}")
    return data


def load_project_map(root: Path, *, allow_missing: bool = False) -> dict:
    path = map_path(root)
    if not path.exists():
        if allow_missing:
            return empty_project_map()
        die(f"missing file: {path}")
    return read_json(path)


def find_entry(index: dict, slug: str) -> dict:
    entry = next((entry for entry in index.get("plans", []) if entry.get("slug") == slug), None)
    if entry is None:
        die(f"unknown plan: {slug}")
    return entry


def selected_plan(args: argparse.Namespace, root: Path) -> tuple[dict, dict, dict]:
    index = load_index(root)
    slug = getattr(args, "plan", None) or index.get("currentPlanSlug")
    if not slug:
        die("there is no current plan; pass --plan")
    entry = find_entry(index, slug)
    return index, entry, read_json(plan_path(root, slug))


def save_index(root: Path, index: dict) -> None:
    index["revision"] = int(index.get("revision", 0)) + 1
    index["updatedAt"] = now()
    atomic_json(index_path(root), index)


@contextlib.contextmanager
def repository_lock(root: Path):
    if fcntl is None:
        die("plan mutations require fcntl locking")
    lock_path = store_dir(root) / ".planctl.lock"
    created_store = not lock_path.parent.exists()
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    try:
        with lock_path.open("a+", encoding="utf-8") as handle:
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
            try:
                yield
            finally:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)
    finally:
        # Taking the lock is what first creates the store directory. A command that then
        # failed before writing anything must not leave that bare directory behind in the
        # repository; anything the command did write keeps it.
        if created_store and lock_path.parent.exists() and \
                {path.name for path in lock_path.parent.iterdir()} == {".planctl.lock"}:
            lock_path.unlink()
            lock_path.parent.rmdir()


def event(root: Path, slug: str, event_type: str, actor: str | None, actor_type: str, details: dict) -> None:
    timestamp = now()
    event_id = f"{timestamp.replace(':', '-')}-{event_type}-{uuid.uuid4().hex[:8]}"
    atomic_json(store_dir(root) / slug / "events" / f"{event_id}.json", {
        "schemaVersion": SCHEMA_VERSION, "eventId": event_id, "occurredAt": timestamp,
        "type": event_type, "planSlug": slug, "actor": actor, "actorType": actor_type,
        "details": details,
    })
