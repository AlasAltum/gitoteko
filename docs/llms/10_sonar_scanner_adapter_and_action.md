# Task 10 — Sonar Scanner Adapter and Execution Action

## Objective

Implement SonarScanner execution in two layers:
1. adapter that runs `sonar-scanner` shell command,
2. pluggable rule action that resolves Sonar config and executes scan per repository.

## What was implemented (high level)

Files changed:
- `src/git_workspace_tool/rules/sonar_runtime.py`
- `src/git_workspace_tool/rules/sonar_scan.py` (new)
- `src/git_workspace_tool/rules/__init__.py`
- `src/git_workspace_tool/adapters/sonar/shell_sonar_scanner.py` (compatibility shim)

### Rule runtime adapter (`ShellSonarScannerRunner`)
- Executes:
  - `sonar-scanner -Dsonar.host.url=<url> -Dsonar.token=<token>`
- Runs from repo root (`cwd=repo_path`).
- Captures and returns `(exit_code, stdout, stderr)`.
- Raises clear runtime errors for:
  - missing scanner binary,
  - timeout.

### Rule (`RunSonarScannerAction`)
- Uses `SonarScannerRunner` dependency (rules-layer contract, adapter injected).
- Resolves Sonar config with precedence:
  1) constructor args,
  2) env URL: `SONARQUBE_URL` or `SONAR_HOST_URL`,
  3) env token: `SONARQUBE_TOKEN` or `SONAR_TOKEN`.
- Returns failed `ActionResult` when URL/token is missing.
- Stores scan summary in metadata:
  - `exit_code`, `stdout`, `stderr`, `analysis_url` (when parsable), `repo_slug`.
- Success is based on `exit_code == 0`.

## How we verified it

Two local tests were executed:
1. Adapter command-construction test with fake subprocess runner:
   - verified command args, cwd, and returned outputs.
2. Rule action behavior test with fake scanner port:
   - verified env-based config resolution,
   - verified success metadata and parsed analysis URL,
   - verified failure when Sonar URL/token missing.

Observed result: both tests passed.

## Why this is acceptable

- Meets Task 10 requirements for scanner execution + captured output.
- Keeps core/rule boundaries clean:
  - scanner execution logic in rules runtime adapter,
  - configuration and per-repo semantics in rule action.
- Ready for composition into action pipelines in later integration tasks.
