from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from git_janitor import fs, git
from git_janitor.models import Removal, Status, Verdict


def clean(verdicts: list[Verdict], forced: frozenset[Path]) -> list[Removal]:
    safe = [v for v in verdicts if v.status is Status.SAFE and not _is_main(v)]
    zombies = [v for v in verdicts if v.status is Status.ZOMBIE]
    repos = sorted({v.repository for v in zombies})
    with ThreadPoolExecutor() as pool:
        removals = list(pool.map(lambda v: _remove(v, v.path.resolve() in forced), safe))
        prune_errors = dict(zip(repos, pool.map(_prune, repos), strict=True))
    return removals + [Removal(v.path, prune_errors[v.repository]) for v in zombies]


def _is_main(verdict: Verdict) -> bool:
    return verdict.path.resolve() == verdict.repository.resolve()


def _remove(verdict: Verdict, force: bool) -> Removal:
    if fs.is_held_open(verdict.path):
        return Removal(verdict.path, "in use by another program, skipped")
    try:
        git.remove_worktree(verdict.repository, verdict.path, force)
    except git.GitError as error:
        return Removal(verdict.path, error.stderr.strip() or str(error))
    return Removal(verdict.path)


def _prune(repository: Path) -> str | None:
    try:
        git.prune_worktrees(repository)
    except git.GitError as error:
        return error.stderr.strip() or str(error)
    return None
