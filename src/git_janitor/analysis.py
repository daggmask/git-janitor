from datetime import datetime, timedelta

from git_janitor.models import MergeCheck, Status, Verdict, WorktreeFacts


def classify_worktree(facts: WorktreeFacts, now: datetime, idle_days: int) -> Verdict:
    status, reason = _status_and_reason(facts, now, idle_days)
    return Verdict(
        path=facts.worktree.path,
        main_worktree_path=facts.worktree.main_worktree_path,
        branch=facts.worktree.branch,
        status=status,
        reason=reason,
        last_commit_at=facts.last_commit_at,
    )


def _status_and_reason(facts: WorktreeFacts, now: datetime, idle_days: int) -> tuple[Status, str]:
    worktree = facts.worktree
    if worktree.is_main:
        return Status.KEEP, "main working tree"
    if not facts.folder_exists:
        return Status.ZOMBIE, "folder is gone, prune the worktree entry"
    if worktree.is_locked:
        return Status.KEEP, "worktree is locked"
    if facts.contains_current_directory:
        return Status.KEEP, "you are standing in it"
    if facts.is_forced:
        return Status.SAFE, "forced with --force"
    if facts.changed_file_count:
        changed_files = _count_with_noun(facts.changed_file_count, "file")
        return Status.KEEP, f"uncommitted changes in {changed_files}"
    if facts.stash_count:
        stashes = _count_with_noun(facts.stash_count, "stash", "stashes")
        return Status.KEEP, f"{stashes} on this branch"
    if facts.unpushed_commit_count:
        unpushed_commits = _count_with_noun(facts.unpushed_commit_count, "commit")
        return Status.KEEP, f"{unpushed_commits} not pushed"
    if _is_recently_used(facts.last_used_at, now, idle_days):
        return Status.KEEP, f"used {_age_in_words(facts.last_used_at, now)}, may still be in use"
    return _status_from_merge_checks(facts.merge_checks)


def _status_from_merge_checks(merge_checks: tuple[MergeCheck, ...]) -> tuple[Status, str]:
    if not merge_checks:
        return Status.KEEP, "no target branch to check against, use --target"
    for check in merge_checks:
        if check.commits_ahead == 0:
            return Status.SAFE, f"already in {check.target_branch}"
        if is_proven_merged(check):
            return Status.SAFE, f"merged into {check.target_branch}"
    nearest = min(merge_checks, key=lambda check: check.commits_not_in_target)
    missing_commits = _count_with_noun(nearest.commits_not_in_target, "commit")
    return Status.KEEP, f"{missing_commits} not in {nearest.target_branch}"


def is_proven_merged(check: MergeCheck) -> bool:
    if check.commits_not_in_target == 0:
        return True
    squash_patch_id = check.branch_diff_patch_id
    return squash_patch_id is not None and squash_patch_id in check.target_commit_patch_ids


def _is_recently_used(last_used_at: datetime | None, now: datetime, idle_days: int) -> bool:
    if last_used_at is None or idle_days == 0:
        return False
    return now - last_used_at < timedelta(days=idle_days)


def _age_in_words(moment: datetime | None, now: datetime) -> str:
    if moment is None:
        return "never"
    days = (now - moment).days
    if days < 1:
        return "today"
    return f"{_count_with_noun(days, 'day')} ago"


def _count_with_noun(count: int, singular: str, plural: str | None = None) -> str:
    return f"{count} {singular if count == 1 else plural or singular + 's'}"
