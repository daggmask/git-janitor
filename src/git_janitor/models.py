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
    repository: Path
    head: str | None
    branch: str | None
    is_main: bool
    detached: bool = False
    bare: bool = False
    locked: bool = False
    prunable: bool = False


@dataclass(frozen=True)
class TargetCheck:
    target: str
    commits: int
    unmerged: int
    branch_patch_id: str | None = None
    target_patch_ids: frozenset[str] = frozenset()


@dataclass(frozen=True)
class WorktreeFacts:
    entry: WorktreeEntry
    exists: bool
    changed_files: int = 0
    last_commit_at: datetime | None = None
    last_used_at: datetime | None = None
    holds_cwd: bool = False
    stashes: int = 0
    unpushed: int = 0
    targets: tuple[TargetCheck, ...] = ()
    forced: bool = False


@dataclass(frozen=True)
class Verdict:
    path: Path
    repository: Path
    branch: str | None
    status: Status
    reason: str
    last_commit_at: datetime | None


@dataclass(frozen=True)
class Removal:
    path: Path
    error: str | None = None
