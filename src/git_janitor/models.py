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
    head: str | None
    branch: str | None
    is_main: bool
    detached: bool = False
    bare: bool = False
    locked: bool = False
    prunable: bool = False


@dataclass(frozen=True)
class WorktreeFacts:
    entry: WorktreeEntry
    exists: bool
    changed_files: int
    last_commit_at: datetime | None


@dataclass(frozen=True)
class Verdict:
    path: Path
    branch: str | None
    status: Status
    reason: str
    last_commit_at: datetime | None
