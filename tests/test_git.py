import shutil
import sys
from pathlib import Path

import pytest
from conftest import add_worktree, commit_file, git
from typer.testing import CliRunner

from git_janitor import git as janitor_git
from git_janitor.cli import app
from git_janitor.models import Status, Verdict
from git_janitor.scan import ScanOptions, scan

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

IDLE = ScanOptions(idle_days=0)


def verdicts_by_path(root: Path, options: ScanOptions = IDLE) -> dict[Path, Verdict]:
    return {v.path.resolve(): v for v in scan(root, max_depth=2, options=options)}


def run_cli(*args: str) -> str:
    result = CliRunner().invoke(app, ["scan", *args])
    assert result.exit_code == 0, result.output
    return result.output


def test_parse_worktree_list_reads_every_field() -> None:
    main, locked, detached, gone = janitor_git.parse_worktree_list(PORCELAIN)

    assert main.is_main
    assert main.branch == "main"
    assert locked.repository == Path("C:/Repo/app")
    assert locked.branch == "feature/FP-1"
    assert locked.locked
    assert detached.detached
    assert detached.branch is None
    assert gone.prunable


def test_parse_stash_branches_handles_both_subject_forms() -> None:
    output = "WIP on main: abc123 msg\nOn feature/x: my stash\nOn (no branch): wip\n"

    assert janitor_git.parse_stash_branches(output) == ["main", "feature/x", "(no branch)"]


def test_list_worktrees_includes_linked_worktree(repo: Path) -> None:
    linked = repo.parent / "app-FP-1"
    git(repo, "worktree", "add", "-q", "-b", "feature/FP-1", str(linked))

    entries = janitor_git.list_worktrees(repo)

    assert [e.path.resolve() for e in entries] == [repo.resolve(), linked.resolve()]
    assert entries[1].repository.resolve() == repo.resolve()


def test_changed_file_count_sees_modified_and_untracked(repo: Path) -> None:
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    (repo / "new.txt").write_text("new\n", encoding="utf-8")

    assert janitor_git.changed_file_count(repo) == 2


def test_last_commit_time_is_none_in_empty_repo(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")

    assert janitor_git.last_commit_time(tmp_path) is None


def test_default_target_follows_origin_head(pushed: Path) -> None:
    assert janitor_git.default_target(pushed) == "origin/main"


def test_fresh_worktree_has_nothing_beyond_target(pushed: Path) -> None:
    fresh = add_worktree(pushed, "fresh")

    verdict = verdicts_by_path(pushed.parent)[fresh.resolve()]

    assert verdict.status is Status.SAFE
    assert verdict.reason == "already in origin/main"


def test_regular_merge_is_safe(pushed: Path) -> None:
    branch = add_worktree(pushed, "merged")
    commit_file(branch, "a.txt")
    git(branch, "push", "-q", "origin", "merged")
    git(pushed, "merge", "-q", "--no-ff", "-m", "merge", "merged")
    git(pushed, "push", "-q", "origin", "main")

    verdict = verdicts_by_path(pushed.parent)[branch.resolve()]

    assert verdict.status is Status.SAFE
    assert verdict.reason == "already in origin/main"


def test_squash_merge_is_proven_by_patch_id(pushed: Path) -> None:
    branch = add_worktree(pushed, "squashed")
    commit_file(branch, "a.txt")
    commit_file(branch, "b.txt")
    git(branch, "push", "-q", "origin", "squashed")
    git(pushed, "merge", "-q", "--squash", "squashed")
    git(pushed, "commit", "-q", "-m", "squash")
    git(pushed, "push", "-q", "origin", "main")

    verdict = verdicts_by_path(pushed.parent)[branch.resolve()]

    assert verdict.status is Status.SAFE
    assert verdict.reason == "merged into origin/main"


def test_squash_with_extra_changes_is_not_proven(pushed: Path) -> None:
    branch = add_worktree(pushed, "squashed")
    commit_file(branch, "a.txt")
    git(branch, "push", "-q", "origin", "squashed")
    git(pushed, "merge", "-q", "--squash", "squashed")
    (pushed / "a.txt").write_text("edited during merge\n", encoding="utf-8")
    git(pushed, "add", "a.txt")
    git(pushed, "commit", "-q", "-m", "squash with edits")
    git(pushed, "push", "-q", "origin", "main")

    verdict = verdicts_by_path(pushed.parent)[branch.resolve()]

    assert verdict.status is Status.KEEP
    assert verdict.reason == "1 commit not in origin/main"


def test_rebased_commits_are_found_by_cherry(pushed: Path) -> None:
    branch = add_worktree(pushed, "rebased")
    commit_file(branch, "a.txt")
    git(branch, "push", "-q", "origin", "rebased")
    commit_file(pushed, "other.txt")
    git(pushed, "cherry-pick", "rebased")
    git(pushed, "push", "-q", "origin", "main")

    assert verdicts_by_path(pushed.parent)[branch.resolve()].status is Status.SAFE


def test_pushed_but_unmerged_is_kept(pushed: Path) -> None:
    branch = add_worktree(pushed, "open-pr")
    commit_file(branch, "a.txt")
    git(branch, "push", "-q", "origin", "open-pr")

    verdict = verdicts_by_path(pushed.parent)[branch.resolve()]

    assert verdict.status is Status.KEEP
    assert verdict.reason == "1 commit not in origin/main"


def test_unpushed_commit_is_kept(pushed: Path) -> None:
    branch = add_worktree(pushed, "local")
    commit_file(branch, "a.txt")

    assert verdicts_by_path(pushed.parent)[branch.resolve()].reason == "1 commit not pushed"


def test_stash_on_branch_is_kept(pushed: Path) -> None:
    branch = add_worktree(pushed, "stashed")
    (branch / "README.md").write_text("wip\n", encoding="utf-8")
    git(branch, "stash", "-q")

    verdict = verdicts_by_path(pushed.parent)[branch.resolve()]

    assert verdict.reason == "1 stash on this branch"


def test_recently_used_worktree_is_kept_by_default(pushed: Path) -> None:
    fresh = add_worktree(pushed, "fresh")

    verdict = verdicts_by_path(pushed.parent, ScanOptions())[fresh.resolve()]

    assert verdict.status is Status.KEEP
    assert verdict.reason == "used today, may still be in use"


def test_extra_target_can_prove_merge(pushed: Path) -> None:
    git(pushed, "push", "-q", "origin", "main:dev")
    branch = add_worktree(pushed, "into-dev")
    commit_file(branch, "a.txt")
    git(branch, "push", "-q", "origin", "into-dev:dev", "into-dev")
    git(pushed, "fetch", "-q", "origin")

    options = ScanOptions(targets=("origin/main", "origin/dev"), idle_days=0)
    verdict = verdicts_by_path(pushed.parent, options)[branch.resolve()]

    assert verdict.reason == "already in origin/dev"


def test_scan_keeps_worktree_list_order(pushed: Path) -> None:
    names = [f"app-{n}" for n in range(6)]
    paths = [add_worktree(pushed, name).resolve() for name in names]

    found = [v.path.resolve() for v in scan(pushed.parent, max_depth=1, options=IDLE)]

    assert found == [pushed.resolve(), *paths]


def test_scan_finds_repositories_nested_in_a_repository(tmp_path: Path) -> None:
    outer = tmp_path / "Repo"
    inner = outer / "app"
    inner.mkdir(parents=True)
    git(outer, "init", "-q", "-b", "main")
    git(inner, "init", "-q", "-b", "main")
    commit_file(inner, "README.md")

    assert set(verdicts_by_path(outer)) == {outer.resolve(), inner.resolve()}


def test_dry_run_changes_nothing(pushed: Path) -> None:
    fresh = add_worktree(pushed, "fresh")
    gone = add_worktree(pushed, "gone")
    shutil.rmtree(gone)
    before = git(pushed, "worktree", "list", "--porcelain")

    output = run_cli(str(pushed.parent), "--idle-days", "0")

    assert "Dry run. 1 safe to remove, 1 zombies to prune" in output
    assert fresh.exists()
    assert git(pushed, "worktree", "list", "--porcelain") == before


def test_delete_removes_only_safe_and_prunes_zombies(pushed: Path) -> None:
    (pushed / ".gitignore").write_text("bin/\n", encoding="utf-8")
    git(pushed, "add", ".gitignore")
    git(pushed, "commit", "-q", "-m", "ignore bin")
    git(pushed, "push", "-q", "origin", "main")
    safe = add_worktree(pushed, "safe")
    (safe / "bin").mkdir()
    (safe / "bin" / "app.dll").write_text("build output\n", encoding="utf-8")
    dirty = add_worktree(pushed, "dirty")
    (dirty / "notes.txt").write_text("keep me\n", encoding="utf-8")
    gone = add_worktree(pushed, "gone")
    shutil.rmtree(gone)

    output = run_cli(str(pushed.parent), "--idle-days", "0", "--delete")

    assert "removed" in output
    assert not safe.exists()
    assert (dirty / "notes.txt").exists()
    assert pushed.exists()
    remaining = [e.path.resolve() for e in janitor_git.list_worktrees(pushed)]
    assert remaining == [pushed.resolve(), dirty.resolve()]


def test_delete_runs_many_removals(pushed: Path) -> None:
    worktrees = [add_worktree(pushed, f"done-{n}") for n in range(8)]

    run_cli(str(pushed.parent), "--idle-days", "0", "--delete")

    assert not any(path.exists() for path in worktrees)
    assert len(janitor_git.list_worktrees(pushed)) == 1


def test_force_is_per_folder(pushed: Path) -> None:
    first = add_worktree(pushed, "first")
    second = add_worktree(pushed, "second")
    for path in (first, second):
        (path / "scratch.txt").write_text("wip\n", encoding="utf-8")

    run_cli(str(pushed.parent), "--idle-days", "0", "--delete", "--force", str(first))

    assert not first.exists()
    assert (second / "scratch.txt").exists()


def test_force_with_unknown_folder_fails(pushed: Path, tmp_path: Path) -> None:
    result = CliRunner().invoke(app, ["scan", str(pushed.parent), "--force", str(tmp_path / "x")])

    assert result.exit_code == 2


def test_delete_skips_worktree_holding_current_directory(
    pushed: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    here = add_worktree(pushed, "here")
    monkeypatch.chdir(here)

    output = run_cli(str(pushed.parent), "--idle-days", "0", "--delete")

    assert here.exists()
    assert "you are standing in it" in output


@pytest.mark.skipif(sys.platform != "win32", reason="only Windows refuses to rename open folders")
def test_delete_skips_worktree_with_open_file(pushed: Path) -> None:
    busy = add_worktree(pushed, "busy")

    with (busy / "README.md").open(encoding="utf-8"):
        result = CliRunner().invoke(
            app, ["scan", str(pushed.parent), "--idle-days", "0", "--delete"]
        )

    assert result.exit_code == 1
    assert "in use by another program, skipped" in result.output
    assert (busy / "README.md").exists()


def test_cli_scan_empty_folder(tmp_path: Path) -> None:
    empty = tmp_path / "nothing"
    empty.mkdir()

    assert "No git repositories found" in run_cli(str(empty))
