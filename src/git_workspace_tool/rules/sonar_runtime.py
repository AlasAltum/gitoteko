from __future__ import annotations
"""Sonar runtime primitives owned by the rules layer.

These contracts are intentionally outside the core domain because Sonar behavior
is rule-specific and optional.
"""

import subprocess
from pathlib import Path
from typing import Callable, Protocol


class SonarScannerRunner(Protocol):
    """Rule-scoped contract for executing SonarScanner."""

    def run(
        self,
        repo_path: Path,
        sonar_url: str,
        token: str,
        *,
        branch_name: str | None = None,
    ) -> tuple[int, str, str]:
        """Execute scanner and return `(exit_code, stdout, stderr)`."""
        ...


class ShellSonarScannerRunner:
    """Run `sonar-scanner` through a shell process."""

    def __init__(
        self,
        *,
        scanner_executable: str = "sonar-scanner",
        timeout_seconds: float = 1800.0,
        runner: Callable[..., subprocess.CompletedProcess[str]] = subprocess.run,
    ) -> None:
        self._scanner_executable = scanner_executable
        self._timeout_seconds = timeout_seconds
        self._runner = runner

    def run(
        self,
        repo_path: Path,
        sonar_url: str,
        token: str,
        *,
        branch_name: str | None = None,
    ) -> tuple[int, str, str]:
        command = [
            self._scanner_executable,
            f"-Dsonar.host.url={sonar_url}",
            f"-Dsonar.token={token}",
        ]
        if branch_name and branch_name != "main":
            command.append(f"-Dsonar.branch.name={branch_name}")

        try:
            completed = self._runner(
                command,
                cwd=str(repo_path),
                check=False,
                text=True,
                capture_output=True,
                timeout=self._timeout_seconds,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                f"SonarScanner executable '{self._scanner_executable}' was not found in PATH"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                f"SonarScanner timed out after {self._timeout_seconds}s in {repo_path}"
            ) from error

        return completed.returncode, completed.stdout or "", completed.stderr or ""
