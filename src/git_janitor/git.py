import os
import subprocess
from datetime import UTC, datetime
from pathlib import Path

from git_janitor.models import WorktreeEntry


class GitError(Exception):
    def __init__(self, args: list[str], cwd: Path, returncode: int, stderr: str) -> None:
        super().__init__(f"git {' '.join(args)} failed in {cwd} ({returncode}): {stderr.strip()}")
        self.returncode = returncode
        self.stderr = stderr


def _env_without_optional_locks() -> dict[str, str]:
    return {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}


def _run(args: list[str], cwd: Path, stdin: str | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=cwd,
        input=stdin,
        capture_output=True,
        encoding="utf-8",
        errors="surrogateescape",
        env=_env_without_optional_locks(),
        check=False,
    )


def run_git(args: list[str], cwd: Path, stdin: str | None = None) -> str:
    result = _run(args, cwd, stdin)
    if result.returncode != 0:
        raise GitError(args, cwd, result.returncode, result.stderr)
    return result.stdout


def common_dir(path: Path) -> Path:
    out = run_git(["rev-parse", "--path-format=absolute", "--git-common-dir"], path)
    return Path(out.strip()).resolve()


def git_dir(path: Path) -> Path:
    return Path(run_git(["rev-parse", "--absolute-git-dir"], path).strip())


def list_worktrees(path: Path) -> list[WorktreeEntry]:
    return parse_worktree_list(run_git(["worktree", "list", "--porcelain"], path))


def parse_worktree_list(output: str) -> list[WorktreeEntry]:
    blocks = [block for block in output.strip().split("\n\n") if block.strip()]
    if not blocks:
        return []
    repository = Path(_fields(blocks[0])["worktree"])
    return [_entry(_fields(block), repository, is_main=i == 0) for i, block in enumerate(blocks)]


def _fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block.splitlines():
        key, _, value = line.partition(" ")
        fields[key] = value
    return fields


def _entry(fields: dict[str, str], repository: Path, is_main: bool) -> WorktreeEntry:
    branch = fields.get("branch")
    return WorktreeEntry(
        path=Path(fields["worktree"]),
        repository=repository,
        head=fields.get("HEAD"),
        branch=branch.removeprefix("refs/heads/") if branch else None,
        is_main=is_main,
        detached="detached" in fields,
        bare="bare" in fields,
        locked="locked" in fields,
        prunable="prunable" in fields,
    )


def changed_file_count(path: Path) -> int:
    out = run_git(["status", "--porcelain=v2"], path)
    return sum(1 for line in out.splitlines() if line and not line.startswith("#"))


def last_commit_time(path: Path) -> datetime | None:
    try:
        out = run_git(["log", "-1", "--format=%ct"], path)
    except GitError:
        return None
    stamp = out.strip()
    return datetime.fromtimestamp(int(stamp), tz=UTC) if stamp else None


def default_target(path: Path) -> str | None:
    result = _run(["symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD"], path)
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def ref_exists(path: Path, ref: str) -> bool:
    return _run(["rev-parse", "--verify", "-q", f"{ref}^{{commit}}"], path).returncode == 0


def stash_branches(path: Path) -> list[str]:
    out = run_git(["stash", "list", "--format=%gs"], path)
    return parse_stash_branches(out)


def parse_stash_branches(output: str) -> list[str]:
    branches = []
    for subject in output.splitlines():
        head, _, _ = subject.partition(":")
        for prefix in ("WIP on ", "On "):
            if head.startswith(prefix):
                branches.append(head.removeprefix(prefix))
                break
    return branches


def unpushed_count(path: Path) -> int:
    return int(run_git(["rev-list", "--count", "HEAD", "--not", "--remotes"], path).strip())


def cherry_marks(path: Path, target: str) -> list[str]:
    out = run_git(["cherry", target, "HEAD"], path)
    return [line[0] for line in out.splitlines() if line]


def branch_patch_id(path: Path, target: str) -> str | None:
    diff = run_git(["diff", "--no-ext-diff", "--no-color", f"{target}...HEAD"], path)
    ids = parse_patch_ids(run_git(["patch-id", "--stable"], path, stdin=diff))
    return next(iter(ids), None)


def target_patch_ids(path: Path, target: str) -> frozenset[str]:
    log = run_git(
        ["log", "-p", "--no-merges", "--no-ext-diff", "--no-color", f"HEAD..{target}"], path
    )
    return frozenset(parse_patch_ids(run_git(["patch-id", "--stable"], path, stdin=log)))


def parse_patch_ids(output: str) -> list[str]:
    return [line.split()[0] for line in output.splitlines() if line.strip()]


def remove_worktree(repository: Path, worktree: Path, force: bool) -> None:
    run_git(["worktree", "remove", *(["--force"] if force else []), str(worktree)], repository)


def prune_worktrees(repository: Path) -> None:
    run_git(["worktree", "prune"], repository)
