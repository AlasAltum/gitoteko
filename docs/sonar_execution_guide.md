# Sonar execution guide

This tool supports three Sonar execution modes. The SonarQube server can be remote/self-hosted in all cases.

## 1) `SONAR_EXECUTION_MODE=local` (default)

- What happens:
  - The CLI runs `sonar-scanner` on the same machine where you run `git_workspace_tool`.
  - The scanner sends analysis to `SONARQUBE_URL` (remote server).
- Required:
  - `SONARQUBE_URL`
  - `SONARQUBE_TOKEN`
  - A scanner binary in PATH or `SONAR_SCANNER_EXECUTABLE` pointing to it.
- Use this when:
  - You want on-demand scans from CLI.
  - Repositories do not have CI Sonar pipeline steps.

## 2) `SONAR_EXECUTION_MODE=cloud`

- What happens:
  - The CLI only queries Sonar server APIs (status/quality gate style checks).
  - It does **not** submit new analyses.
- Required:
  - `SONARQUBE_URL`
  - `SONARQUBE_TOKEN`
- Use this when:
  - You only need to inspect existing Sonar state/results.

## 3) `SONAR_EXECUTION_MODE=ci`

- What happens:
  - The CLI triggers remote CI pipeline execution (Bitbucket pipelines).
  - Scanner runs in CI/runner, not on your laptop.
- Required:
  - CI pipeline definitions in each repository.
  - Bitbucket auth with permission to trigger pipelines.

Optional enforcement controls:

- `SONAR_CI_VERIFY_SONAR_STEP=true` (default): inspect triggered pipeline steps and verify a Sonar step exists.
- `SONAR_CI_SONAR_SELECTOR=sonar-scan` (default): fallback selector triggered automatically when initial pipeline does not contain a Sonar step.

If no Sonar step is found after fallback, the action fails for that repository.

## "local" meaning

It means the **scanner client** runs locally; the SonarQube instance can still be fully remote/self-hosted.

## Java vs non-Java repositories

- Not all repositories need Java settings.
- The generated `sonar-project.properties` only sets `sonar.java.binaries` when Java files are detected.
- If Java repos fail because binaries path does not exist, use:

```bash
export SONAR_PROPERTIES_OVERWRITE=true
export SONAR_JAVA_BINARIES_PATH=.
```

This is a practical fallback for mixed repositories when compiled classes are unavailable.

## Recommended env for on-demand CLI scans

```bash
export SONAR_EXECUTION_MODE=local
export SONAR_SCANNER_EXECUTABLE=/absolute/path/to/sonar-scanner
export SONAR_PROPERTIES_OVERWRITE=true
export SONAR_JAVA_BINARIES_PATH=.
```

Then run:

```bash
set -a && source .env && set +a
PYTHONPATH=src .venv/bin/python -m git_workspace_tool --max-repos 10 --repo-selection first
```
