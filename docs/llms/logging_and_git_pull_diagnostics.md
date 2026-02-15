# Structured Logging and Git Pull Diagnostics

## Objective

Add structured logging and diagnose the reported clone/pull failure to confirm whether git clone is functional and fix update behavior.

## What changed

Files changed:
- `src/git_workspace_tool/logging_utils.py` (new)
- `src/git_workspace_tool/cli/main.py`
- `src/git_workspace_tool/application/use_cases/git_workspace_scanner.py`
- `src/git_workspace_tool/adapters/git_client/shell_git_client.py`

### Structured logging
- Added JSON formatter and centralized logger configuration.
- Added runtime events at CLI, scanner orchestration, and git adapter levels.
- Log output now includes structured fields such as:
  - `event`, `workspace`, `repo_slug`, `sync_operation`, `local_path`, and error details.

### Git pull behavior fix
- Previous failure reason was not clone authentication. It was pull branch tracking.
- `git pull` failed when local branch had no upstream.
- Updated pull strategy:
  1. fetch from origin,
  2. if upstream exists -> `git pull --ff-only`,
  3. otherwise fallback to:
     - `git pull --ff-only origin <current_branch>` when available, or
     - `git pull --ff-only origin <default_remote_branch>`.

## Diagnosis summary

Validation commands showed:
- SSH auth to Bitbucket works.
- `git ls-remote` for target repo works.
- Manual clone works quickly.

The earlier application error happened because the local repo already existed and entered `pull` path, then failed with:
- "There is no tracking information for the current branch."

## Verification done

1. Fresh non-dry run with one repo (`<repo-slug>`) into clean base dir:
- clone succeeded.

2. Second non-dry run on same repo path:
- pull succeeded with new fallback strategy.

Both runs were observed through structured JSON logs.

## Why this is acceptable

- Confirms clone path is functional.
- Fixes practical pull edge case in existing local repositories.
- Improves observability for future debugging and vibe coding iterations.
