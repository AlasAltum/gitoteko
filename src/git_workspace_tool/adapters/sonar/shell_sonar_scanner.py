from __future__ import annotations

from pathlib import Path

from git_workspace_tool.domain.ports import SonarScannerPort


class ShellSonarScannerAdapter(SonarScannerPort):
    def run(self, repo_path: Path, sonar_url: str, token: str) -> tuple[int, str, str]:
        # Placeholder for Task 10 implementation.
        raise NotImplementedError
