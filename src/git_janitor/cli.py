from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from git_janitor import __version__
from git_janitor.clean import clean
from git_janitor.git import GitError
from git_janitor.models import Removal, Status, Verdict
from git_janitor.scan import ScanOptions
from git_janitor.scan import scan as run_scan

app = typer.Typer(
    help="Find old git worktrees and clones and clean them up safely.",
    no_args_is_help=True,
    add_completion=False,
)

CWD = Path(".")
STATUS_STYLE = {Status.ZOMBIE: "magenta", Status.SAFE: "green", Status.KEEP: "yellow"}


def _show_version(value: bool) -> None:
    if value:
        typer.echo(__version__)
        raise typer.Exit()


@app.callback()
def main(
    version: Annotated[
        bool, typer.Option("--version", callback=_show_version, is_eager=True)
    ] = False,
) -> None:
    pass


@app.command(help="List worktrees under ROOT and say which are safe to delete.")
def scan(
    root: Annotated[Path, typer.Argument(exists=True, file_okay=False, resolve_path=True)] = CWD,
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
    forced = frozenset(path.resolve() for path in force or [])
    options = ScanOptions(
        targets=tuple(target or []), idle_days=idle_days, forced=forced, cwd=Path.cwd()
    )
    try:
        verdicts = run_scan(root, max_depth, options)
    except GitError as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(1) from error
    _check_forced_paths_exist(forced, verdicts)
    if not verdicts:
        typer.echo(f"No git repositories found under {root}")
        return
    console = Console()
    console.print(_table(verdicts, root))
    if delete:
        _report(console, clean(verdicts, forced), root)
    else:
        console.print(_dry_run_hint(verdicts))


def _check_forced_paths_exist(forced: frozenset[Path], verdicts: list[Verdict]) -> None:
    known = {verdict.path.resolve() for verdict in verdicts}
    unknown = sorted(path for path in forced if path not in known)
    if unknown:
        names = ", ".join(str(path) for path in unknown)
        typer.echo(f"error: --force names no worktree found in the scan: {names}", err=True)
        raise typer.Exit(2)


def _dry_run_hint(verdicts: list[Verdict]) -> str:
    safe = sum(1 for v in verdicts if v.status is Status.SAFE)
    zombies = sum(1 for v in verdicts if v.status is Status.ZOMBIE)
    if not safe and not zombies:
        return "Nothing to clean up."
    return f"Dry run. {safe} safe to remove, {zombies} zombies to prune. Add --delete to do it."


def _report(console: Console, removals: list[Removal], root: Path) -> None:
    for removal in removals:
        where = _display_path(removal.path, root)
        if removal.error:
            console.print(f"[red]failed[/] {where}: {removal.error}")
        else:
            console.print(f"[green]removed[/] {where}")
    if any(removal.error for removal in removals):
        raise typer.Exit(1)


def _table(verdicts: list[Verdict], root: Path) -> Table:
    table = Table(show_edge=False, pad_edge=False)
    table.add_column("Path")
    table.add_column("Branch")
    table.add_column("Status")
    table.add_column("Last commit", justify="right")
    table.add_column("Reason")
    now = datetime.now(UTC)
    for verdict in verdicts:
        style = STATUS_STYLE[verdict.status]
        table.add_row(
            _display_path(verdict.path, root),
            verdict.branch or "-",
            f"[{style}]{verdict.status.value}[/]",
            _age(verdict.last_commit_at, now),
            verdict.reason,
        )
    return table


def _display_path(path: Path, root: Path) -> str:
    try:
        return path.resolve().relative_to(root).as_posix()
    except ValueError:
        return str(path)


def _age(moment: datetime | None, now: datetime) -> str:
    if moment is None:
        return "-"
    days = (now - moment).days
    if days < 1:
        return "today"
    return f"{days}d ago"
