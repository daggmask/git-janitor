from pathlib import Path

from git_janitor import fs, git
from git_janitor.analysis import classify
from git_janitor.models import Verdict, WorktreeEntry, WorktreeFacts


def scan(root: Path, max_depth: int) -> list[Verdict]:
    entries = _unique_worktrees(fs.find_repositories(root, max_depth))
    return [classify(_facts(entry)) for entry in entries]


def _unique_worktrees(repositories: list[Path]) -> list[WorktreeEntry]:
    seen_common_dirs: set[Path] = set()
    entries: list[WorktreeEntry] = []
    for repo in repositories:
        common = git.common_dir(repo)
        if common in seen_common_dirs:
            continue
        seen_common_dirs.add(common)
        entries.extend(entry for entry in git.list_worktrees(repo) if not entry.bare)
    return entries


def _facts(entry: WorktreeEntry) -> WorktreeFacts:
    exists = fs.folder_exists(entry.path)
    return WorktreeFacts(
        entry=entry,
        exists=exists,
        changed_files=git.changed_file_count(entry.path) if exists else 0,
        last_commit_at=git.last_commit_time(entry.path) if exists else None,
    )
