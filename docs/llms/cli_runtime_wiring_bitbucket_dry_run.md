# CLI Runtime Wiring — Bitbucket Dry-Run Listing

## Objective

Wire the CLI entrypoint to the core use case so we can perform a real Bitbucket workspace dry-run listing without cloning repositories.

## What was implemented (high level)

Files changed:
- `src/git_workspace_tool/cli/config.py`
- `src/git_workspace_tool/cli/main.py`

Key changes:
1. Core runtime config now includes Bitbucket provider auth/runtime options from environment:
   - `BITBUCKET_TOKEN`
   - `BITBUCKET_USERNAME`
   - `BITBUCKET_APP_PASSWORD`
   - optional `BITBUCKET_API_BASE_URL`
   - optional `BITBUCKET_TIMEOUT_SECONDS`
2. CLI now builds and executes the runtime graph:
   - `BitbucketCloudGitProviderAdapter`
   - `ShellGitClientAdapter`
   - `LocalFileSystemAdapter`
   - `ActionPipeline([])` (no rules in core by default)
   - `GitWorkspaceScanner`
3. CLI prints a run summary including:
   - mode (`DRY-RUN`/`RUN`)
   - workspace/base dir
   - repositories discovered
   - per repo planned sync operation (`clone`/`pull`)

## How we verified it

Executed commands:
1. CLI help
2. Real dry-run with workspace `<your-workspace>`

Observed dry-run output showed scanner execution and repository discovery summary, with no cloning.

Environment check showed Bitbucket auth vars were not set in the current shell, which explains zero discovered repositories in this session.

## Why this is acceptable

- Preserves core/rule boundary:
  - core CLI runs orchestration only,
  - no rule-specific config leaked into core.
- Enables immediate real-world dry-run verification against Bitbucket listing.
- Keeps execution safe in dry-run mode (no clone/pull side effects).
