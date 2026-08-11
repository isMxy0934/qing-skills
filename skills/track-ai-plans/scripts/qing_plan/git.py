"""Git observations, baselines, and file snapshots."""

from __future__ import annotations

from .storage import *


def run_git(root: Path, args: list[str]) -> subprocess.CompletedProcess:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def require_git_root(root: Path) -> None:
    result = run_git(root, ["rev-parse", "--show-toplevel"])
    if result.returncode != 0:
        die("ROOT must be a Git repository with an initial commit")
    reported = Path(result.stdout.strip()).resolve()
    if reported != root.resolve():
        die(f"--root must be Git top-level: {reported}")


def git_head(root: Path) -> str:
    result = run_git(root, ["rev-parse", "HEAD"])
    if result.returncode != 0:
        die("repository needs an initial commit")
    return result.stdout.strip()


def git_branch(root: Path) -> str:
    result = run_git(root, ["branch", "--show-current"])
    return result.stdout.strip() if result.returncode == 0 else ""


def git_is_ancestor(root: Path, ancestor: str, descendant: str) -> bool:
    # A checkpoint's headCommit is recorded before the checkpoint's own JSON is committed,
    # so the very next legitimate commit (checkpoint + code together) always moves HEAD past
    # it. Ancestry, not equality, is what tells apart normal forward progress from a real
    # divergence (reset, rebase, force-push, or resuming on a stale checkout).
    result = run_git(root, ["merge-base", "--is-ancestor", ancestor, descendant])
    return result.returncode == 0


def is_tool_storage_path(path: str) -> bool:
    return (
        path == "plans" or path.startswith("plans/") or path == "qing-plans" or
        path.startswith("qing-plans/") or path.startswith(".qing-plans-migrate-") or
        path == "plan-dashboard.html"
    )


def raw_dirty_paths(root: Path) -> list[str]:
    result = run_git(root, ["status", "--porcelain=v1", "--untracked-files=all"])
    if result.returncode != 0:
        die(f"git status failed: {result.stderr.strip()}")
    paths = (line[3:].split(" -> ", 1)[-1] for line in result.stdout.splitlines())
    return sorted({path for path in paths if path})


def git_dirty_paths(root: Path) -> list[str]:
    return [path for path in raw_dirty_paths(root) if not is_tool_storage_path(path)]


def migration_dirty_paths(root: Path) -> list[str]:
    """Require a fully recoverable pre-migration tree, excluding only our lock."""
    return [path for path in raw_dirty_paths(root) if path != "plans/.planctl.lock"]


def handoff_dirty_paths(root: Path) -> list[str]:
    """Return every uncommitted path that another computer would not receive."""
    ignored = {"plans/.planctl.lock", "qing-plans/.planctl.lock"}
    return [path for path in raw_dirty_paths(root) if path not in ignored]


def git_push_state(root: Path) -> dict:
    upstream = run_git(root, ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"])
    if upstream.returncode != 0:
        return {"status": "no-upstream", "upstream": None, "ahead": None, "behind": None}
    name = upstream.stdout.strip()
    counts = run_git(root, ["rev-list", "--left-right", "--count", f"{name}...HEAD"])
    if counts.returncode != 0:
        return {"status": "unknown", "upstream": name, "ahead": None, "behind": None}
    behind, ahead = (int(value) for value in counts.stdout.split())
    return {"status": "pushed" if ahead == 0 else "unpushed", "upstream": name,
            "ahead": ahead, "behind": behind}


def capture_activation_baseline(root: Path) -> str:
    require_git_root(root)
    dirty = git_dirty_paths(root)
    if dirty:
        die("cannot activate with dirty files outside qing-plans/: " + ", ".join(dirty))
    return git_head(root)


def parse_name_status(output: str) -> dict[str, dict]:
    changes = {}
    for line in output.splitlines():
        parts = line.split("\t")
        if not parts or not parts[0]:
            continue
        code = parts[0]
        if code.startswith("R") and len(parts) >= 3:
            changes[parts[2]] = {"action": "move", "from": parts[1]}
        elif code.startswith("C") and len(parts) >= 3:
            changes[parts[2]] = {"action": "create", "from": parts[1]}
        elif len(parts) >= 2:
            changes[parts[1]] = {"action": {"A": "create", "M": "modify", "D": "delete"}.get(code[0], "modify"), "from": None}
    return changes


def git_change_map(root: Path, baseline: str | None) -> dict[str, dict]:
    if not baseline:
        return {}
    require_git_root(root)
    result = run_git(root, ["diff", "--find-renames", "--name-status", baseline])
    if result.returncode != 0:
        die(f"git diff failed for {baseline}: {result.stderr.strip()}")
    changes = parse_name_status(result.stdout)
    untracked = run_git(root, ["ls-files", "--others", "--exclude-standard"])
    if untracked.returncode != 0:
        die(f"untracked scan failed: {untracked.stderr.strip()}")
    for path in untracked.stdout.splitlines():
        if path:
            changes[path] = {"action": "create", "from": None}
    return {path: info for path, info in changes.items() if not is_tool_storage_path(path)}


def sha256_file(path: Path) -> str | None:
    if not path.is_file():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def path_snapshot(root: Path, path: str) -> dict:
    target = root / path
    return {"path": path, "exists": target.exists(), "sha256": sha256_file(target), "capturedAt": now()}
