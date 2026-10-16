from git_janitor.models import Status, Verdict, WorktreeFacts


def classify(facts: WorktreeFacts) -> Verdict:
    status, reason = _decide(facts)
    return Verdict(
        path=facts.entry.path,
        branch=facts.entry.branch,
        status=status,
        reason=reason,
        last_commit_at=facts.last_commit_at,
    )


def _decide(facts: WorktreeFacts) -> tuple[Status, str]:
    entry = facts.entry
    if entry.is_main:
        return Status.KEEP, "main working tree"
    if not facts.exists:
        return Status.ZOMBIE, "folder is gone, prune the worktree entry"
    if entry.locked:
        return Status.KEEP, "worktree is locked"
    if facts.changed_files:
        return Status.KEEP, f"uncommitted changes in {_files(facts.changed_files)}"
    if entry.detached:
        return Status.KEEP, "detached HEAD, merge not checked"
    return Status.KEEP, "merge status not checked yet"


def _files(count: int) -> str:
    return "1 file" if count == 1 else f"{count} files"
