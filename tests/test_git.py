import shutil
from pathlib import Path

from conftest import commit_file, git
from typer.testing import CliRunner

from git_janitor import git as janitor_git
from git_janitor.cli import app
from git_janitor.models import Status
from git_janitor.scan import scan

PORCELAIN = """worktree C:/Repo/app
HEAD 1111111111111111111111111111111111111111
branch refs/heads/main

worktree C:/Repo/app-FP-1
HEAD 2222222222222222222222222222222222222222
branch refs/heads/feature/FP-1
locked

worktree C:/Repo/app-detached
HEAD 3333333333333333333333333333333333333333
detached

worktree C:/Repo/app-gone
HEAD 4444444444444444444444444444444444444444
branch refs/heads/old
prunable gitdir file points to non-existent location

"""


def test_parse_worktree_list_reads_every_field() -> None:
    main, locked, detached, gone = janitor_git.parse_worktree_list(PORCELAIN)

    assert main.is_main
    assert main.branch == "main"
    assert not locked.is_main
    assert locked.branch == "feature/FP-1"
    assert locked.locked
    assert detached.detached
    assert detached.branch is None
    assert gone.prunable
    assert gone.path == Path("C:/Repo/app-gone")


def test_list_worktrees_includes_linked_worktree(repo: Path) -> None:
    linked = repo.parent / "app-FP-1"
    git(repo, "worktree", "add", "-q", "-b", "feature/FP-1", str(linked))

    entries = janitor_git.list_worktrees(repo)

    assert [e.path.resolve() for e in entries] == [repo.resolve(), linked.resolve()]
    assert entries[1].branch == "feature/FP-1"


def test_changed_file_count_sees_modified_and_untracked(repo: Path) -> None:
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    (repo / "new.txt").write_text("new\n", encoding="utf-8")

    assert janitor_git.changed_file_count(repo) == 2


def test_last_commit_time_is_none_in_empty_repo(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")

    assert janitor_git.last_commit_time(tmp_path) is None


def test_scan_reports_main_dirty_and_zombie(repo: Path) -> None:
    dirty = repo.parent / "app-dirty"
    gone = repo.parent / "app-gone"
    git(repo, "worktree", "add", "-q", "-b", "dirty", str(dirty))
    git(repo, "worktree", "add", "-q", "-b", "gone", str(gone))
    commit_file(dirty, "work.txt")
    (dirty / "work.txt").write_text("more\n", encoding="utf-8")
    shutil.rmtree(gone)

    verdicts = {v.path.resolve(): v for v in scan(repo.parent, max_depth=2)}

    assert len(verdicts) == 3
    assert verdicts[repo.resolve()].reason == "main working tree"
    assert verdicts[dirty.resolve()].reason == "uncommitted changes in 1 file"
    assert verdicts[gone.resolve()].status is Status.ZOMBIE


def test_scan_does_not_touch_anything(repo: Path) -> None:
    gone = repo.parent / "app-gone"
    git(repo, "worktree", "add", "-q", "-b", "gone", str(gone))
    shutil.rmtree(gone)
    before = git(repo, "worktree", "list", "--porcelain")

    scan(repo.parent, max_depth=2)

    assert git(repo, "worktree", "list", "--porcelain") == before


def test_scan_finds_repositories_nested_in_a_repository(tmp_path: Path) -> None:
    outer = tmp_path / "Repo"
    inner = outer / "app"
    inner.mkdir(parents=True)
    git(outer, "init", "-q", "-b", "main")
    git(inner, "init", "-q", "-b", "main")
    commit_file(inner, "README.md")

    paths = {v.path.resolve() for v in scan(outer, max_depth=2)}

    assert paths == {outer.resolve(), inner.resolve()}


def test_cli_scan_prints_table(repo: Path) -> None:
    result = CliRunner().invoke(app, ["scan", str(repo.parent)])

    assert result.exit_code == 0, result.output
    assert "main working tree" in result.output


def test_cli_scan_empty_folder(tmp_path: Path) -> None:
    empty = tmp_path / "nothing"
    empty.mkdir()

    result = CliRunner().invoke(app, ["scan", str(empty)])

    assert result.exit_code == 0
    assert "No git repositories found" in result.output
