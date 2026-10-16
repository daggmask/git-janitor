from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from git_janitor import __version__
from git_janitor.git import GitError
from git_janitor.models import Status, Verdict
from git_janitor.scan import scan as run_scan

app = typer.Typer(no_args_is_help=True, add_completion=False)

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
    """Find old git worktrees and clones and clean them up safely."""


@app.command()
def scan(
    root: Annotated[Path, typer.Argument(exists=True, file_okay=False, resolve_path=True)] = CWD,
    max_depth: Annotated[int, typer.Option(min=0, help="How deep to look for repositories.")] = 3,
) -> None:
    """List worktrees under ROOT and say which are safe to delete. Deletes nothing."""
    try:
        verdicts = run_scan(root, max_depth)
    except GitError as error:
        typer.echo(f"error: {error}", err=True)
        raise typer.Exit(1) from error
    if not verdicts:
        typer.echo(f"No git repositories found under {root}")
        return
    Console().print(_table(verdicts, root))


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
