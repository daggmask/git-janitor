from dataclasses import replace
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from git_janitor.analysis import classify_worktree
from git_janitor.models import MergeCheck, Status, Verdict, WorktreeEntry, WorktreeFacts

NOW = datetime(2026, 10, 16, 12, 0, tzinfo=UTC)
LONG_AGO = NOW - timedelta(days=30)

LINKED_WORKTREE = WorktreeEntry(
    path=Path("/repo/app-FP-1"),
    main_worktree_path=Path("/repo/app"),
    head_commit="abc123",
    branch="feature/FP-1",
    is_main=False,
)

MERGED_INTO_MAIN = MergeCheck(target_branch="origin/main", commits_ahead=2, commits_not_in_target=0)
THREE_COMMITS_NOT_IN_MAIN = MergeCheck(
    target_branch="origin/main", commits_ahead=3, commits_not_in_target=3
)


def worktree_with(**overrides: Any) -> WorktreeEntry:
    return replace(LINKED_WORKTREE, **overrides)


def facts_with(**overrides: Any) -> WorktreeFacts:
    merged_idle_worktree = WorktreeFacts(
        worktree=LINKED_WORKTREE,
        folder_exists=True,
        last_commit_at=LONG_AGO,
        last_used_at=LONG_AGO,
        merge_checks=(MERGED_INTO_MAIN,),
    )
    return replace(merged_idle_worktree, **overrides)


def verdict_for(**overrides: Any) -> Verdict:
    return classify_worktree(facts_with(**overrides), NOW, idle_days=3)


def test_merged_clean_idle_worktree_is_safe() -> None:
    verdict = verdict_for()
    assert verdict.status is Status.SAFE
    assert verdict.reason == "merged into origin/main"


def test_main_working_tree_is_always_kept() -> None:
    verdict = verdict_for(worktree=worktree_with(is_main=True), is_forced=True)
    assert verdict.status is Status.KEEP
    assert verdict.reason == "main working tree"


def test_missing_folder_is_zombie() -> None:
    verdict = verdict_for(worktree=worktree_with(is_prunable=True), folder_exists=False)
    assert verdict.status is Status.ZOMBIE


def test_locked_worktree_is_kept_even_when_forced() -> None:
    verdict = verdict_for(worktree=worktree_with(is_locked=True), is_forced=True)
    assert verdict.status is Status.KEEP
    assert verdict.reason == "worktree is locked"


def test_locked_worktree_with_missing_folder_is_kept_not_zombie() -> None:
    verdict = verdict_for(worktree=worktree_with(is_locked=True), folder_exists=False)
    assert verdict.status is Status.KEEP
    assert verdict.reason == "worktree is locked"


def test_git_failure_keeps_it_even_when_forced() -> None:
    verdict = verdict_for(git_failure="fatal: not a git repository", is_forced=True)
    assert verdict.status is Status.KEEP
    assert verdict.reason == "git failed: fatal: not a git repository"


def test_worktree_holding_the_current_directory_is_kept() -> None:
    verdict = verdict_for(contains_current_directory=True, is_forced=True)
    assert verdict.status is Status.KEEP
    assert verdict.reason == "you are standing in it"


def test_force_overrides_uncommitted_changes() -> None:
    verdict = verdict_for(changed_file_count=4, unpushed_commit_count=2, is_forced=True)
    assert verdict.status is Status.SAFE
    assert verdict.reason == "forced with --force"


def test_uncommitted_changes_are_counted_in_reason() -> None:
    verdict = verdict_for(changed_file_count=3)
    assert verdict.status is Status.KEEP
    assert verdict.reason == "uncommitted changes in 3 files"


def test_one_changed_file_is_singular() -> None:
    assert verdict_for(changed_file_count=1).reason == "uncommitted changes in 1 file"


def test_stash_on_branch_keeps_it() -> None:
    assert verdict_for(stash_count=2).reason == "2 stashes on this branch"


def test_unpushed_commits_keep_it_even_if_merged() -> None:
    verdict = verdict_for(unpushed_commit_count=3)
    assert verdict.status is Status.KEEP
    assert verdict.reason == "3 commits not pushed"


def test_recently_used_worktree_is_kept() -> None:
    verdict = verdict_for(last_used_at=NOW - timedelta(hours=5))
    assert verdict.status is Status.KEEP
    assert verdict.reason == "used today, may still be in use"


def test_idle_days_zero_does_not_keep_recent_use() -> None:
    facts = facts_with(last_used_at=NOW - timedelta(hours=5))
    assert classify_worktree(facts, NOW, idle_days=0).status is Status.SAFE


def test_use_timestamp_slightly_after_scan_start_reads_as_today() -> None:
    verdict = verdict_for(last_used_at=NOW + timedelta(milliseconds=5))
    assert verdict.reason == "used today, may still be in use"


def test_idle_days_zero_ignores_use_timestamp_after_scan_start() -> None:
    facts = facts_with(last_used_at=NOW + timedelta(milliseconds=5))
    assert classify_worktree(facts, NOW, idle_days=0).status is Status.SAFE


def test_old_last_commit_alone_never_makes_it_safe() -> None:
    verdict = verdict_for(
        merge_checks=(THREE_COMMITS_NOT_IN_MAIN,), last_commit_at=NOW - timedelta(days=900)
    )
    assert verdict.status is Status.KEEP
    assert verdict.reason == "3 commits not in origin/main"


def test_squash_merge_proven_by_patch_id() -> None:
    squashed = replace(
        THREE_COMMITS_NOT_IN_MAIN,
        branch_diff_patch_id="p1",
        target_commit_patch_ids=frozenset({"p0", "p1"}),
    )
    verdict = verdict_for(merge_checks=(squashed,))
    assert verdict.status is Status.SAFE
    assert verdict.reason == "merged into origin/main"


def test_patch_id_missing_from_target_is_not_merged() -> None:
    not_squashed = replace(
        THREE_COMMITS_NOT_IN_MAIN,
        branch_diff_patch_id="p1",
        target_commit_patch_ids=frozenset({"p0"}),
    )
    assert verdict_for(merge_checks=(not_squashed,)).status is Status.KEEP


def test_branch_without_own_commits_is_safe() -> None:
    nothing_ahead = MergeCheck(
        target_branch="origin/main", commits_ahead=0, commits_not_in_target=0
    )
    verdict = verdict_for(merge_checks=(nothing_ahead,))
    assert verdict.status is Status.SAFE
    assert verdict.reason == "already in origin/main"


def test_any_target_can_prove_merge() -> None:
    merged_into_dev = MergeCheck(
        target_branch="origin/dev", commits_ahead=1, commits_not_in_target=0
    )
    verdict = verdict_for(merge_checks=(THREE_COMMITS_NOT_IN_MAIN, merged_into_dev))
    assert verdict.reason == "merged into origin/dev"


def test_reason_names_the_closest_target() -> None:
    one_commit_not_in_dev = MergeCheck(
        target_branch="origin/dev", commits_ahead=3, commits_not_in_target=1
    )
    verdict = verdict_for(merge_checks=(THREE_COMMITS_NOT_IN_MAIN, one_commit_not_in_dev))
    assert verdict.reason == "1 commit not in origin/dev"


def test_no_target_means_keep() -> None:
    verdict = verdict_for(merge_checks=())
    assert verdict.status is Status.KEEP
    assert "--target" in verdict.reason


def test_detached_head_is_classified_like_a_branch() -> None:
    verdict = verdict_for(worktree=worktree_with(branch=None, is_detached=True))
    assert verdict.status is Status.SAFE
    assert verdict.branch is None
