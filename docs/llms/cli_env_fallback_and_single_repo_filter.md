# CLI Env Fallback and Single-Repository Filter

## Objective

Improve testability and ergonomics by:
1. allowing core CLI arguments to be sourced from environment variables,
2. supporting safe execution targeting one repository slug,
3. supporting controlled partial runs with repository limits.

## What was implemented (high level)

Files changed:
- `src/git_workspace_tool/cli/config.py`
- `src/git_workspace_tool/cli/main.py`
- `src/git_workspace_tool/application/use_cases/git_workspace_scanner.py`
- `.env.example`

### Environment fallback for core args
Core values now resolve from CLI first, then environment:
- `provider` <- `--provider` or `GIT_PROVIDER`
- `workspace` <- `--workspace` or `GIT_WORKSPACE`
- `base_dir` <- `--base-dir` or `BASE_DIR`

Validation errors are raised when required values are still missing.

### Single-repository filter
- New optional input: `--repo-slug` (or `GIT_REPO_SLUG`).
- Use case supports `only_repo_slug` to process/list one repository only.
- Useful for dry-run and incremental testing without touching all repos.

### Controlled partial runs
- New optional limit input: `--max-repos` (or `GIT_MAX_REPOS`).
- Selection mode: `--repo-selection first|random` (or `GIT_REPO_SELECTION`).
- Optional deterministic seed: `--random-seed` (or `GIT_RANDOM_SEED`).
- Enables safe testing with first/random N repositories.

### Environment template
- Added `.env.example` with all core/provider/rule-related env vars and placeholders.

## How we verified it

- CLI help still renders successfully.
- Dry-run supports repo filtering via `--repo-slug` / env.
- Existing behavior remains unchanged when filter is omitted.

## Why this is acceptable

- Keeps core/rule boundary intact.
- Enables safer, faster testing in large workspaces.
- Documents expected environment configuration clearly for future contributors.
