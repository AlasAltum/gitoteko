from __future__ import annotations
"""Deprecated compatibility shim.

Sonar runtime now belongs to `git_workspace_tool.rules.sonar_runtime` because
Sonar is rule-specific and not part of the core domain ports/adapters.
"""

from git_workspace_tool.rules.sonar_runtime import ShellSonarScannerRunner


class ShellSonarScannerAdapter(ShellSonarScannerRunner):
    """Backward-compatible alias; prefer `ShellSonarScannerRunner`."""
