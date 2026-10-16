from dataclasses import replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from git_janitor.analysis import classify
from git_janitor.models import Status, WorktreeEntry, WorktreeFacts

LINKED = WorktreeEntry(
    path=Path("/repo/app-FP-1"),
    head="abc123",
    branch="feature/FP-1",
    is_main=False,
)


def entry(**overrides: Any) -> WorktreeEntry:
    return replace(LINKED, **overrides)


def facts(worktree: WorktreeEntry, exists: bool = True, changed_files: int = 0) -> WorktreeFacts:
    return WorktreeFacts(
        entry=worktree,
        exists=exists,
        changed_files=changed_files,
        last_commit_at=datetime(2026, 1, 1, tzinfo=UTC),
    )


def test_main_working_tree_is_always_kept() -> None:
    verdict = classify(facts(entry(is_main=True), changed_files=0))
    assert verdict.status is Status.KEEP
    assert verdict.reason == "main working tree"


def test_missing_folder_is_zombie() -> None:
    verdict = classify(facts(entry(prunable=True), exists=False))
    assert verdict.status is Status.ZOMBIE


def test_uncommitted_changes_are_counted_in_reason() -> None:
    verdict = classify(facts(entry(), changed_files=3))
    assert verdict.status is Status.KEEP
    assert verdict.reason == "uncommitted changes in 3 files"


def test_single_changed_file_reads_naturally() -> None:
    assert classify(facts(entry(), changed_files=1)).reason == "uncommitted changes in 1 file"


def test_locked_worktree_is_kept() -> None:
    verdict = classify(facts(entry(locked=True)))
    assert verdict.status is Status.KEEP
    assert verdict.reason == "worktree is locked"


def test_clean_worktree_is_not_called_safe_before_merge_check() -> None:
    verdict = classify(facts(entry()))
    assert verdict.status is Status.KEEP
    assert verdict.reason == "merge status not checked yet"


def test_detached_head_says_so() -> None:
    verdict = classify(facts(entry(branch=None, detached=True)))
    assert verdict.status is Status.KEEP
    assert verdict.branch is None
    assert "detached" in verdict.reason
