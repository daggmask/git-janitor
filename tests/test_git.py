import shutil
import sys
from pathlib import Path

import pytest
from conftest import add_worktree, commit_file, git
from typer.testing import CliRunner

from git_janitor import git as janitor_git
from git_janitor.cli import app
from git_janitor.models import Status, Verdict
from git_janitor.scan import ScanOptions, scan_worktrees

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

IGNORE_RECENT_USE = ScanOptions(idle_days=0)


def verdicts_by_path(root: Path, options: ScanOptions = IGNORE_RECENT_USE) -> dict[Path, Verdict]:
    return {
        verdict.path.resolve(): verdict
        for verdict in scan_worktrees(root, max_depth=2, options=options)
    }


def command_that_leaves_marker(tmp_path: Path) -> tuple[str, Path]:
    marker = tmp_path / "command-ran"
    script = tmp_path / "leave_marker.py"
    script.write_text(f"open({str(marker)!r}, 'w').close()\n", encoding="utf-8")
    return f'"{Path(sys.executable).as_posix()}" "{script.as_posix()}"', marker


def commit_with_signature_block(worktree: Path) -> None:
    tree = git(worktree, "write-tree").strip()
    parent = git(worktree, "rev-parse", "HEAD").strip()
    commit_lines = [
        f"tree {tree}",
        f"parent {parent}",
        "author Test <test@example.com> 1700000000 +0000",
        "committer Test <test@example.com> 1700000000 +0000",
        "gpgsig -----BEGIN PGP SIGNATURE-----",
        " ",
        " abc",
        " -----END PGP SIGNATURE-----",
        "",
        "signed",
        "",
    ]
    commit_file_path = worktree.parent / "signed-commit.txt"
    commit_file_path.write_bytes("\n".join(commit_lines).encode("utf-8"))
    commit = git(worktree, "hash-object", "-t", "commit", "-w", str(commit_file_path)).strip()
    git(worktree, "reset", "-q", "--hard", commit)


def run_scan_command(*args: str) -> str:
    result = CliRunner().invoke(app, ["scan", *args])
    assert result.exit_code == 0, result.output
    return result.output


def test_parse_worktree_list_reads_every_field() -> None:
    main, locked, detached, gone = janitor_git.parse_worktree_list(PORCELAIN)

    assert main.is_main
    assert main.branch == "main"
    assert locked.main_worktree_path == Path("C:/Repo/app")
    assert locked.branch == "feature/FP-1"
    assert locked.is_locked
    assert detached.is_detached
    assert detached.branch is None
    assert gone.is_prunable


def test_git_error_last_line_skips_warnings() -> None:
    error = janitor_git.GitError(["status"], Path("."), 128, "warning: x\nfatal: y\n")

    assert error.last_line == "fatal: y"


def test_parse_stash_branch_names_handles_both_subject_forms() -> None:
    output = "WIP on main: abc123 msg\nOn feature/x: my stash\nOn (no branch): wip\n"

    assert janitor_git.parse_stash_branch_names(output) == ["main", "feature/x", "(no branch)"]


def test_list_worktrees_includes_linked_worktree(repo: Path) -> None:
    linked = repo.parent / "app-FP-1"
    git(repo, "worktree", "add", "-q", "-b", "feature/FP-1", str(linked))

    entries = janitor_git.list_worktrees(repo)

    assert [worktree.path.resolve() for worktree in entries] == [repo.resolve(), linked.resolve()]
    assert entries[1].main_worktree_path.resolve() == repo.resolve()


def test_changed_file_count_sees_modified_and_untracked(repo: Path) -> None:
    (repo / "README.md").write_text("changed\n", encoding="utf-8")
    (repo / "new.txt").write_text("new\n", encoding="utf-8")

    assert janitor_git.changed_file_count(repo) == 2


def test_last_commit_time_is_none_in_empty_repo(tmp_path: Path) -> None:
    git(tmp_path, "init", "-q")

    assert janitor_git.last_commit_time(tmp_path) is None


def test_origin_default_branch_follows_origin_head(repo_with_remote: Path) -> None:
    assert janitor_git.origin_default_branch(repo_with_remote) == "origin/main"


def test_fresh_worktree_has_nothing_beyond_target(repo_with_remote: Path) -> None:
    fresh = add_worktree(repo_with_remote, "fresh")

    verdict = verdicts_by_path(repo_with_remote.parent)[fresh.resolve()]

    assert verdict.status is Status.SAFE
    assert verdict.reason == "already in origin/main"


def test_regular_merge_is_safe(repo_with_remote: Path) -> None:
    branch = add_worktree(repo_with_remote, "merged")
    commit_file(branch, "a.txt")
    git(branch, "push", "-q", "origin", "merged")
    git(repo_with_remote, "merge", "-q", "--no-ff", "-m", "merge", "merged")
    git(repo_with_remote, "push", "-q", "origin", "main")

    verdict = verdicts_by_path(repo_with_remote.parent)[branch.resolve()]

    assert verdict.status is Status.SAFE
    assert verdict.reason == "already in origin/main"


def test_squash_merge_is_proven_by_patch_id(repo_with_remote: Path) -> None:
    branch = add_worktree(repo_with_remote, "squashed")
    commit_file(branch, "a.txt")
    commit_file(branch, "b.txt")
    git(branch, "push", "-q", "origin", "squashed")
    git(repo_with_remote, "merge", "-q", "--squash", "squashed")
    git(repo_with_remote, "commit", "-q", "-m", "squash")
    git(repo_with_remote, "push", "-q", "origin", "main")

    verdict = verdicts_by_path(repo_with_remote.parent)[branch.resolve()]

    assert verdict.status is Status.SAFE
    assert verdict.reason == "merged into origin/main"


def test_squash_with_extra_changes_is_not_proven(repo_with_remote: Path) -> None:
    branch = add_worktree(repo_with_remote, "squashed")
    commit_file(branch, "a.txt")
    git(branch, "push", "-q", "origin", "squashed")
    git(repo_with_remote, "merge", "-q", "--squash", "squashed")
    (repo_with_remote / "a.txt").write_text("edited during merge\n", encoding="utf-8")
    git(repo_with_remote, "add", "a.txt")
    git(repo_with_remote, "commit", "-q", "-m", "squash with edits")
    git(repo_with_remote, "push", "-q", "origin", "main")

    verdict = verdicts_by_path(repo_with_remote.parent)[branch.resolve()]

    assert verdict.status is Status.KEEP
    assert verdict.reason == "1 commit not in origin/main"


def test_rebased_commits_are_found_by_cherry(repo_with_remote: Path) -> None:
    branch = add_worktree(repo_with_remote, "rebased")
    commit_file(branch, "a.txt")
    git(branch, "push", "-q", "origin", "rebased")
    commit_file(repo_with_remote, "other.txt")
    git(repo_with_remote, "cherry-pick", "rebased")
    git(repo_with_remote, "push", "-q", "origin", "main")

    assert verdicts_by_path(repo_with_remote.parent)[branch.resolve()].status is Status.SAFE


def test_pushed_but_unmerged_is_kept(repo_with_remote: Path) -> None:
    branch = add_worktree(repo_with_remote, "open-pr")
    commit_file(branch, "a.txt")
    git(branch, "push", "-q", "origin", "open-pr")

    verdict = verdicts_by_path(repo_with_remote.parent)[branch.resolve()]

    assert verdict.status is Status.KEEP
    assert verdict.reason == "1 commit not in origin/main"


def test_unpushed_commit_is_kept(repo_with_remote: Path) -> None:
    branch = add_worktree(repo_with_remote, "local")
    commit_file(branch, "a.txt")

    assert (
        verdicts_by_path(repo_with_remote.parent)[branch.resolve()].reason == "1 commit not pushed"
    )


def test_stash_on_branch_is_kept(repo_with_remote: Path) -> None:
    branch = add_worktree(repo_with_remote, "stashed")
    (branch / "README.md").write_text("wip\n", encoding="utf-8")
    git(branch, "stash", "-q")

    verdict = verdicts_by_path(repo_with_remote.parent)[branch.resolve()]

    assert verdict.reason == "1 stash on this branch"


def test_recently_used_worktree_is_kept_by_default(repo_with_remote: Path) -> None:
    fresh = add_worktree(repo_with_remote, "fresh")

    verdict = verdicts_by_path(repo_with_remote.parent, ScanOptions())[fresh.resolve()]

    assert verdict.status is Status.KEEP
    assert verdict.reason == "used today, may still be in use"


def test_extra_target_can_prove_merge(repo_with_remote: Path) -> None:
    git(repo_with_remote, "push", "-q", "origin", "main:dev")
    branch = add_worktree(repo_with_remote, "into-dev")
    commit_file(branch, "a.txt")
    git(branch, "push", "-q", "origin", "into-dev:dev", "into-dev")
    git(repo_with_remote, "fetch", "-q", "origin")

    options = ScanOptions(target_branches=("origin/main", "origin/dev"), idle_days=0)
    verdict = verdicts_by_path(repo_with_remote.parent, options)[branch.resolve()]

    assert verdict.reason == "already in origin/dev"


def test_scan_keeps_worktree_list_order(repo_with_remote: Path) -> None:
    worktree_names = [f"app-{number}" for number in range(6)]
    worktree_paths = [add_worktree(repo_with_remote, name).resolve() for name in worktree_names]

    scanned_paths = [
        verdict.path.resolve()
        for verdict in scan_worktrees(
            repo_with_remote.parent, max_depth=1, options=IGNORE_RECENT_USE
        )
    ]

    assert scanned_paths == [repo_with_remote.resolve(), *worktree_paths]


def test_scan_finds_repositories_nested_in_a_repository(tmp_path: Path) -> None:
    outer = tmp_path / "Repo"
    inner = outer / "app"
    inner.mkdir(parents=True)
    git(outer, "init", "-q", "-b", "main")
    git(inner, "init", "-q", "-b", "main")
    commit_file(inner, "README.md")

    assert set(verdicts_by_path(outer)) == {outer.resolve(), inner.resolve()}


def test_broken_folder_does_not_stop_the_scan(repo_with_remote: Path) -> None:
    fresh = add_worktree(repo_with_remote, "fresh")
    orphan = repo_with_remote.parent / "orphan"
    orphan.mkdir()
    (orphan / ".git").write_text("gitdir: ../moved-away/.git\n", encoding="utf-8")

    verdicts = verdicts_by_path(repo_with_remote.parent)

    assert verdicts[fresh.resolve()].status is Status.SAFE
    assert verdicts[orphan.resolve()].status is Status.KEEP
    assert verdicts[orphan.resolve()].reason.startswith("git failed: ")


def test_scan_does_not_run_fsmonitor_from_scanned_repo(
    repo_with_remote: Path, tmp_path: Path
) -> None:
    add_worktree(repo_with_remote, "fresh")
    command, marker = command_that_leaves_marker(tmp_path)
    git(repo_with_remote, "config", "core.fsmonitor", command)

    verdicts_by_path(repo_with_remote.parent)

    assert not marker.exists()


def test_scan_does_not_run_textconv_from_scanned_repo(
    repo_with_remote: Path, tmp_path: Path
) -> None:
    branch = add_worktree(repo_with_remote, "open-pr")
    commit_file(branch, ".gitattributes", "*.txt diff=marker\n")
    commit_file(branch, "a.txt")
    git(branch, "push", "-q", "origin", "open-pr")
    command, marker = command_that_leaves_marker(tmp_path)
    git(repo_with_remote, "config", "diff.marker.textconv", command)

    verdict = verdicts_by_path(repo_with_remote.parent)[branch.resolve()]

    assert verdict.reason == "2 commits not in origin/main"
    assert not marker.exists()


def test_scan_does_not_run_gpg_from_scanned_repo(repo_with_remote: Path, tmp_path: Path) -> None:
    signed = add_worktree(repo_with_remote, "signed")
    commit_with_signature_block(signed)
    marker = tmp_path / "gpg-ran"
    fake_gpg = tmp_path / "fake-gpg.sh"
    fake_gpg.write_bytes(f"#!/bin/sh\ntouch '{marker.as_posix()}'\nexit 1\n".encode())
    fake_gpg.chmod(0o755)
    git(repo_with_remote, "config", "log.showSignature", "true")
    git(repo_with_remote, "config", "gpg.program", fake_gpg.as_posix())

    verdicts_by_path(repo_with_remote.parent)

    assert not marker.exists()


def test_missing_git_gives_keep_rows_not_a_crash(
    repo_with_remote: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    add_worktree(repo_with_remote, "fresh")
    monkeypatch.setenv("PATH", "")

    verdicts = verdicts_by_path(repo_with_remote.parent)

    assert verdicts
    assert all(verdict.status is Status.KEEP for verdict in verdicts.values())
    assert all(verdict.reason.startswith("git failed: ") for verdict in verdicts.values())


def test_delete_leaves_locked_worktree_with_missing_folder(repo_with_remote: Path) -> None:
    unplugged = add_worktree(repo_with_remote, "unplugged")
    git(repo_with_remote, "worktree", "lock", str(unplugged))
    shutil.rmtree(unplugged)

    output = run_scan_command(str(repo_with_remote.parent), "--idle-days", "0", "--delete")

    assert "removed" not in output
    assert "worktree is locked" in output
    assert len(janitor_git.list_worktrees(repo_with_remote)) == 2


def test_dry_run_changes_nothing(repo_with_remote: Path) -> None:
    fresh = add_worktree(repo_with_remote, "fresh")
    gone = add_worktree(repo_with_remote, "gone")
    shutil.rmtree(gone)
    worktrees_before = git(repo_with_remote, "worktree", "list", "--porcelain")

    output = run_scan_command(str(repo_with_remote.parent), "--idle-days", "0")

    assert "Dry run. 1 safe to remove, 1 zombies to prune" in output
    assert fresh.exists()
    assert git(repo_with_remote, "worktree", "list", "--porcelain") == worktrees_before


def test_delete_removes_only_safe_and_prunes_zombies(repo_with_remote: Path) -> None:
    (repo_with_remote / ".gitignore").write_text("bin/\n", encoding="utf-8")
    git(repo_with_remote, "add", ".gitignore")
    git(repo_with_remote, "commit", "-q", "-m", "ignore bin")
    git(repo_with_remote, "push", "-q", "origin", "main")
    safe = add_worktree(repo_with_remote, "safe")
    (safe / "bin").mkdir()
    (safe / "bin" / "app.dll").write_text("build output\n", encoding="utf-8")
    dirty = add_worktree(repo_with_remote, "dirty")
    (dirty / "notes.txt").write_text("keep me\n", encoding="utf-8")
    gone = add_worktree(repo_with_remote, "gone")
    shutil.rmtree(gone)

    output = run_scan_command(str(repo_with_remote.parent), "--idle-days", "0", "--delete")

    assert "removed" in output
    assert not safe.exists()
    assert (dirty / "notes.txt").exists()
    assert repo_with_remote.exists()
    remaining_worktrees = [
        worktree.path.resolve() for worktree in janitor_git.list_worktrees(repo_with_remote)
    ]
    assert remaining_worktrees == [repo_with_remote.resolve(), dirty.resolve()]


def test_delete_runs_many_removals(repo_with_remote: Path) -> None:
    worktrees = [add_worktree(repo_with_remote, f"done-{number}") for number in range(8)]

    run_scan_command(str(repo_with_remote.parent), "--idle-days", "0", "--delete")

    assert not any(path.exists() for path in worktrees)
    assert len(janitor_git.list_worktrees(repo_with_remote)) == 1


def test_force_is_per_folder(repo_with_remote: Path) -> None:
    first = add_worktree(repo_with_remote, "first")
    second = add_worktree(repo_with_remote, "second")
    for path in (first, second):
        (path / "scratch.txt").write_text("wip\n", encoding="utf-8")

    run_scan_command(
        str(repo_with_remote.parent), "--idle-days", "0", "--delete", "--force", str(first)
    )

    assert not first.exists()
    assert (second / "scratch.txt").exists()


def test_force_with_unknown_folder_fails(repo_with_remote: Path, tmp_path: Path) -> None:
    result = CliRunner().invoke(
        app, ["scan", str(repo_with_remote.parent), "--force", str(tmp_path / "x")]
    )

    assert result.exit_code == 2


def test_delete_skips_worktree_holding_current_directory(
    repo_with_remote: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    current_worktree = add_worktree(repo_with_remote, "here")
    monkeypatch.chdir(current_worktree)

    output = run_scan_command(str(repo_with_remote.parent), "--idle-days", "0", "--delete")

    assert current_worktree.exists()
    assert "you are standing in it" in output


@pytest.mark.skipif(sys.platform != "win32", reason="only Windows refuses to rename open folders")
def test_delete_skips_worktree_with_open_file(repo_with_remote: Path) -> None:
    worktree_in_use = add_worktree(repo_with_remote, "busy")

    with (worktree_in_use / "README.md").open(encoding="utf-8"):
        result = CliRunner().invoke(
            app, ["scan", str(repo_with_remote.parent), "--idle-days", "0", "--delete"]
        )

    assert result.exit_code == 1
    assert "in use by another program, skipped" in result.output
    assert (worktree_in_use / "README.md").exists()


def test_delete_reports_folder_that_could_not_be_renamed_back(
    repo_with_remote: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    stuck = add_worktree(repo_with_remote, "stuck")
    fine = add_worktree(repo_with_remote, "fine")
    real_rename = Path.rename

    def rename_that_fails_moving_stuck_back(self: Path, target: Path) -> Path:
        if self.name.startswith("stuck.janitor-"):
            raise PermissionError("held open")
        return real_rename(self, target)

    monkeypatch.setattr(Path, "rename", rename_that_fails_moving_stuck_back)

    result = CliRunner().invoke(
        app, ["scan", str(repo_with_remote.parent), "--idle-days", "0", "--delete"]
    )

    assert result.exit_code == 1
    assert "could not move it back" in result.output
    assert not fine.exists()
    assert not stuck.exists()


def test_cli_scan_empty_folder(tmp_path: Path) -> None:
    empty = tmp_path / "nothing"
    empty.mkdir()

    assert "No git repositories found" in run_scan_command(str(empty))
