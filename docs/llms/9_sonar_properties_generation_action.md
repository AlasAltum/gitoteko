# Task 9 — Sonar Properties Generation Action

## Objective

Implement a pluggable rule action that creates `sonar-project.properties` at repository root using a deterministic language template selection based on detected extensions.

## What was implemented (high level)

Files changed:
- `src/git_workspace_tool/rules/sonar_properties.py` (new)
- `src/git_workspace_tool/rules/__init__.py`

Main behavior (`GenerateSonarPropertiesAction`):
1. Chooses language template by priority:
   - Java (`.java`)
   - TypeScript (`.ts`)
   - JavaScript (`.js`)
   - Python (`.py`)
   - fallback generic
2. Writes `sonar-project.properties` with required keys:
   - `sonar.projectKey`
   - `sonar.projectName`
   - `sonar.sources=.`
   - `sonar.sourceEncoding=UTF-8`
3. Java template includes:
   - `sonar.java.binaries` (configurable path, default `target/classes`)
4. Existing file behavior:
   - default: skip
   - overwrite mode: replace content
5. Returns structured `ActionResult` metadata (`written`, `language_template`, `path`).

## How we verified it

Executed local temporary-directory tests:
1. With `{.ts, .java}` detected extensions:
   - Java template selected,
   - required keys present,
   - Java binaries key present.
2. Re-running with default mode:
   - existing file skipped.
3. Running with overwrite and `{.py}`:
   - file rewritten,
   - Python template selected,
   - Java binaries key removed.

Observed result: test passed.

## Why this is acceptable

- Meets Task 9 requirements for deterministic template selection and file generation behavior.
- Keeps sonar file generation as a pluggable rule action, preserving core orchestration boundaries.
- Provides predictable output for subsequent scanner execution tasks.
