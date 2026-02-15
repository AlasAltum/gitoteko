# Implementation Plan — Git Workspace Tool (Python)

This is the standalone execution backlog for the project.

Scope reminders:
- Python + vanilla CLI (`argparse`) first.
- Hexagonal architecture (core orchestration + pluggable rule actions).
- Full Bitbucket workspace scan by default (no project-filtered subset unless explicitly requested).
- Human-centered validation steps.

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
- Define port interfaces (`GitProviderPort`, `GitClientPort`, `SonarScannerPort`, filesystem abstraction if used).
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
- Ensure full workspace scope is used by default.

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
