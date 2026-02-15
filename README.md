# Gitoteko - Git Workspace Tool

Python CLI for scanning a Git provider workspace (GitHub, Bitbucket, GitLab) and running pluggable per-repository actions across **all repositories** in that workspace.

Use cases:
- Apply code quality rules (SonarQube scans) to all repositories
- Detect programming languages across your organization's codebase
- Generate reports or perform batch operations on multiple repositories
- Migrate repositories from one provider to another

Rules are implemented with a hexagonal architecture boundary and a strategy pattern:

- Hexagonal boundary: core scanner orchestration is provider/rule agnostic.
- Strategy pattern: each rule is an `Action` strategy injected into `ActionPipeline`.

## Requirements

- Python 3.11 or higher
- Git CLI installed and available in PATH
- SSH access configured for the target provider (GitHub, Bitbucket, GitLab)
  - SSH keys already set up for repository cloning
- No external Python dependencies (uses standard library only)

## Core behavior

The scanner:

1. Lists repositories from a workspace
2. Clones missing repositories into `BASE_DIR`
3. Pulls existing repositories from `BASE_DIR`
4. Executes configured actions in order (`GIT_ACTIONS`)

Repositories are cached in `BASE_DIR` and are not auto-deleted.

## Setup

1. Clone this repository:
```bash
git clone https://github.com/AlasAltum/gitoteko.git
cd gitoteko
```

2. Create Python virtual environment:
```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install the package in editable mode:
```bash
pip install -e .
```

4. Copy and configure environment file:
```bash
cp .env.example .env
# Edit .env with your credentials:
# - BITBUCKET_TOKEN or BITBUCKET_USERNAME/BITBUCKET_APP_PASSWORD
# - GIT_WORKSPACE (your organization/workspace name)
# - BASE_DIR (where repositories will be cloned)
# - SONARQUBE_URL and SONARQUBE_TOKEN (if using Sonar scans)
```

## Quick start

Dry-run (lists repositories without cloning):

```bash
set -a && source .env && set +a
PYTHONPATH=src .venv/bin/python -m git_workspace_tool --dry-run
```

## Real run examples

**Test run with first 3 repositories** (useful when analyzing a whole workspace with many repos):

```bash
set -a && source .env && set +a
PYTHONPATH=src .venv/bin/python -m git_workspace_tool \
	--max-repos 3 \
	--repo-selection first
```

**Full workspace scan** (all repositories):

```bash
set -a && source .env && set +a
PYTHONPATH=src .venv/bin/python -m git_workspace_tool
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

## SonarQube (remote) execution controls for code scanning

Use remote host URL only (no endpoint suffix):

```bash
export SONARQUBE_URL="https://<your-sonarqube-host>"
export SONARQUBE_TOKEN="<token>"
```

Backpressure controls to avoid overloading SonarQube server:

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
