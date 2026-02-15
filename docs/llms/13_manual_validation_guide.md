# Task 13 — Manual validation guide (human-centered)

## Objective
Provide a practical, repeatable manual verification flow from a clean session to real workspace execution.

## Prerequisites
- Linux/WSL shell with git and Python available.
- Workspace cloned locally and terminal opened at repository root.
- Bitbucket SSH access configured.
- Remote SonarQube URL/token available.

## 1) Environment setup
From project root:

```bash
cd <your-repo-root>
set -a && source .env && set +a
```

Minimum required environment values:
- `GIT_PROVIDER=bitbucket`
- `GIT_WORKSPACE=<workspace>`
- `BASE_DIR=<local-repo-cache-dir>`
- `BITBUCKET_TOKEN` (or `BITBUCKET_USERNAME` + `BITBUCKET_APP_PASSWORD`)

For Sonar rule execution:
- `SONARQUBE_URL=https://<remote-sonarqube-host>`
- `SONARQUBE_TOKEN=<token>`

## 2) Dry-run validation (no side effects)

```bash
PYTHONPATH=src .venv/bin/python -m git_workspace_tool --dry-run
```

Expected:
- Workspace repositories are listed.
- Summary shows planned clone/pull operations.
- No local repository changes are made.

## 3) Real sync validation (small sample)
Use first 3 repositories into a test cache directory:

```bash
PYTHONPATH=src .venv/bin/python -m git_workspace_tool \
  --base-dir /tmp/gitoteko-test \
  --max-repos 3 \
  --repo-selection first
```

Expected:
- First run: mostly `clone`.
- Second run: same repos switch to `pull`.
- Summary includes successful/failed repository counts.

## 4) Rule pipeline activation
Enable rule actions with env-based composition:

```bash
export GIT_ACTIONS="detect-languages,generate-sonar-properties,run-sonar-scan"
```

Optional language CSV report:

```bash
export GIT_ACTIONS="detect-languages,write-language-csv,generate-sonar-properties,run-sonar-scan"
```

## 5) Sonar pacing and wait-mode controls
Recommended conservative settings:

```bash
export SONAR_WAIT_MODE=sync
export SONAR_SUBMISSION_DELAY_SECONDS=10
export SONAR_SYNC_POLL_INTERVAL_SECONDS=5
export SONAR_SYNC_TIMEOUT_SECONDS=1800
```

Behavior:
- `sync`: wait for each Sonar CE task before moving to next repo.
- `async`: submit and continue (still respects submission delay).

## 6) Error policy
Default continues on repo failures. To stop immediately:

```bash
export GIT_STOP_ON_ERROR=true
```

## 7) Verification checklist
- [ ] Dry-run returns expected repo count.
- [ ] Real run creates or updates repositories under `BASE_DIR`.
- [ ] `GIT_ACTIONS` controls which actions execute.
- [ ] Sonar uses remote URL (host only, no endpoint suffix in config).
- [ ] Summary clearly reports successful and failed repositories.
- [ ] With `GIT_STOP_ON_ERROR=true`, processing stops on first failure.

## 8) Common troubleshooting
- No repositories listed:
  - Verify Bitbucket auth env values and workspace permissions.
- `sonar-scanner` not found:
  - Install scanner on host or configure scanner runtime accordingly.
- Sonar scan submitted but not visible immediately:
  - Wait for CE task processing and verify project key/branch context.
- Existing repos not found:
  - Check `BASE_DIR` value in `.env` and runtime command overrides.

## Why this guide is acceptable
It documents exact operator steps for dry-run, controlled real execution, remote Sonar usage, pacing, and failure policy with minimal ambiguity for first-time and repeat validations.
