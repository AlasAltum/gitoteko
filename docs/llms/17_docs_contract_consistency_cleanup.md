# Task 17 — Docs contract consistency cleanup

## Objective
Align specification docs with the current implemented runtime contract.

## Changes
- Updated [docs/prompt.md](prompt.md) to match implemented behavior:
  - `LANGUAGE_DETECTION_EXTENSIONS` naming
  - `LANGUAGE_REPORT_CSV` default value
  - remote Sonar URL/token env-only contract
  - Sonar pacing and wait-mode controls
  - `GIT_ACTIONS` action composition
  - `GIT_STOP_ON_ERROR` failure policy
- Removed references to non-implemented CLI flags for rule-specific settings.

## Why acceptable
This avoids operator confusion by keeping architecture/spec docs consistent with actual CLI and rule runtime behavior.
