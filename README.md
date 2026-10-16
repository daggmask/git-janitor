# git-janitor

Find old git worktrees and local clones and tell you which ones are safe to delete.

Working ticket by ticket leaves a trail of `repo-FP-314`, `repo-perf` and friends. After a few
months nobody remembers which are merged, which have uncommitted work and which have commits that
never got pushed. `git janitor` answers that per folder, with a reason you can read.

Work in progress. Right now `scan` lists worktrees and flags zombies and uncommitted changes.
Merge detection and deletion are coming.

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
```

Nothing is ever deleted by `scan`. Dry run is the default for every command.

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
