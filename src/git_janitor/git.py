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


TURN_OFF_FSMONITOR_AND_SIGNATURE_CHECKS = (
    "-c",
    "core.fsmonitor=false",
    "-c",
    "log.showSignature=false",
)


def _noninteractive_git_env() -> dict[str, str]:
    return {**os.environ, "GIT_OPTIONAL_LOCKS": "0", "GIT_TERMINAL_PROMPT": "0"}


def _run_git_allowing_failure(
    args: list[str], cwd: Path, stdin: str | None = None
) -> subprocess.CompletedProcess[str]:
    try:
        return subprocess.run(
            ["git", *TURN_OFF_FSMONITOR_AND_SIGNATURE_CHECKS, *args],
            cwd=cwd,
            input=stdin,
            capture_output=True,
            encoding="utf-8",
            errors="surrogateescape",
            env=_noninteractive_git_env(),
            check=False,
        )
    except OSError as error:
        raise GitError(args, cwd, -1, str(error)) from error


def _run_git(args: list[str], cwd: Path, stdin: str | None = None) -> str:
    result = _run_git_allowing_failure(args, cwd, stdin)
    if result.returncode != 0:
        raise GitError(args, cwd, result.returncode, result.stderr)
    return result.stdout


def common_git_dir(path: Path) -> Path:
    output = _run_git(["rev-parse", "--path-format=absolute", "--git-common-dir"], path)
    return Path(output.strip()).resolve()


def worktree_git_dir(path: Path) -> Path:
    return Path(_run_git(["rev-parse", "--absolute-git-dir"], path).strip())


def list_worktrees(path: Path) -> list[WorktreeEntry]:
    return parse_worktree_list(_run_git(["worktree", "list", "--porcelain"], path))


def parse_worktree_list(output: str) -> list[WorktreeEntry]:
    worktree_blocks = [block for block in output.strip().split("\n\n") if block.strip()]
    if not worktree_blocks:
        return []
    main_worktree_path = Path(_porcelain_fields(worktree_blocks[0])["worktree"])
    return [
        _worktree_entry(_porcelain_fields(block), main_worktree_path, is_main=index == 0)
        for index, block in enumerate(worktree_blocks)
    ]


def _porcelain_fields(block: str) -> dict[str, str]:
    fields: dict[str, str] = {}
    for line in block.splitlines():
        key, _, value = line.partition(" ")
        fields[key] = value
    return fields


def _worktree_entry(
    fields: dict[str, str], main_worktree_path: Path, is_main: bool
) -> WorktreeEntry:
    branch_ref = fields.get("branch")
    return WorktreeEntry(
        path=Path(fields["worktree"]),
        main_worktree_path=main_worktree_path,
        head_commit=fields.get("HEAD"),
        branch=branch_ref.removeprefix("refs/heads/") if branch_ref else None,
        is_main=is_main,
        is_detached="detached" in fields,
        is_bare="bare" in fields,
        is_locked="locked" in fields,
        is_prunable="prunable" in fields,
    )


def changed_file_count(path: Path) -> int:
    status_output = _run_git(["status", "--porcelain=v2"], path)
    return sum(1 for line in status_output.splitlines() if line and not line.startswith("#"))


def last_commit_time(path: Path) -> datetime | None:
    try:
        output = _run_git(["log", "-1", "--format=%ct"], path)
    except GitError:
        return None
    unix_seconds = output.strip()
    return datetime.fromtimestamp(int(unix_seconds), tz=UTC) if unix_seconds else None


def origin_default_branch(path: Path) -> str | None:
    result = _run_git_allowing_failure(
        ["symbolic-ref", "-q", "--short", "refs/remotes/origin/HEAD"], path
    )
    if result.returncode != 0:
        return None
    return result.stdout.strip() or None


def ref_exists(path: Path, ref: str) -> bool:
    result = _run_git_allowing_failure(["rev-parse", "--verify", "-q", f"{ref}^{{commit}}"], path)
    return result.returncode == 0


def stash_branch_names(path: Path) -> list[str]:
    return parse_stash_branch_names(_run_git(["stash", "list", "--format=%gs"], path))


def parse_stash_branch_names(output: str) -> list[str]:
    branch_names = []
    for stash_subject in output.splitlines():
        stash_label, _, _ = stash_subject.partition(":")
        for prefix in ("WIP on ", "On "):
            if stash_label.startswith(prefix):
                branch_names.append(stash_label.removeprefix(prefix))
                break
    return branch_names


def unpushed_commit_count(path: Path) -> int:
    output = _run_git(["rev-list", "--count", "HEAD", "--not", "--remotes"], path)
    return int(output.strip())


def cherry_marks(path: Path, target_branch: str) -> list[str]:
    output = _run_git(["cherry", target_branch, "HEAD"], path)
    return [line[0] for line in output.splitlines() if line]


def branch_diff_patch_id(path: Path, target_branch: str) -> str | None:
    branch_diff = _run_git(
        ["diff", "--no-ext-diff", "--no-textconv", "--no-color", f"{target_branch}...HEAD"], path
    )
    patch_ids = parse_patch_ids(_run_git(["patch-id", "--stable"], path, stdin=branch_diff))
    return next(iter(patch_ids), None)


def target_commit_patch_ids(path: Path, target_branch: str) -> frozenset[str]:
    target_commits = _run_git(
        [
            "log",
            "-p",
            "--no-merges",
            "--no-ext-diff",
            "--no-textconv",
            "--no-color",
            f"HEAD..{target_branch}",
        ],
        path,
    )
    patch_ids = parse_patch_ids(_run_git(["patch-id", "--stable"], path, stdin=target_commits))
    return frozenset(patch_ids)


def parse_patch_ids(output: str) -> list[str]:
    return [line.split()[0] for line in output.splitlines() if line.strip()]


def remove_worktree(main_worktree_path: Path, worktree_path: Path, force: bool) -> None:
    force_flag = ["--force"] if force else []
    _run_git(["worktree", "remove", *force_flag, str(worktree_path)], main_worktree_path)


def prune_worktrees(main_worktree_path: Path) -> None:
    _run_git(["worktree", "prune"], main_worktree_path)
