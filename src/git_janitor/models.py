from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from pathlib import Path


class Status(Enum):
    ZOMBIE = "zombie"
    SAFE = "safe"
    KEEP = "keep"


@dataclass(frozen=True)
class WorktreeEntry:
    path: Path
    main_worktree_path: Path
    head_commit: str | None
    branch: str | None
    is_main: bool
    is_detached: bool = False
    is_bare: bool = False
    is_locked: bool = False
    is_prunable: bool = False


@dataclass(frozen=True)
class MergeCheck:
    target_branch: str
    commits_ahead_of_target: int
    commits_without_patch_in_target: int
    branch_diff_patch_id: str | None = None
    target_commit_patch_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class WorktreeFacts:
    worktree: WorktreeEntry
    folder_exists: bool
    changed_file_count: int = 0
    last_commit_at: datetime | None = None
    last_used_at: datetime | None = None
    contains_current_directory: bool = False
    stash_count: int = 0
    unpushed_commit_count: int = 0
    merge_checks: tuple[MergeCheck, ...] = ()
    is_forced: bool = False
    git_failure: str | None = None


@dataclass(frozen=True)
class Verdict:
    path: Path
    main_worktree_path: Path
    branch: str | None
    status: Status
    reason: str
    last_commit_at: datetime | None
    is_forced: bool


@dataclass(frozen=True)
class RemovalResult:
    path: Path
    error: str | None = None
