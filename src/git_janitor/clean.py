from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from git_janitor import fs, git
from git_janitor.models import RemovalResult, Status, Verdict


def remove_safe_worktrees(
    verdicts: list[Verdict], forced_paths: frozenset[Path]
) -> list[RemovalResult]:
    safe_worktrees = [
        verdict
        for verdict in verdicts
        if verdict.status is Status.SAFE and not _is_main_worktree(verdict)
    ]
    zombies = [verdict for verdict in verdicts if verdict.status is Status.ZOMBIE]
    repositories_with_zombies = sorted({zombie.main_worktree_path for zombie in zombies})
    with ThreadPoolExecutor() as pool:
        removals = list(
            pool.map(
                lambda verdict: _remove_worktree(verdict, verdict.path.resolve() in forced_paths),
                safe_worktrees,
            )
        )
        prune_errors = pool.map(_prune_zombies, repositories_with_zombies)
        prune_error_by_repository = dict(zip(repositories_with_zombies, prune_errors, strict=True))
    prunes = [
        RemovalResult(zombie.path, prune_error_by_repository[zombie.main_worktree_path])
        for zombie in zombies
    ]
    return removals + prunes


def _is_main_worktree(verdict: Verdict) -> bool:
    return verdict.path.resolve() == verdict.main_worktree_path.resolve()


def _remove_worktree(verdict: Verdict, force: bool) -> RemovalResult:
    if fs.is_in_use_by_another_program(verdict.path):
        return RemovalResult(verdict.path, "in use by another program, skipped")
    try:
        git.remove_worktree(verdict.main_worktree_path, verdict.path, force)
    except git.GitError as error:
        return RemovalResult(verdict.path, error.stderr.strip() or str(error))
    return RemovalResult(verdict.path)


def _prune_zombies(main_worktree_path: Path) -> str | None:
    try:
        git.prune_worktrees(main_worktree_path)
    except git.GitError as error:
        return error.stderr.strip() or str(error)
    return None
