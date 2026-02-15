# Task 12 — Logging, error policy, and run summary

## Objective
Improve run observability and control behavior when repository processing fails.

## High-level changes
- Extended per-repository summary with:
  - `success`
  - `error`
- Extended scan summary with:
  - `successful_repositories`
  - `failed_repositories`
- Added repository-level exception handling in scanner execution.
- Added stop policy toggle:
  - `GIT_STOP_ON_ERROR=false` (default): continue processing next repositories.
  - `GIT_STOP_ON_ERROR=true`: stop after first failed repository.
- Enhanced CLI output to include success/failed totals and per-repo status.

## Files changed
- `src/git_workspace_tool/application/use_cases/git_workspace_scanner.py`
- `src/git_workspace_tool/cli/main.py`

## Verification performed
- Static error check reports no issues on modified files.

## Why acceptable
The scanner now supports an explicit and predictable failure policy while preserving the default resilient behavior for batch runs. Run summaries are clearer for operators and easier to review after large executions.
