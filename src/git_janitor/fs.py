import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

SKIP_DIRS = frozenset({"node_modules", ".venv", "venv", "__pycache__", "bin", "obj"})
ACTIVITY_FILES = ("HEAD", "index", "logs/HEAD", "ORIG_HEAD")


def folder_exists(path: Path) -> bool:
    return path.is_dir()


def find_repositories(root: Path, max_depth: int) -> list[Path]:
    return sorted(_walk(root, max_depth))


def _walk(folder: Path, depth_left: int) -> Iterator[Path]:
    if (folder / ".git").exists():
        yield folder
    if depth_left == 0:
        return
    try:
        children = [entry for entry in os.scandir(folder) if _should_descend(entry)]
    except OSError:
        return
    for child in children:
        yield from _walk(Path(child.path), depth_left - 1)


def _should_descend(entry: os.DirEntry[str]) -> bool:
    if entry.name in SKIP_DIRS or entry.name.startswith("."):
        return False
    try:
        return entry.is_dir(follow_symlinks=False)
    except OSError:
        return False


def last_activity(git_dir: Path) -> datetime | None:
    stamps = [_mtime(git_dir / name) for name in ACTIVITY_FILES]
    known = [stamp for stamp in stamps if stamp is not None]
    return max(known) if known else None


def _mtime(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        return None


def is_inside(path: Path, folder: Path) -> bool:
    return path.resolve().is_relative_to(folder.resolve())


def is_held_open(folder: Path) -> bool:
    probe = folder.with_name(f"{folder.name}.janitor-{os.getpid()}")
    try:
        folder.rename(probe)
    except OSError:
        return True
    probe.rename(folder)
    return False
