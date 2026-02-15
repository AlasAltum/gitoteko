# Task 14 — Optional semi-automation preparation

## Objective
Reduce repetitive manual validation steps while preserving human control points.

## What was added
- Helper script: [scripts/manual_validation_quickcheck.sh](../scripts/manual_validation_quickcheck.sh)
  - Loads `.env`
  - Validates required runtime values
  - Runs a bounded sample execution (`--max-repos`, default `3`)
  - Supports dry-run (default) and real mode (`--real`)

## Why this is semi-automation
- It does not hide critical decisions.
- Operator still chooses run mode (`dry-run` vs real) and sample size.
- It avoids fully automated mass execution and keeps validation intentional.

## Usage examples
From repository root:

```bash
scripts/manual_validation_quickcheck.sh
scripts/manual_validation_quickcheck.sh --real
scripts/manual_validation_quickcheck.sh --max-repos 5 --base-dir /tmp/gitoteko-quickcheck
```

## Notes
- Script is path-agnostic: it assumes current working directory is repository root.
- It uses `.venv/bin/python` from the current repository.
- It is intentionally lightweight and can be expanded later with additional checks.

## Verification done
- Script syntax/logic written for strict shell mode (`set -euo pipefail`).
- Inputs are validated before command execution.

## Why acceptable
This task lowers repeated manual effort while staying aligned with the project’s human-centered validation requirement.
