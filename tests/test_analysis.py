from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from git_janitor.analysis import classify
from git_janitor.models import Status, TargetCheck, Verdict, WorktreeEntry, WorktreeFacts

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
LONG_AGO = NOW - timedelta(days=30)

LINKED = WorktreeEntry(
    path=Path("/repo/app-FP-1"),
    repository=Path("/repo/app"),
    head="abc123",
    branch="feature/FP-1",
    is_main=False,
)

MERGED = TargetCheck(target="origin/main", commits=2, unmerged=0)
UNMERGED = TargetCheck(target="origin/main", commits=3, unmerged=3)


def entry(**overrides: Any) -> WorktreeEntry:
    return replace(LINKED, **overrides)


def facts(**overrides: Any) -> WorktreeFacts:
    base = WorktreeFacts(
        entry=LINKED,
        exists=True,
        last_commit_at=LONG_AGO,
        last_used_at=LONG_AGO,
        targets=(MERGED,),
    )
    return replace(base, **overrides)


def verdict(**overrides: Any) -> Verdict:
    return classify(facts(**overrides), NOW, idle_days=3)


def test_merged_clean_idle_worktree_is_safe() -> None:
    result = verdict()
    assert result.status is Status.SAFE
    assert result.reason == "merged into origin/main"


def test_main_working_tree_is_always_kept() -> None:
    result = verdict(entry=entry(is_main=True), forced=True)
    assert result.status is Status.KEEP
    assert result.reason == "main working tree"


def test_missing_folder_is_zombie() -> None:
    assert verdict(entry=entry(prunable=True), exists=False).status is Status.ZOMBIE


def test_locked_worktree_is_kept_even_when_forced() -> None:
    result = verdict(entry=entry(locked=True), forced=True)
    assert result.status is Status.KEEP
    assert result.reason == "worktree is locked"


def test_worktree_holding_the_current_directory_is_kept() -> None:
    result = verdict(holds_cwd=True, forced=True)
    assert result.status is Status.KEEP
    assert result.reason == "you are standing in it"


def test_force_overrides_uncommitted_changes() -> None:
    result = verdict(changed_files=4, unpushed=2, forced=True)
    assert result.status is Status.SAFE
    assert result.reason == "forced with --force"


def test_uncommitted_changes_are_counted_in_reason() -> None:
    result = verdict(changed_files=3)
    assert result.status is Status.KEEP
    assert result.reason == "uncommitted changes in 3 files"


def test_single_changed_file_reads_naturally() -> None:
    assert verdict(changed_files=1).reason == "uncommitted changes in 1 file"


def test_stash_on_branch_keeps_it() -> None:
    assert verdict(stashes=2).reason == "2 stashes on this branch"


def test_unpushed_commits_keep_it_even_if_merged() -> None:
    result = verdict(unpushed=3)
    assert result.status is Status.KEEP
    assert result.reason == "3 commits not pushed"


def test_recently_used_worktree_is_kept() -> None:
    result = verdict(last_used_at=NOW - timedelta(hours=5))
    assert result.status is Status.KEEP
    assert result.reason == "used today, may still be in use"


def test_idle_days_zero_does_not_keep_recent_use() -> None:
    result = classify(facts(last_used_at=NOW - timedelta(hours=5)), NOW, idle_days=0)
    assert result.status is Status.SAFE


def test_old_last_commit_alone_never_makes_it_safe() -> None:
    result = verdict(targets=(UNMERGED,), last_commit_at=NOW - timedelta(days=900))
    assert result.status is Status.KEEP
    assert result.reason == "3 commits not in origin/main"


def test_squash_merge_proven_by_patch_id() -> None:
    squashed = replace(UNMERGED, branch_patch_id="p1", target_patch_ids=frozenset({"p0", "p1"}))
    result = verdict(targets=(squashed,))
    assert result.status is Status.SAFE
    assert result.reason == "merged into origin/main"


def test_patch_id_missing_from_target_is_not_merged() -> None:
    other = replace(UNMERGED, branch_patch_id="p1", target_patch_ids=frozenset({"p0"}))
    assert verdict(targets=(other,)).status is Status.KEEP


def test_branch_without_own_commits_is_safe() -> None:
    result = verdict(targets=(TargetCheck(target="origin/main", commits=0, unmerged=0),))
    assert result.status is Status.SAFE
    assert result.reason == "already in origin/main"


def test_any_target_can_prove_merge() -> None:
    into_dev = TargetCheck(target="origin/dev", commits=1, unmerged=0)
    result = verdict(targets=(UNMERGED, into_dev))
    assert result.reason == "merged into origin/dev"


def test_reason_names_the_closest_target() -> None:
    almost = TargetCheck(target="origin/dev", commits=3, unmerged=1)
    assert verdict(targets=(UNMERGED, almost)).reason == "1 commit not in origin/dev"


def test_no_target_means_keep() -> None:
    result = verdict(targets=())
    assert result.status is Status.KEEP
    assert "--target" in result.reason


def test_detached_head_is_judged_like_any_other() -> None:
    result = verdict(entry=entry(branch=None, detached=True))
    assert result.status is Status.SAFE
    assert result.branch is None
