from collections.abc import Iterable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from git_janitor import fs, git
from git_janitor.analysis import classify
from git_janitor.models import TargetCheck, Verdict, WorktreeEntry, WorktreeFacts


@dataclass(frozen=True)
class ScanOptions:
    targets: tuple[str, ...] = ()
    idle_days: int = 3
    forced: frozenset[Path] = frozenset()
    cwd: Path = Path(".")


@dataclass(frozen=True)
class _Repository:
    worktrees: tuple[WorktreeEntry, ...]
    targets: tuple[str, ...]
    stash_branches: tuple[str, ...]


def scan(root: Path, max_depth: int, options: ScanOptions) -> list[Verdict]:
    repositories = fs.find_repositories(root, max_depth)
    now = datetime.now(UTC)
    with ThreadPoolExecutor() as pool:
        common_dirs = list(pool.map(git.common_dir, repositories))
        unique = _one_per_repository(zip(repositories, common_dirs, strict=True))
        repos = list(pool.map(lambda path: _repository(path, options.targets), unique))
        jobs = [(entry, repo) for repo in repos for entry in repo.worktrees]
        facts = pool.map(lambda job: _facts(job[0], job[1], options), jobs)
        return [classify(f, now, options.idle_days) for f in facts]


def _one_per_repository(repositories: Iterable[tuple[Path, Path]]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for repo, common in repositories:
        if common not in seen:
            seen.add(common)
            unique.append(repo)
    return unique


def _repository(path: Path, wanted_targets: tuple[str, ...]) -> _Repository:
    worktrees = tuple(entry for entry in git.list_worktrees(path) if not entry.bare)
    return _Repository(
        worktrees=worktrees,
        targets=_targets(path, wanted_targets),
        stash_branches=tuple(git.stash_branches(path)),
    )


def _targets(path: Path, wanted: tuple[str, ...]) -> tuple[str, ...]:
    if wanted:
        return tuple(target for target in wanted if git.ref_exists(path, target))
    default = git.default_target(path)
    return (default,) if default else ()


def _facts(entry: WorktreeEntry, repo: _Repository, options: ScanOptions) -> WorktreeFacts:
    exists = fs.folder_exists(entry.path)
    if entry.is_main or not exists:
        return WorktreeFacts(entry=entry, exists=exists)
    path = entry.path
    return WorktreeFacts(
        entry=entry,
        exists=True,
        changed_files=git.changed_file_count(path),
        last_commit_at=git.last_commit_time(path),
        last_used_at=fs.last_activity(git.git_dir(path)),
        holds_cwd=fs.is_inside(options.cwd, path),
        stashes=_stash_count(entry, repo),
        unpushed=git.unpushed_count(path),
        targets=tuple(_target_check(path, target) for target in repo.targets),
        forced=path.resolve() in options.forced,
    )


def _stash_count(entry: WorktreeEntry, repo: _Repository) -> int:
    branch = entry.branch or "(no branch)"
    return repo.stash_branches.count(branch)


def _target_check(path: Path, target: str) -> TargetCheck:
    marks = git.cherry_marks(path, target)
    unmerged = marks.count("+")
    if unmerged == 0:
        return TargetCheck(target=target, commits=len(marks), unmerged=0)
    return TargetCheck(
        target=target,
        commits=len(marks),
        unmerged=unmerged,
        branch_patch_id=git.branch_patch_id(path, target),
        target_patch_ids=git.target_patch_ids(path, target),
    )
