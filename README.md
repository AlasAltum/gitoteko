# Git Workspace Tool

Python CLI for scanning a Git provider workspace and running pluggable per-repository actions.

Rules are implemented with a hexagonal architecture boundary and a strategy pattern:

- Hexagonal boundary: core scanner orchestration is provider/rule agnostic.
- Strategy pattern: each rule is an `Action` strategy injected into `ActionPipeline`.

## Requirements

- Python virtual environment available at `.venv`
- Git + SSH access configured for the target provider (Github, Bitbucket, Gitlab)
- Environment values configured in `.env`

## Core behavior

The scanner:

1. Lists repositories from a workspace
2. Clones missing repositories into `BASE_DIR`
3. Pulls existing repositories from `BASE_DIR`
4. Executes configured actions in order (`GIT_ACTIONS`)

Repositories are cached in `BASE_DIR` and are not auto-deleted.

## Quick start

From repository root:

```bash
set -a && source .env && set +a
PYTHONPATH=src .venv/bin/python -m git_workspace_tool --dry-run
```

## Real run sample (first 3 repositories)

```bash
set -a && source .env && set +a
PYTHONPATH=src .venv/bin/python -m git_workspace_tool \
	--max-repos 3 \
	--repo-selection first
```

## Action pipeline configuration

Actions are configured through `GIT_ACTIONS` (comma-separated):

```bash
export GIT_ACTIONS="detect-languages,generate-sonar-properties,run-sonar-scan"
```

Optional CSV reporting:

```bash
export GIT_ACTIONS="detect-languages,write-language-csv,generate-sonar-properties,run-sonar-scan"
```


Supported action names:

- `detect-languages`
- `write-language-csv`
- `generate-sonar-properties`
- `run-sonar-scan`

## SonarQube (remote) execution controls

Use remote host URL only (no endpoint suffix):

```bash
export SONARQUBE_URL="https://<your-sonarqube-host>"
export SONARQUBE_TOKEN="<token>"
```

Backpressure controls to avoid 

```bash
export SONAR_WAIT_MODE=sync
export SONAR_SUBMISSION_DELAY_SECONDS=10
export SONAR_SYNC_POLL_INTERVAL_SECONDS=5
export SONAR_SYNC_TIMEOUT_SECONDS=1800
```

- `SONAR_WAIT_MODE=sync`: waits for CE task completion per repo.
- `SONAR_WAIT_MODE=async`: submits scan and continues.

De-dup controls (avoid scanning unchanged repositories twice):

```bash
export SONAR_SKIP_UNCHANGED=true
export SONAR_FORCE_SCAN=false
export SONAR_STATE_FILE=.git/gitoteko_sonar_state.json
```

- `SONAR_SKIP_UNCHANGED=true`: skip scan if the same repo revision was already scanned successfully.
- `SONAR_FORCE_SCAN=true`: force scan even when revision did not change.
- `SONAR_STATE_FILE`: per-repo state file path (relative to repo root).

## Failure policy

By default, repository failures do not stop the batch.

To stop on first failure:

```bash
export GIT_STOP_ON_ERROR=true
```


## Additional docs

- [Prompt/spec](docs/prompt.md)
- [How to add a new rule](docs/adding_new_rules.md)
