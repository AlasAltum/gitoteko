# Task 15 — Sonar execution pacing and wait mode

## Objective
Add safe Sonar execution controls to prevent overwhelming a remote SonarQube instance during large workspace scans.

## High-level changes
- Added dynamic action composition in CLI runtime using `GIT_ACTIONS`.
- Added Sonar scan controls in `RunSonarScannerAction`:
  - `wait_mode` (`sync` or `async`)
  - `submission_delay_seconds` between repository submissions
  - synchronous CE task polling with timeout and polling interval
- Added CE task metadata extraction and status reporting in action results.
- Normalized Sonar URL handling to use base host URL (no endpoint suffix in config).

## Runtime configuration
Configured through environment variables:

- `GIT_ACTIONS`: comma-separated action list. Example:
  - `detect-languages,generate-sonar-properties,run-sonar-scan`
- `SONAR_WAIT_MODE`: `sync` (default) or `async`
- `SONAR_SUBMISSION_DELAY_SECONDS`: pacing delay between scans
- `SONAR_SYNC_POLL_INTERVAL_SECONDS`: CE polling interval
- `SONAR_SYNC_TIMEOUT_SECONDS`: max wait time per repository
- `SONAR_SCANNER_EXECUTABLE`: scanner command (default `sonar-scanner`)
- `SONAR_SCANNER_TIMEOUT_SECONDS`: scanner process timeout

## Notes
- SonarQube server remains remote (`SONARQUBE_URL`/`SONAR_HOST_URL`).
- These changes do not require running a local SonarQube server.
- Docker-based scanner usage can remain optional and external.

## Verification performed
- Static error validation on changed files (`main.py`, `sonar_scan.py`) reports no errors.
- Implementation plan updated with Task 15 acceptance criteria and test step.

## Why acceptable
This implementation preserves the hexagonal separation (Sonar behavior in rules layer), keeps core orchestration generic, and introduces explicit controls to reduce backpressure against remote SonarQube instances during high-volume runs.
