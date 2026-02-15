# Task 6 — Git Workspace Scanner Use Case

## Objective

Implement the core orchestration use case that:
- lists repositories in a workspace,
- decides clone vs pull per repository,
- builds `RepoContext`,
- runs the configured `ActionPipeline`,
- and supports `dry_run` without side effects.

## What was implemented (high level)

Files changed:
- `src/git_workspace_tool/application/use_cases/git_workspace_scanner.py`
- `src/git_workspace_tool/domain/ports.py`
- `src/git_workspace_tool/adapters/filesystem/local_filesystem.py`

Key changes:
1. Added execution summary models in the use case layer:
   - `RepositoryExecutionSummary`
   - `ScanExecutionSummary`

2. Updated `GitWorkspaceScanner.execute(...)` to return a summary object.
   - Includes planned action names and per-repository operation (`clone`/`pull`).

3. Implemented explicit dry-run planning behavior.
   - In dry-run mode, the use case does **not** call clone/pull, does **not** run actions, and does **not** create directories.
   - It still computes what would happen and returns that plan in summary data.

4. Removed direct filesystem checks from the use case.
   - Added `path_exists(path)` to `FileSystemPort` and implemented it in `LocalFileSystemAdapter`.
   - The use case now depends only on ports.

## How we verified it

A local in-memory orchestration test was executed with fake ports/actions:
- provider returns two repos,
- filesystem reports one existing repo and one missing repo,
- pipeline has two ordered actions.

Validated behavior:
1. Dry-run:
   - no directory creation,
   - no git commands,
   - summary contains planned operations and planned action order.

2. Normal run:
   - base directory ensured once,
   - clone called for missing repo,
   - pull called for existing repo,
   - action results are present and ordered.

Observed result: test passed.

## Why this is acceptable

- Satisfies Task 6 acceptance criteria in the implementation plan.
- Keeps boundaries clean: orchestration in use case, side effects through ports/adapters.
- Dry-run behavior is explicit and safe.
- Summary output gives a reliable base for future logging/reporting (Task 12).
