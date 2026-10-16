import os
from collections.abc import Iterator
from pathlib import Path

SKIP_DIRS = frozenset({"node_modules", ".venv", "venv", "__pycache__", "bin", "obj"})


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
