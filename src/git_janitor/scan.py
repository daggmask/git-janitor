from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from git_janitor import fs, git
from git_janitor.analysis import classify_worktree
from git_janitor.models import MergeCheck, Verdict, WorktreeEntry, WorktreeFacts


@dataclass(frozen=True)
class ScanOptions:
    target_branches: tuple[str, ...] = ()
    idle_days: int = 3
    forced_paths: frozenset[Path] = frozenset()
    current_directory: Path = Path(".")


@dataclass(frozen=True)
class _RepositoryInfo:
    worktrees: tuple[WorktreeEntry, ...]
    target_branches: tuple[str, ...]
    stash_branch_names: tuple[str, ...]
    load_failure: str | None = None


def scan_worktrees(root: Path, max_depth: int, options: ScanOptions) -> list[Verdict]:
    git_folders = fs.find_git_folders(root, max_depth)
    now = datetime.now(UTC)
    with ThreadPoolExecutor() as pool:
        common_git_dirs = list(pool.map(_common_git_dir_or_folder, git_folders))
        one_folder_per_repository = _first_folder_per_repository(
            zip(git_folders, common_git_dirs, strict=True)
        )
        repositories = list(
            pool.map(
                lambda folder: _load_repository(folder, options.target_branches),
                one_folder_per_repository,
            )
        )
        worktrees_with_repository = [
            (worktree, repository)
            for repository in repositories
            for worktree in repository.worktrees
        ]
        all_facts = pool.map(
            lambda pair: _gather_worktree_facts(pair[0], pair[1], options),
            worktrees_with_repository,
        )
        return [classify_worktree(facts, now, options.idle_days) for facts in all_facts]


def _common_git_dir_or_folder(folder: Path) -> Path:
    try:
        return git.common_git_dir(folder)
    except git.GitError:
        return folder


def _first_folder_per_repository(
    folders_with_common_git_dir: Iterable[tuple[Path, Path]],
) -> list[Path]:
    seen_common_git_dirs: set[Path] = set()
    first_folders: list[Path] = []
    for folder, common_git_dir in folders_with_common_git_dir:
        if common_git_dir not in seen_common_git_dirs:
            seen_common_git_dirs.add(common_git_dir)
            first_folders.append(folder)
    return first_folders


def _load_repository(folder: Path, requested_targets: tuple[str, ...]) -> _RepositoryInfo:
    try:
        worktrees = tuple(
            worktree for worktree in git.list_worktrees(folder) if not worktree.is_bare
        )
    except git.GitError as error:
        return _failed_repository((_unreadable_folder(folder),), error)
    try:
        return _RepositoryInfo(
            worktrees=worktrees,
            target_branches=_existing_target_branches(folder, requested_targets),
            stash_branch_names=tuple(git.stash_branch_names(folder)),
        )
    except git.GitError as error:
        return _failed_repository(worktrees, error)


def _failed_repository(
    worktrees: tuple[WorktreeEntry, ...], error: git.GitError
) -> _RepositoryInfo:
    return _RepositoryInfo(
        worktrees=worktrees,
        target_branches=(),
        stash_branch_names=(),
        load_failure=_git_failure_reason(error),
    )


def _unreadable_folder(folder: Path) -> WorktreeEntry:
    return WorktreeEntry(
        path=folder, main_worktree_path=folder, head_commit=None, branch=None, is_main=False
    )


def _git_failure_reason(error: git.GitError) -> str:
    stderr_lines = error.stderr.strip().splitlines()
    return stderr_lines[-1] if stderr_lines else str(error)


def _existing_target_branches(folder: Path, requested: tuple[str, ...]) -> tuple[str, ...]:
    if requested:
        return tuple(branch for branch in requested if git.ref_exists(folder, branch))
    default_branch = git.origin_default_branch(folder)
    return (default_branch,) if default_branch else ()


def _gather_worktree_facts(
    worktree: WorktreeEntry, repository: _RepositoryInfo, options: ScanOptions
) -> WorktreeFacts:
    if repository.load_failure:
        return WorktreeFacts(
            worktree=worktree, folder_exists=True, git_failure=repository.load_failure
        )
    folder_exists = fs.folder_exists(worktree.path)
    if worktree.is_main or not folder_exists:
        return WorktreeFacts(worktree=worktree, folder_exists=folder_exists)
    try:
        return _read_worktree_facts(worktree, repository, options)
    except git.GitError as error:
        return WorktreeFacts(
            worktree=worktree, folder_exists=True, git_failure=_git_failure_reason(error)
        )


def _read_worktree_facts(
    worktree: WorktreeEntry, repository: _RepositoryInfo, options: ScanOptions
) -> WorktreeFacts:
    path = worktree.path
    return WorktreeFacts(
        worktree=worktree,
        folder_exists=True,
        changed_file_count=git.changed_file_count(path),
        last_commit_at=git.last_commit_time(path),
        last_used_at=fs.last_used_time(git.worktree_git_dir(path)),
        contains_current_directory=fs.is_inside_folder(options.current_directory, path),
        stash_count=_stash_count_on_branch(worktree, repository),
        unpushed_commit_count=git.unpushed_commit_count(path),
        merge_checks=tuple(
            _check_merged_into(path, branch) for branch in repository.target_branches
        ),
        is_forced=path.resolve() in options.forced_paths,
    )


def _stash_count_on_branch(worktree: WorktreeEntry, repository: _RepositoryInfo) -> int:
    stash_label = worktree.branch or "(no branch)"
    return repository.stash_branch_names.count(stash_label)


def _check_merged_into(path: Path, target_branch: str) -> MergeCheck:
    cherry_marks = git.cherry_marks(path, target_branch)
    commits_not_in_target = cherry_marks.count("+")
    if commits_not_in_target == 0:
        return MergeCheck(target_branch, commits_ahead=len(cherry_marks), commits_not_in_target=0)
    return MergeCheck(
        target_branch=target_branch,
        commits_ahead=len(cherry_marks),
        commits_not_in_target=commits_not_in_target,
        branch_diff_patch_id=git.branch_diff_patch_id(path, target_branch),
        target_commit_patch_ids=git.target_commit_patch_ids(path, target_branch),
    )
