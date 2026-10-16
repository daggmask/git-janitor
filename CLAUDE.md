# CLAUDE.md

## What this is

`git-janitor` is a command line tool that finds old git worktrees and local clones on your machine and cleans them up safely.

The problem: working ticket by ticket leaves a trail of `repo-FP-314`, `repo-FP-843`, `repo-perf` folders and worktrees. After a few months nobody remembers which ones are merged, which have uncommitted work and which still have commits that were never pushed. Deleting by hand is slow and risky, so the folders pile up and eat disk. The tool answers one question per folder: is it safe to delete, and if not, why not.

It runs as `git janitor` (git picks up any `git-*` executable on the PATH) and ships on PyPI, so anyone can install it with `pipx install git-janitor` or `uv tool install git-janitor`.

## Stack

- Python 3.11+. Runs the same on Windows, macOS and Linux, and pipx/uv give users an isolated install with one command.
- Typer for the CLI. Commands are plain typed functions and help text comes for free.
- Rich for tables and the interactive pick list. Already pulled in by Typer, so no extra weight.
- The `git` CLI itself, called through `subprocess` with `--porcelain` output where it exists. Not GitPython or pygit2: worktree support is thin there, and they don't always agree with the user's own git about config, credentials or hooks.
- pytest for tests. Integration tests build real throwaway repositories in `tmp_path`.
- ruff for lint and format, mypy in strict mode for types.
- hatchling as build backend, configured in `pyproject.toml`. No `setup.py`.

## Layout

```
src/git_janitor/
  cli.py            Typer app, parsing and output only
  analysis.py       pure logic: given repo facts, decide status and reason
  git.py            everything that starts a git process
  fs.py             everything that scans or deletes folders
  models.py         dataclasses passed between the layers
tests/
  test_analysis.py  unit tests, no git, no disk
  test_git.py       integration tests against temp repos
```

## Commands

```bash
python -m venv .venv && .venv/Scripts/activate   # source .venv/bin/activate on macOS/Linux
pip install -e ".[dev]"
pytest
ruff check . && ruff format --check .
mypy src
git janitor scan C:/Repo
python -m build                                  # sdist and wheel for PyPI
```

## Architecture principles

- All I/O goes through `git.py` and `fs.py`. `analysis.py` takes dataclasses in and returns dataclasses out, never runs a process or touches the disk. That is what keeps it testable.
- One git call per question. A function like `ahead_count()` runs one command and parses one output. No function that both runs git and decides what the answer means.
- Parse porcelain output, never human output. `git worktree list --porcelain`, `git status --porcelain=v2`, `for-each-ref --format`. Human output changes between git versions and locales.
- Every status the tool reports has a reason the user can read: "3 commits not pushed", "uncommitted changes in 2 files", "branch merged into main". No bare "unsafe".
- No module-level mutable state. No globals that get reassigned, no singletons. Pass what a function needs as arguments.
- Functions do one thing. If a function needs comments to explain its sections, split it.
- Type hints on everything public. Frozen dataclasses for data that crosses a layer.
- `subprocess.run` with a list of arguments, never `shell=True`, always `check=True` or an explicit return code check, and `encoding="utf-8"`.
- Output for scripts is a separate flag (`--json`), not something parsed out of the table.

## Safety rules for the tool itself

These are product requirements, not style. Don't weaken them.

- Dry run is the default. Nothing is deleted without `--delete` or an explicit confirm in interactive mode.
- Never delete a folder with uncommitted changes, untracked files, stashes or commits that don't exist on any remote. `--force` exists but has to be per folder, never global.
- Worktrees are removed with `git worktree remove`, not by deleting the folder, so the main repo's metadata stays consistent.
- Never touch the main working tree of a repository, only linked worktrees and separate clones.
- Squash and rebase merges count as merged only when the branch's changes are proven to be in the target (`git cherry` or patch-id), never on name or age alone.

## Don't

- Don't add dependencies beyond the ones listed above without asking. The standard library covers most things here.
- Don't replace the git CLI with GitPython, pygit2 or another library.
- Don't add network calls (GitHub API, telemetry, update checks) without asking. The tool should work offline.
- Don't change the default from dry run to delete, and don't loosen any of the safety rules above.
- Don't write tests that run against real repositories on this machine. Use temp repos created in the test.
- Don't commit or push unless asked.
