# Sonar Boundary Refactor

## Objective

Align architecture boundaries so Sonar concerns are no longer part of core domain ports/adapters.

## What changed

1. Removed Sonar from core domain ports:
- `SonarScannerPort` was removed from `src/git_workspace_tool/domain/ports.py`.

2. Introduced Sonar runtime contracts in rules layer:
- Added `src/git_workspace_tool/rules/sonar_runtime.py` with:
  - `SonarScannerRunner` protocol
  - `ShellSonarScannerRunner` implementation

3. Updated Sonar rule action to depend on rules-layer contract:
- `src/git_workspace_tool/rules/sonar_scan.py` now expects `SonarScannerRunner`.

4. Kept backward compatibility shim under adapters:
- `src/git_workspace_tool/adapters/sonar/shell_sonar_scanner.py` now acts as deprecated alias pointing to rules runtime.

## Why this matches the intended architecture

- Core domain remains generic and focused on repository orchestration.
- Sonar is optional/specific behavior and now belongs to rule modules.
- Rule-specific runtime implementations are colocated with rules, not core adapters.
