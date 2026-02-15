# Task 18 — Sonar skip-unchanged and rule authoring docs

## Objective
Add safe Sonar de-dup behavior and improve rule authoring guidance.

## Implementation changes
- Added Sonar scan de-dup support in [src/git_workspace_tool/rules/sonar_scan.py](../src/git_workspace_tool/rules/sonar_scan.py):
  - Tracks scanned repository revision (`git rev-parse HEAD`)
  - Stores state in per-repo state file (default: `.git/gitoteko_sonar_state.json`)
  - Skips scan when the same revision was already scanned successfully
  - Supports force override
- Added runtime config wiring in [src/git_workspace_tool/cli/main.py](../src/git_workspace_tool/cli/main.py):
  - `SONAR_SKIP_UNCHANGED`
  - `SONAR_FORCE_SCAN`
  - `SONAR_STATE_FILE`
- Updated [README.md](../README.md) with architecture/strategy notes and Sonar de-dup controls.
- Added authoring guide in [docs/adding_new_rules.md](adding_new_rules.md).
- Updated [.env.example](../.env.example) with new Sonar controls.

## Why acceptable
This avoids duplicate Sonar submissions for unchanged repositories while preserving explicit override controls. Documentation now explains how rules are designed and added under the project’s architecture constraints.
