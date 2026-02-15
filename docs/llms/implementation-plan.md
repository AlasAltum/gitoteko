# Implementation Plan — Git Workspace Tool (Python)

This is the standalone execution backlog for the project.

Scope reminders:
- Python + vanilla CLI (`argparse`) first.
- Hexagonal architecture (core orchestration + pluggable rule actions).
- Full Bitbucket workspace scan by default (no project-filtered subset unless explicitly requested).
- Human-centered validation steps.

## Task delivery documentation

For each completed task, add a short high-level implementation note in `docs/` using this naming pattern:

- `<task-number>_<short_name>.md`

Each note should include:
- objective
- high-level design/changes
- verification done
- why the implementation is considered acceptable

Current notes:
- [Task 5 note](5_shell_git_client_adapter.md)
- [Task 6 note](6_git_workspace_scanner_use_case.md)
- [Task 7 note](7_language_detection_action.md)
- [Task 8 note](8_csv_report_action.md)
- [Task 9 note](9_sonar_properties_generation_action.md)
- [Task 10 note](10_sonar_scanner_adapter_and_action.md)
- [CLI runtime wiring note](cli_runtime_wiring_bitbucket_dry_run.md)
- [CLI env fallback and single-repo filter note](cli_env_fallback_and_single_repo_filter.md)
- [Sonar boundary refactor note](sonar_boundary_refactor.md)
- [Logging and git pull diagnostics note](logging_and_git_pull_diagnostics.md)
- [Task 11 note](11_cli_action_toggles_and_composition.md)
- [Task 12 note](12_logging_error_policy_and_summary.md)
- [Task 13 note](13_manual_validation_guide.md)
- [Task 14 note](14_semi_automation_preparation.md)
- [Task 15 note](15_sonar_execution_pacing_and_wait_mode.md)
- [Task 16 note](16_readme_operator_guide_refresh.md)
- [Task 17 note](17_docs_contract_consistency_cleanup.md)
- [Task 18 note](../18_sonar_skip_unchanged_and_rule_authoring.md)

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
- Keep Sonar execution contracts in rules layer (not core domain ports).
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
- Keep core config focused on orchestration inputs (`provider`, `workspace`, `base_dir`, `dry_run`).
- Keep rule-specific configuration out of core config (rules own their env/flags).

### How to check correctness
- Missing required inputs produce clear errors.
- Core CLI rejects unknown rule-specific flags unless a rule extension explicitly adds them.
- Core config remains stable even as new rules are added.

### Test step
- Human run: invoke core CLI with required args and `--dry-run`, then pass a rule-specific flag and verify it is rejected by core.

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
- Build pipeline dynamically from selected action registrations.
- If action toggles are needed, define them in the action pack/extension layer, not in the core CLI.

### How to check correctness
- Enabled/disabled action composition produces the expected action list.
- Core CLI remains unchanged when adding/removing rule-specific toggles.

### Test step
- Human run: run core with different registered action sets and verify which artifacts are created.

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

## Task 15 — Sonar execution pacing and wait mode

### What to do (high level)
- Add Sonar rule runtime controls for paced execution to avoid backpressure.
- Add explicit wait mode configuration:
  - synchronous: wait for each submitted analysis result before continuing.
  - asynchronous: submit and continue without waiting for processing completion.
- Add configurable pacing controls (for example: per-repo delay seconds and/or max analyses per minute).
- Ensure defaults are conservative for production Sonar instances.

### How to check correctness
- Execution rate is bounded according to configured pacing values.
- In synchronous mode, next repository is processed only after previous Sonar background task reaches terminal state.
- In asynchronous mode, submission does not block on Sonar background processing.
- Logs clearly show submission time, wait decisions, and Sonar task IDs.

### Test step
- Human run: process a small repository batch with synchronous mode and verify sequential completion; re-run with asynchronous mode and verify faster submissions with bounded pacing.
