# git-janitor

Find old git worktrees and local clones and tell you which ones are safe to delete.

Working ticket by ticket leaves a trail of `repo-FP-314`, `repo-perf` and friends. After a few
months nobody remembers which are merged, which have uncommitted work and which have commits that
never got pushed. `git janitor` answers that per folder, with a reason you can read.

Work in progress. Linked worktrees are handled; separate clones are listed but always kept for now.

## Install

```bash
pipx install git-janitor
```

or

```bash
uv tool install git-janitor
```

Git picks up any `git-*` executable on the PATH, so it runs as `git janitor`.

## Usage

```bash
git janitor scan C:/Repo
git janitor scan C:/Repo --target origin/main --target origin/dev
git janitor scan C:/Repo --delete
git janitor scan C:/Repo --delete --force C:/Repo/app-FP-314
```

Without `--delete` nothing is touched. With it, safe worktrees are removed in parallel with
`git worktree remove` and zombies are pruned.

A worktree is safe only when all of this holds:

- no uncommitted changes or untracked files
- no stash made on its branch
- every commit exists on a remote
- every change is in a target branch, checked with `git cherry` for merges and rebases and with
  patch-id for squash merges
- not touched in the last `--idle-days` days (default 3)
- not the folder you are standing in

Right before removal the folder is renamed and renamed back. If a program holds something open in
it (works on Windows) the folder is skipped instead of being half deleted.

`--force` takes one folder and can be repeated. It never applies to locked worktrees or the main
working tree. The age of the last commit is shown as a hint and is never a reason to delete.

Remote branches are compared as your local git last saw them. Run `git fetch --prune` first for an
up to date answer.

| Status  | Meaning |
|---------|---------|
| zombie  | git still has a worktree entry but the folder is gone. Cleaned with `git worktree prune`. |
| safe    | Proven merged, nothing uncommitted, nothing unpushed. |
| keep    | Not safe to delete. The reason column says why. |

The main working tree of a repository is never touched.

## Development

```bash
python -m venv .venv
.venv/Scripts/activate        # source .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check .
mypy src
```

## License

MIT
