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


def _git_env() -> dict[str, str]:
    # a scan must never take index.lock in someone's working tree
    return {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}


def run_git(args: list[str], cwd: Path) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=cwd,
        capture_output=True,
        encoding="utf-8",
        env=_git_env(),
        check=False,
    )
    if result.returncode != 0:
        raise GitError(args, cwd, result.returncode, result.stderr)
    return result.stdout


def common_dir(path: Path) -> Path:
    out = run_git(["rev-parse", "--path-format=absolute", "--git-common-dir"], path)
    return Path(out.strip()).resolve()


def list_worktrees(path: Path) -> list[WorktreeEntry]:
    return parse_worktree_list(run_git(["worktree", "list", "--porcelain"], path))


def parse_worktree_list(output: str) -> list[WorktreeEntry]:
    blocks = [block for block in output.strip().split("\n\n") if block.strip()]
    return [_parse_worktree_block(block, is_main=i == 0) for i, block in enumerate(blocks)]


def _parse_worktree_block(block: str, is_main: bool) -> WorktreeEntry:
    fields: dict[str, str] = {}
    for line in block.splitlines():
        key, _, value = line.partition(" ")
        fields[key] = value
    branch = fields.get("branch")
    return WorktreeEntry(
        path=Path(fields["worktree"]),
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
