from datetime import datetime, timedelta

from git_janitor.models import Status, TargetCheck, Verdict, WorktreeFacts


def classify(facts: WorktreeFacts, now: datetime, idle_days: int) -> Verdict:
    status, reason = _decide(facts, now, idle_days)
    return Verdict(
        path=facts.entry.path,
        repository=facts.entry.repository,
        branch=facts.entry.branch,
        status=status,
        reason=reason,
        last_commit_at=facts.last_commit_at,
    )


def _decide(facts: WorktreeFacts, now: datetime, idle_days: int) -> tuple[Status, str]:
    entry = facts.entry
    if entry.is_main:
        return Status.KEEP, "main working tree"
    if not facts.exists:
        return Status.ZOMBIE, "folder is gone, prune the worktree entry"
    if entry.locked:
        return Status.KEEP, "worktree is locked"
    if facts.holds_cwd:
        return Status.KEEP, "you are standing in it"
    if facts.forced:
        return Status.SAFE, "forced with --force"
    if facts.changed_files:
        return Status.KEEP, f"uncommitted changes in {_plural(facts.changed_files, 'file')}"
    if facts.stashes:
        return Status.KEEP, f"{_plural(facts.stashes, 'stash', 'stashes')} on this branch"
    if facts.unpushed:
        return Status.KEEP, f"{_plural(facts.unpushed, 'commit')} not pushed"
    if _recently_used(facts.last_used_at, now, idle_days):
        return Status.KEEP, f"used {_ago(facts.last_used_at, now)}, may still be in use"
    return _merge_verdict(facts.targets)


def _merge_verdict(targets: tuple[TargetCheck, ...]) -> tuple[Status, str]:
    if not targets:
        return Status.KEEP, "no target branch to check against, use --target"
    for check in targets:
        if check.commits == 0:
            return Status.SAFE, f"already in {check.target}"
        if is_merged(check):
            return Status.SAFE, f"merged into {check.target}"
    closest = min(targets, key=lambda check: check.unmerged)
    return Status.KEEP, f"{_plural(closest.unmerged, 'commit')} not in {closest.target}"


def is_merged(check: TargetCheck) -> bool:
    if check.unmerged == 0:
        return True
    return check.branch_patch_id is not None and check.branch_patch_id in check.target_patch_ids


def _recently_used(last_used_at: datetime | None, now: datetime, idle_days: int) -> bool:
    return last_used_at is not None and now - last_used_at < timedelta(days=idle_days)


def _ago(moment: datetime | None, now: datetime) -> str:
    if moment is None:
        return "never"
    days = (now - moment).days
    if days == 0:
        return "today"
    return f"{_plural(days, 'day')} ago"


def _plural(count: int, word: str, plural: str | None = None) -> str:
    return f"{count} {word if count == 1 else plural or word + 's'}"
