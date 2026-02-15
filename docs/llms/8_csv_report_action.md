# Task 8 — CSV Report Action (Idempotent)

## Objective

Implement a pluggable rule action that writes per-repository language detection results into a configurable CSV file with idempotent behavior.

## What was implemented (high level)

Files changed:
- `src/git_workspace_tool/rules/language_report_csv.py` (new)
- `src/git_workspace_tool/rules/__init__.py`

Main behavior (`WriteLanguageReportCsvAction`):
1. Accepts destination CSV path and idempotency mode (`regenerate`).
2. Writes rows with fields:
   - `workspace`, `repo_name`, `repo_slug`, `local_path`, `extensions`
3. Serializes extensions in deterministic order (`;` delimiter by default).
4. Default idempotency (`regenerate=False`):
   - if `workspace+repo_slug` row already exists, skip write.
5. Regenerate mode (`regenerate=True`):
   - replace existing row for same `workspace+repo_slug`.
6. Ensures parent directory exists and returns structured `ActionResult` metadata.

## How we verified it

Executed a local temporary-file test flow:
1. First execution writes one CSV row.
2. Second execution with same repo (default mode) does not duplicate row.
3. Regenerate execution replaces existing row content.

Validated outcomes:
- header and row format are correct,
- no duplicate rows in default mode,
- regenerate mode updates existing row.

Observed result: test passed.

## Why this is acceptable

- Matches Task 8 acceptance criteria from the implementation plan.
- Keeps CSV reporting as a rule action, not core orchestration logic.
- Provides deterministic and repeatable output suitable for CI/manual review.
