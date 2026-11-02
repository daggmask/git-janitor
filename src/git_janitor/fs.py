import os
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

FOLDERS_NOT_SEARCHED = frozenset({"node_modules", ".venv", "venv", "__pycache__", "bin", "obj"})
GIT_FILES_TOUCHED_ON_USE = ("HEAD", "index", "logs/HEAD", "ORIG_HEAD")


def folder_exists(path: Path) -> bool:
    return path.is_dir()


def find_git_folders(root: Path, max_depth: int) -> list[Path]:
    return sorted(_walk_for_git_folders(root, max_depth))


def _walk_for_git_folders(folder: Path, levels_left: int) -> Iterator[Path]:
    if (folder / ".git").exists():
        yield folder
    if levels_left == 0:
        return
    try:
        subfolders = [entry for entry in os.scandir(folder) if _is_folder_to_search(entry)]
    except OSError:
        return
    for subfolder in subfolders:
        yield from _walk_for_git_folders(Path(subfolder.path), levels_left - 1)


def _is_folder_to_search(entry: os.DirEntry[str]) -> bool:
    if entry.name in FOLDERS_NOT_SEARCHED or entry.name.startswith("."):
        return False
    try:
        return entry.is_dir(follow_symlinks=False)
    except OSError:
        return False


def last_used_time(git_dir: Path) -> datetime | None:
    modified_times = [_modified_time(git_dir / name) for name in GIT_FILES_TOUCHED_ON_USE]
    known_times = [time for time in modified_times if time is not None]
    return max(known_times) if known_times else None


def _modified_time(path: Path) -> datetime | None:
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=UTC)
    except OSError:
        return None


def is_inside_folder(path: Path, folder: Path) -> bool:
    return path.resolve().is_relative_to(folder.resolve())


def check_folder_free_by_renaming(folder: Path) -> str | None:
    temporary_path = folder.with_name(f"{folder.name}.janitor-{os.getpid()}")
    try:
        folder.rename(temporary_path)
    except OSError:
        return "in use by another program, skipped"
    try:
        temporary_path.rename(folder)
    except OSError:
        return f"moved to {temporary_path} and could not move it back"
    return None
