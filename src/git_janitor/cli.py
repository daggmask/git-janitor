from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from git_janitor import __version__
from git_janitor.clean import remove_safe_and_prune_zombies
from git_janitor.git import GitError
from git_janitor.models import RemovalResult, Status, Verdict
from git_janitor.scan import ScanOptions, scan_worktrees

app = typer.Typer(
    help="Find old git worktrees and clones and clean them up safely.",
    no_args_is_help=True,
    add_completion=False,
)

CURRENT_DIRECTORY = Path(".")
STATUS_COLOR = {Status.ZOMBIE: "magenta", Status.SAFE: "green", Status.KEEP: "yellow"}


def _print_version_and_exit(requested: bool) -> None:
    if requested:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=_print_version_and_exit, is_eager=True)
    ] = False,
) -> None:
    pass


@app.command(help="List worktrees under ROOT and say which are safe to delete.")
def scan(
    root: Annotated[
        Path, typer.Argument(exists=True, file_okay=False, resolve_path=True)
    ] = CURRENT_DIRECTORY,
    max_depth: Annotated[int, typer.Option(min=0, help="How deep to look for repositories.")] = 3,
    target: Annotated[
        list[str] | None,
        typer.Option(help="Branch a worktree must be merged into. Default: origin/HEAD."),
    ] = None,
    idle_days: Annotated[
        int, typer.Option(min=0, help="Keep worktrees touched within this many days.")
    ] = 3,
    delete: Annotated[
        bool, typer.Option("--delete", help="Remove safe worktrees and prune zombies.")
    ] = False,
    force: Annotated[
        list[Path] | None,
        typer.Option(help="Treat this worktree as safe even if it is not. Repeat per folder."),
    ] = None,
) -> None:
    forced_paths = frozenset(path.resolve() for path in force or [])
    options = ScanOptions(
        target_branches=tuple(target or []),
        idle_days=idle_days,
        forced_paths=forced_paths,
        current_directory=Path.cwd(),
    )
    try:
        verdicts = scan_worktrees(root, max_depth, options)
    except GitError as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(1) from error
    _exit_if_forced_path_was_not_scanned(forced_paths, verdicts)
    if not verdicts:
        typer.echo(f"No git repositories found under {root}")
        return
    console = Console()
    console.print(_verdict_table(verdicts, root))
    if delete:
        _print_removal_results(console, remove_safe_and_prune_zombies(verdicts), root)
    else:
        console.print(_dry_run_summary(verdicts))


def _exit_if_forced_path_was_not_scanned(
    forced_paths: frozenset[Path], verdicts: list[Verdict]
) -> None:
    scanned_paths = {verdict.path.resolve() for verdict in verdicts}
    missing_paths = sorted(path for path in forced_paths if path not in scanned_paths)
    if missing_paths:
        missing = ", ".join(str(path) for path in missing_paths)
        typer.echo(f"error: --force names no worktree found in the scan: {missing}", err=True)
        raise typer.Exit(2)


def _dry_run_summary(verdicts: list[Verdict]) -> str:
    safe_count = sum(1 for verdict in verdicts if verdict.status is Status.SAFE)
    zombie_count = sum(1 for verdict in verdicts if verdict.status is Status.ZOMBIE)
    if not safe_count and not zombie_count:
        return "Nothing to clean up."
    return (
        f"Dry run. {safe_count} safe to remove, {zombie_count} zombies to prune. "
        "Add --delete to do it."
    )


def _print_removal_results(console: Console, results: list[RemovalResult], root: Path) -> None:
    for result in results:
        shown_path = _path_relative_to_root(result.path, root)
        if result.error:
            console.print(f"[red]failed[/] {shown_path}: {result.error}")
        else:
            console.print(f"[green]removed[/] {shown_path}")
    if any(result.error for result in results):
        raise typer.Exit(1)


def _verdict_table(verdicts: list[Verdict], root: Path) -> Table:
    table = Table(show_edge=False, pad_edge=False)
    table.add_column("Path")
    table.add_column("Branch")
    table.add_column("Status")
    table.add_column("Last commit", justify="right")
    table.add_column("Reason")
    now = datetime.now(UTC)
    for verdict in verdicts:
        color = STATUS_COLOR[verdict.status]
        table.add_row(
            _path_relative_to_root(verdict.path, root),
            verdict.branch or "-",
            f"[{color}]{verdict.status.value}[/]",
            _compact_age(verdict.last_commit_at, now),
            verdict.reason,
        )
    return table


def _path_relative_to_root(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _compact_age(moment: datetime | None, now: datetime) -> str:
    if moment is None:
        return "-"
    days = (now - moment).days
    if days < 1:
        return "today"
    return f"{days}d ago"
