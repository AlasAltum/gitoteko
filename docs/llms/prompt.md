# Base Prompt (Python) — Git Workspace Tool

You are an expert software engineer.
Use specs-driven development and vibe coding:
1) restate requirements,
2) propose design (ports/adapters),
3) implement incrementally.

## Fixed stack and style

- Language: Python (single language for this project).
- CLI approach: vanilla Python tooling first (prefer `argparse` and standard library).
- Architecture: hexagonal (ports/adapters), portable to other providers.
- Keep external dependencies minimal and justified.

## High-level goal

Build a CLI that:

1. Connects to a Git provider workspace (first provider: Bitbucket Cloud).
2. Lists all repositories in the workspace (full workspace scope).
3. Clones or updates each repository locally via SSH clone URLs.
4. Runs a configurable action pipeline per repository.

Workspace scope clarification:
- In Bitbucket Cloud, workspace is the top-level grouping.
- The tool must enumerate repositories from the full workspace scope, not only a project-filtered or UI-filtered subset.
- Result set is still bounded by the authenticated user/service permissions.

Important boundary:
- Core use case is orchestration only (list repos, clone/pull, invoke pipeline).
- Repository-level behaviors are implemented as pluggable action rules.
- The initial actions below are rule implementations, not core logic.

Initial rule actions (executed per repository):

- Detect repository languages from file extensions.
- Write language summary to CSV.
- Generate `sonar-project.properties` from language templates.
- Run `sonar-scanner` and record a per-repo result summary.

## Functional scope

### 1) Git providers and use case

Domain use case: `GitWorkspaceScanner`

Inputs:
- `workspace` identifier
- `base_dir` local path
- configured action pipeline

Behavior:
- list repositories in workspace
- ensure local clone/update for each repo
- execute actions sequentially per repo

Core ports:
- `GitProviderPort`
  - `list_repositories(workspace) -> list[Repository]`
  - `get_clone_url(repo) -> str`
- `GitClientPort`
  - `clone(url, local_path)`
  - `pull(local_path)`

Bitbucket adapter (first implementation):
- Use Bitbucket Cloud API `GET /2.0/repositories/{workspace}` (handle pagination).
- Prefer SSH clone URL for cloning.
- Do not apply project-level filtering unless explicitly requested by CLI flags.
- Assume credentials are already configured via SSH key in OS/WSL.

### 2) Repository clone/update behavior

- Ensure base directory exists.
- Compute local repo path as `<base_dir>/<repo_slug>` (sanitize as needed).
- If missing: clone.
- If exists: pull (simple mode acceptable).

### 3) Action pipeline pattern

Define:
- `Action` interface: `execute(repo_context) -> ActionResult`
- `RepoContext` containing workspace, repo metadata, local path, detected languages, and mutable metadata.
- `ActionPipeline` executing actions in order.

Boundary rule:
- `GitWorkspaceScanner` must not hardcode language detection, CSV writing, sonar file generation, or sonar scan execution.
- Those behaviors must be injected as `Action` implementations in the pipeline.

Output of each action must be available to subsequent actions through `RepoContext`.

Class and public method input contracts (must be documented in code):
- `Repository(name, slug, clone_url)`
  - `name`: human-readable repo name
  - `slug`: stable identifier for local folder naming
  - `clone_url`: cloneable URL (SSH preferred)
- `RepoContext(workspace_id, repository, local_path, ...)`
  - `workspace_id`: workspace identifier string
  - `repository`: `Repository` instance for current execution
  - `local_path`: local repo path to read/write
  - `detected_extensions` and `metadata` are mutable outputs for action chaining
- `Action.execute(repo_context)`
  - input: mutable `RepoContext`
  - output: `ActionResult`
- `ActionPipeline(actions)`
  - input: ordered `Action` sequence
  - behavior: execute in order, pass same `RepoContext`, collect ordered `ActionResult` list
- `GitProviderPort.list_repositories(workspace)`
  - input: workspace id
  - output: full workspace repository list (subject to permissions)
- `GitProviderPort.get_clone_url(repository)`
  - input: `Repository`
  - output: clone URL string
- `GitClientPort.clone(clone_url, local_path)`
  - inputs: clone URL + target local path
- `GitClientPort.pull(local_path)`
  - input: existing local repository path
- `FileSystemPort.ensure_directory(path)` / `path_exists(path)` / `list_files_recursive(path)`
  - inputs: filesystem paths used by orchestration/rules
- `DetectLanguagesAction(extensions)`
  - input: iterable of extensions (with or without `.`)
  - `execute(repo_context)` scans `repo_context.local_path`, updates `repo_context.detected_extensions`

### 4) Action: language detection + CSV

Config sources:
- env `LANGUAGE_DETECTION_EXTENSIONS` (default `.py,.ts,.js,.java,...` as configured by runtime)

Behavior:
- recursive scan of repo files
- match configured extensions
- deduplicate per repo
- write CSV row with fields:
  - workspace, repo_name, repo_slug, local_path, extensions

CSV path config:
- env `LANGUAGE_REPORT_CSV` (default `<base_dir>/language_report.csv`)
- optional `LANGUAGE_REPORT_REGENERATE` controls replacement/skip behavior

Idempotency:
- avoid duplicate rows for same repo on rerun, or allow explicit regenerate mode.

### 5) Action: generate sonar-project.properties

Language template support (minimum):
- `.java` -> Java template
- `.ts` -> TypeScript template
- `.js` -> JavaScript template
- `.py` -> Python template

Deterministic priority if multiple languages:
1. Java
2. TypeScript
3. JavaScript
4. Python

Behavior:
- create `sonar-project.properties` in repo root when missing
- default behavior when file exists: skip
- optional flag to overwrite (or backup+overwrite)

Minimum properties:
- `sonar.projectKey=<workspace>_<repoSlug>`
- `sonar.projectName=<repo name>`
- `sonar.sources=.`
- `sonar.sourceEncoding=UTF-8`

Java template:
- include `sonar.java.binaries` placeholder (default configurable path, e.g. `target/classes`)

Implementation should make adding language templates straightforward.

### 6) Action: run SonarScanner

From repo root run:
- `sonar-scanner -Dsonar.host.url=<url> -Dsonar.token=<token>`

Config sources:
- URL: `SONARQUBE_URL` or `SONAR_HOST_URL` (base host URL)
- token: `SONARQUBE_TOKEN` or `SONAR_TOKEN`

Execution controls:
- `SONAR_WAIT_MODE` = `sync` | `async`
- `SONAR_SUBMISSION_DELAY_SECONDS` for pacing submissions
- `SONAR_SYNC_POLL_INTERVAL_SECONDS` and `SONAR_SYNC_TIMEOUT_SECONDS` for CE polling in sync mode
- `SONAR_SCANNER_EXECUTABLE` and `SONAR_SCANNER_TIMEOUT_SECONDS`

Capture per repo:
- exit code
- stdout/stderr
- optional analysis URL (if parsable)

### 7) CLI contract

Core args (required unless provided via environment fallback):
- `--provider` (`bitbucket|github|gitlab`, only `bitbucket` implemented now)
- `--workspace`
- `--base-dir`

Core arg fallback from environment (when CLI args are omitted):
- `GIT_PROVIDER` -> provider
- `GIT_WORKSPACE` -> workspace
- `BASE_DIR` -> base directory
- optional `GIT_REPO_SLUG` -> run/filter only one repository slug
- optional `GIT_MAX_REPOS` -> limit count
- optional `GIT_REPO_SELECTION` -> `first` or `random`
- optional `GIT_RANDOM_SEED` -> deterministic random seed

Optional args:
- `--dry-run`
- `--repo-slug` (single repository filter)
- `--max-repos` (limit number of repositories)
- `--repo-selection` (`first` or `random` when limiting)
- `--random-seed` (optional deterministic seed for random selection)

Rule-specific settings:
- Language detection, CSV, sonar generation, and sonar scanner settings are not part of the core CLI contract.
- Those inputs must be owned by the corresponding rule/action implementation.
- Rule implementations read their own environment variables.
- Action composition is configured via `GIT_ACTIONS` (comma-separated), e.g.
  - `detect-languages,generate-sonar-properties,run-sonar-scan`
  - `detect-languages,write-language-csv,generate-sonar-properties,run-sonar-scan`

Failure policy:
- `GIT_STOP_ON_ERROR=false` (default): continue with next repository
- `GIT_STOP_ON_ERROR=true`: stop at first repository failure

Core provider auth settings (environment variables):
- `BITBUCKET_TOKEN` (preferred when available)
- or `BITBUCKET_USERNAME` + `BITBUCKET_APP_PASSWORD`
- optional: `BITBUCKET_API_BASE_URL` (default `https://api.bitbucket.org/2.0`)
- optional: `BITBUCKET_TIMEOUT_SECONDS` (default `30`)

### 8) Non-functional requirements

- Hexagonal architecture with clear domain/application/adapters boundaries.
- Dependency injection of ports into use cases.
- Log progress per repository and action.
- `--dry-run` must not modify filesystem, clone, pull, or run scanner.
- Keep code testable and maintainable.

## Required response format for implementation tasks

For each implementation step you perform, return:

1. Requirement restatement (brief)
2. Design sketch (ports/adapters touched)
3. Code changes summary
4. Human verification checklist
5. If relevant, suggested test step (manual or semi-automated)

If requirements are ambiguous, ask concise clarifying questions before coding.

---

# Implementation Plan (LLM Task Backlog)

This backlog is designed to be executed one task at a time.

## Task 1 — Project skeleton and package boundaries

### What to do (high level)
- Create Python project layout for hexagonal architecture.
- Add entrypoint, package modules, and placeholders for domain ports/entities/use cases and adapters.

### How to check correctness
- Project imports succeed.
- CLI entrypoint prints help without errors.
- Directory structure reflects domain vs adapters separation.

### Test step
- Human run: invoke CLI with `--help` and verify expected command/options text appears.

## Task 2 — Core domain model and ports

### What to do (high level)
- Implement domain entities (`Repository`, `RepoContext`, `ActionResult`, etc.).
- Define core port interfaces (`GitProviderPort`, `GitClientPort`, filesystem abstraction if used).
- Keep Sonar execution contracts in rules layer (not in domain ports).
- Implement `Action` contract and `ActionPipeline`.

### How to check correctness
- Type/contract consistency across domain modules.
- `ActionPipeline` runs actions in deterministic order.
- Context updates from one action are visible to subsequent actions.

### Test step
- Human run: execute a small demo flow with fake in-memory actions and verify expected ordered output.

## Task 3 — Configuration resolution (CLI + env)

### What to do (high level)
- Parse required and optional CLI args using `argparse`.
- Resolve env defaults and CLI override precedence.
- Implement token resolution for `env:VAR_NAME` format.

### How to check correctness
- Missing required inputs produce clear errors.
- CLI values override env values.
- Defaults match specification.

### Test step
- Human run: try combinations of env-only, CLI-only, and mixed inputs; compare effective config in logs.

## Task 4 — Bitbucket Cloud provider adapter

### What to do (high level)
- Implement Bitbucket repository listing with pagination.
- Map API response to domain `Repository` entities.
- Resolve SSH clone URL from returned clone links.

### How to check correctness
- Adapter returns complete repo list from a real workspace.
- Pagination is followed until completion.
- Each returned repo has valid slug/name and SSH URL.
- Returned list is not limited to one project/view unless a filter is explicitly enabled.

### Test step
- Human run: with a workspace containing multiple pages of repos (or enough repos), verify total count and sample URLs.

## Task 5 — Shell Git client adapter

### What to do (high level)
- Implement clone and pull operations through subprocess commands.
- Add safe execution, exit code handling, and readable logs.
- Ensure base directory and sanitized local paths are handled.

### How to check correctness
- Non-existing repo folder gets cloned.
- Existing repo folder gets pulled.
- Failures are surfaced with actionable errors.

### Test step
- Human run: first execution on empty base dir, second execution on populated base dir; verify clone then pull behavior.

## Task 6 — Git workspace scanner use case

### What to do (high level)
- Implement orchestration use case:
  - list repos
  - clone/pull
  - build `RepoContext`
  - run `ActionPipeline`
- Respect `--dry-run` mode.

### How to check correctness
- For each repo, expected lifecycle logs appear in order.
- Dry-run lists planned actions but does not mutate anything.

### Test step
- Human run: compare normal run vs `--dry-run` in same workspace and verify side effects only occur in normal run.

## Task 7 — Language detection action

### What to do (high level)
- Recursively scan repo files and detect configured extensions.
- Deduplicate and normalize extension list.
- Store result in `RepoContext` for downstream actions.

### How to check correctness
- Known mixed-language repositories produce expected extension set.
- Unsupported extensions are ignored.

### Test step
- Human run: use a small sample repo with known files and verify detected extensions in logs/context output.

## Task 8 — CSV report action (idempotent)

### What to do (high level)
- Write per-repo language rows into CSV.
- Enforce idempotency strategy (skip duplicates or explicit regenerate mode).
- Respect configured CSV path.

### How to check correctness
- CSV created with header and expected row format.
- Re-running does not duplicate rows under default behavior.

### Test step
- Human run: execute pipeline twice and inspect CSV row count stability.

## Task 9 — Sonar properties generation action

### What to do (high level)
- Choose template from detected languages using deterministic priority.
- Generate `sonar-project.properties` with required keys.
- Handle existing file with default skip and optional overwrite mode.

### How to check correctness
- Correct template is selected for single- and multi-language repos.
- Output file includes required values and Java-specific field when applicable.

### Test step
- Human run: test repos with Java, TS, JS, Python, and mixed stacks; verify generated file contents.

## Task 10 — Sonar scanner adapter and execution action

### What to do (high level)
- Implement shell adapter to run `sonar-scanner` from repo root.
- Pass URL/token from resolved config.
- Capture and store exit code + stdout/stderr summary per repo.

### How to check correctness
- Command runs with expected arguments.
- Success/failure per repo is logged and persisted in summary output.

### Test step
- Human run: execute with valid and invalid token values and verify exit handling/logging quality.

## Task 11 — CLI action toggles and composition

### What to do (high level)
- Wire CLI flags to include/exclude actions:
  - `--skip-sonar`
  - `--skip-language-detection`
  - `--skip-sonar-file-generation`
- Build pipeline dynamically from selected flags.

### How to check correctness
- Flag combinations produce correct action list.
- Skipped actions produce no side effects.

### Test step
- Human run: test at least three flag combinations and verify which artifacts are created.

## Task 12 — Logging, error policy, and run summary

### What to do (high level)
- Standardize logs by repo and action stage.
- Decide failure policy (continue next repo vs stop on first fatal error).
- Emit final summary table/report.

### How to check correctness
- Logs are readable and traceable by repo.
- Summary clearly indicates completed/failed repos and reasons.

### Test step
- Human run: force one repo to fail (e.g., no permissions) and confirm behavior matches policy.

## Task 13 — Manual validation guide (human-centered)

### What to do (high level)
- Write a concise manual test guide for WSL usage:
  - SSH prerequisites
  - environment variable setup
  - representative command invocations
  - expected outcomes

### How to check correctness
- A human can follow steps from zero to first successful scan without guessing.

### Test step
- Human run: follow guide on a clean machine/session and record any missing instructions.

## Task 14 — Optional semi-automation preparation (later)

### What to do (high level)
- Prepare lightweight scripts/checklists to reduce manual testing effort while preserving human approval points.

### How to check correctness
- Scripts reduce repeated manual steps but still allow environment-driven execution.

### Test step
- Human run: use helper scripts and confirm outputs match manual process.