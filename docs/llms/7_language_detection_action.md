# Task 7 — Language Detection Action

## Objective

Implement a pluggable rule action that scans a local repository and detects configured programming language extensions.

## What was implemented (high level)

Files added:
- `src/git_workspace_tool/rules/__init__.py`
- `src/git_workspace_tool/rules/language_detection.py`

Main behavior (`DetectLanguagesAction`):
1. Accepts configured extensions in constructor.
2. Normalizes extensions (lowercase, ensures leading dot, removes duplicates).
3. Recursively scans repository files under `RepoContext.local_path`.
4. Ignores files inside `.git`.
5. Detects matching extensions and stores them in `RepoContext.detected_extensions`.
6. Returns `ActionResult` with:
   - success flag,
   - count summary message,
   - metadata containing sorted detected extensions.

If no extensions are configured, returns a failed `ActionResult` with a clear message.

## How we verified it

A local temporary repository structure test was executed:
- created files: `.py`, `.ts`, `.md`, and `.git/config`;
- configured action extensions with mixed input (`py`, `.ts`, duplicated values);
- executed action with `RepoContext`.

Validated:
- only configured extensions were detected (`.py`, `.ts`),
- `.md` was ignored,
- `.git` content was ignored,
- deduplication and normalization worked,
- action result metadata matched expected sorted extensions.

Observed result: test passed.

## Why this is acceptable

- Satisfies Task 7 acceptance criteria:
  - recursive scan,
  - dedup + normalization,
  - context update for downstream actions.
- Keeps behavior as a pluggable rule action, not core orchestration logic.
- Prepares for Task 8 (CSV reporting) which consumes detected extensions from context.
