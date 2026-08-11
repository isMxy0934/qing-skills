"""Command-line parser and process entrypoint."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import storage as st
from .storage import *
from .git import *
from .domain import *
from .projection import *
from .commands import *
from .execution import *
from .amendments import *
from .migration import *


def add_plan_option(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--plan", help="plan slug; defaults to currentPlanSlug")


def add_actor_option(parser: argparse.ArgumentParser, *, required: bool = False) -> None:
    parser.add_argument("--actor", required=required, default=None if required else os.environ.get("USER", "codex"))
    parser.add_argument("--actor-type", choices=["human", "agent"], default="agent")


def add_review_args(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--result", required=True, choices=["pass", "fail"])
    parser.add_argument("--evidence", required=True)
    parser.add_argument("--reason")
    add_actor_option(parser, required=True)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", default=".", help="Git repository root")
    sub = parser.add_subparsers(dest="command", required=True)

    create = sub.add_parser("create")
    create.add_argument("--slug", required=True)
    create.add_argument("--name", required=True)
    create.add_argument("--goal", required=True)
    create.add_argument("--owner", default=os.environ.get("USER", "codex"))
    create.add_argument("--review-policy", choices=sorted(REVIEW_POLICIES), default="single")
    create.add_argument("--doc-mode", choices=sorted(DOC_MODES))
    create.add_argument("--doc-coverage", choices=sorted(DOC_COVERAGE), default="all")
    create.add_argument("--doc-reason")
    create.add_argument("--doc-target", action="append")
    add_actor_option(create, required=True)
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
    item.add_argument("--module")
    item.add_argument("--change-reason")
    item.add_argument("--verify-kind", required=True, choices=sorted(VERIFY_KINDS))
    add_actor_option(item)
    item.set_defaults(handler=cmd_add_item)

    review = sub.add_parser("review-plan")
    add_plan_option(review)
    add_review_args(review)
    review.set_defaults(handler=cmd_review_plan)

    module = sub.add_parser("upsert-module")
    add_plan_option(module)
    module.add_argument("--id", required=True)
    module.add_argument("--name", required=True)
    module.add_argument("--description", required=True)
    module.add_argument("--path-pattern", action="append")
    module.add_argument("--reason", required=True)
    module.add_argument("--evidence", required=True)
    add_actor_option(module)
    module.set_defaults(handler=cmd_upsert_module)

    dep = sub.add_parser("upsert-dependency")
    add_plan_option(dep)
    dep.add_argument("--module", required=True)
    dep.add_argument("--depends-on", required=True)
    dep.add_argument("--reason", required=True)
    dep.add_argument("--evidence", required=True)
    add_actor_option(dep)
    dep.set_defaults(handler=cmd_upsert_dependency)

    amend = sub.add_parser("propose-amendment")
    add_plan_option(amend)
    amend.add_argument("--kind", required=True, choices=sorted(AMENDMENT_KINDS))
    amend.add_argument("--reason", required=True)
    amend.add_argument("--evidence", required=True)
    amend.add_argument("--operation", required=True, action="append")
    amend.add_argument("--cleanup-item")
    add_actor_option(amend, required=True)
    amend.set_defaults(handler=cmd_propose_amendment)

    amend_review = sub.add_parser("review-amendment")
    add_plan_option(amend_review)
    amend_review.add_argument("--amendment", required=True)
    add_review_args(amend_review)
    amend_review.set_defaults(handler=cmd_review_amendment)

    update = sub.add_parser("update-item")
    add_plan_option(update)
    update.add_argument("--item", required=True)
    update.add_argument("--status", required=True, choices=["in-progress", "failed", "blocked"])
    update.add_argument("--reason")
    add_actor_option(update)
    update.set_defaults(handler=cmd_update_item)

    verify = sub.add_parser("verify")
    add_plan_option(verify)
    verify.add_argument("--item", required=True)
    verify.add_argument("--result", required=True, choices=["pass", "fail", "not-run"])
    verify.add_argument("--evidence", required=True)
    verify.add_argument("--reason")
    verify.add_argument("--verified-by", required=True, choices=sorted(VERIFY_SOURCES))
    add_actor_option(verify)
    verify.set_defaults(handler=cmd_verify)

    checkpoint = sub.add_parser("checkpoint")
    add_plan_option(checkpoint)
    checkpoint.add_argument("--item")
    checkpoint.add_argument("--reason", required=True)
    checkpoint.add_argument("--next-action", required=True)
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
    resume = sub.add_parser("resume")
    add_plan_option(resume)
    resume.set_defaults(handler=cmd_resume)
    refresh = sub.add_parser("refresh-status")
    add_plan_option(refresh)
    refresh.set_defaults(handler=cmd_refresh_status)
    install = sub.add_parser("install-dashboard")
    install.set_defaults(handler=cmd_install_dashboard)
    serve = sub.add_parser("serve")
    serve.add_argument("--host", default="127.0.0.1")
    serve.add_argument("--port", type=int, default=DEFAULT_SERVE_PORT)
    serve.add_argument("--no-open", action="store_true", help="do not open a browser automatically")
    serve.set_defaults(handler=cmd_serve)
    migrate = sub.add_parser("migrate-store")
    migrate.add_argument("--dry-run", action="store_true")
    migrate.set_defaults(handler=cmd_migrate_store)
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    root = Path(args.root).expanduser().resolve()
    try:
        reject_root_inside_store(root)
        select_store(root, args.command)
        if st._USING_LEGACY and args.command not in READ_ONLY_COMMANDS | {"migrate-store"}:
            die("legacy plans/ is read-only; migrate it before mutation")
        needs_lock = args.command in MUTATING_COMMANDS and not (args.command == "migrate-store" and args.dry_run)
        if needs_lock:
            with repository_lock(root):
                result = args.handler(args, root)
        else:
            result = args.handler(args, root)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except PlanError as exc:
        print(f"planctl: {exc}", file=sys.stderr)
        return 2
    except (KeyError, TypeError, ValueError) as exc:
        print(f"planctl: malformed plan data or command payload: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
