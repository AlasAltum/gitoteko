# Task 11 — CLI action toggles and composition

## Objective
Allow operators to choose which repository actions run without changing core CLI arguments.

## High-level implementation
- Added environment-driven action composition through `GIT_ACTIONS`.
- Kept core CLI contract unchanged (`provider`, `workspace`, `base_dir`, filters, dry-run).
- Rule-specific configuration stays in action/runtime layer, preserving architecture boundaries.

## Supported action names
- `detect-languages`
- `write-language-csv`
- `generate-sonar-properties`
- `run-sonar-scan`

## Runtime behavior
- If `GIT_ACTIONS` is empty or unset, no actions run (sync-only mode).
- If set, actions are instantiated in the exact listed order.
- Unknown action names fail fast with a clear runtime error.

## Configuration examples

```bash
export GIT_ACTIONS="detect-languages,generate-sonar-properties,run-sonar-scan"
```

```bash
export GIT_ACTIONS="detect-languages,write-language-csv,generate-sonar-properties,run-sonar-scan"
```

## Why acceptable
This enables flexible action toggling while keeping core orchestration generic and stable, which matches the hexagonal architecture intent.
