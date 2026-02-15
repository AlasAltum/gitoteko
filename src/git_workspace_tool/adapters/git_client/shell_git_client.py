from __future__ import annotations

import logging
import subprocess
from pathlib import Path
from typing import Sequence

from git_workspace_tool.domain.ports import GitClientPort


class ShellGitClientAdapter(GitClientPort):
    def __init__(self, *, git_executable: str = "git", timeout_seconds: float = 300.0) -> None:
        self._git_executable = git_executable
        self._timeout_seconds = timeout_seconds
        self._logger = logging.getLogger(__name__)

    def clone(self, clone_url: str, local_path: Path) -> None:
        if local_path.exists():
            self._logger.info(
                "clone skipped: path already exists",
                extra={"event": "git.clone.skip_exists", "local_path": str(local_path)},
            )
            return

        local_path.parent.mkdir(parents=True, exist_ok=True)
        self._logger.info(
            "cloning repository",
            extra={
                "event": "git.clone.start",
                "clone_url": clone_url,
                "local_path": str(local_path),
            },
        )
        self._run_git(["clone", clone_url, str(local_path)], cwd=local_path.parent)
        self._logger.info(
            "clone completed",
            extra={"event": "git.clone.success", "local_path": str(local_path)},
        )

    def pull(self, local_path: Path) -> None:
        if not local_path.exists():
            raise RuntimeError(f"Cannot pull repository: path does not exist: {local_path}")

        git_dir = local_path / ".git"
        if not git_dir.exists():
            raise RuntimeError(f"Cannot pull repository: not a git repository: {local_path}")

        self._logger.info(
            "pulling repository",
            extra={"event": "git.pull.start", "local_path": str(local_path)},
        )

        self._run_git(["fetch", "--prune", "origin"], cwd=local_path)

        if self._has_upstream(local_path):
            self._run_git(["pull", "--ff-only"], cwd=local_path)
        else:
            current_branch = self._get_current_branch(local_path)
            default_branch = self._get_default_remote_branch(local_path)

            self._logger.info(
                "repository has no upstream tracking; applying fallback pull strategy",
                extra={
                    "event": "git.pull.no_upstream",
                    "local_path": str(local_path),
                    "current_branch": current_branch,
                    "default_branch": default_branch,
                },
            )

            if current_branch and current_branch != "HEAD" and self._remote_branch_exists(local_path, current_branch):
                self._run_git(["pull", "--ff-only", "origin", current_branch], cwd=local_path)
            elif default_branch:
                self._run_git(["pull", "--ff-only", "origin", default_branch], cwd=local_path)
            else:
                raise RuntimeError(
                    f"Cannot pull repository: no upstream and no resolvable remote default branch: {local_path}"
                )

        self._logger.info(
            "pull completed",
            extra={"event": "git.pull.success", "local_path": str(local_path)},
        )

    def _has_upstream(self, cwd: Path) -> bool:
        result = self._run_git_allow_fail(
            ["rev-parse", "--abbrev-ref", "--symbolic-full-name", "@{u}"],
            cwd=cwd,
        )
        return result.returncode == 0

    def _get_current_branch(self, cwd: Path) -> str | None:
        result = self._run_git_allow_fail(["rev-parse", "--abbrev-ref", "HEAD"], cwd=cwd)
        if result.returncode != 0:
            return None
        branch = (result.stdout or "").strip()
        return branch or None

    def _get_default_remote_branch(self, cwd: Path) -> str | None:
        result = self._run_git_allow_fail(["symbolic-ref", "--short", "refs/remotes/origin/HEAD"], cwd=cwd)
        if result.returncode != 0:
            return None
        value = (result.stdout or "").strip()
        if value.startswith("origin/"):
            return value.split("/", 1)[1]
        return None

    def _remote_branch_exists(self, cwd: Path, branch: str) -> bool:
        result = self._run_git_allow_fail(["show-ref", "--verify", f"refs/remotes/origin/{branch}"], cwd=cwd)
        return result.returncode == 0

    def _run_git_allow_fail(self, args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        command = [self._git_executable, *args]
        try:
            return subprocess.run(
                command,
                cwd=str(cwd),
                check=False,
                text=True,
                capture_output=True,
                timeout=self._timeout_seconds,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                f"Git executable '{self._git_executable}' was not found in PATH"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                f"Git command timed out after {self._timeout_seconds}s: {' '.join(command)}"
            ) from error

    def _run_git(self, args: Sequence[str], cwd: Path) -> subprocess.CompletedProcess[str]:
        command = [self._git_executable, *args]
        try:
            return subprocess.run(
                command,
                cwd=str(cwd),
                check=True,
                text=True,
                capture_output=True,
                timeout=self._timeout_seconds,
            )
        except FileNotFoundError as error:
            raise RuntimeError(
                f"Git executable '{self._git_executable}' was not found in PATH"
            ) from error
        except subprocess.TimeoutExpired as error:
            raise RuntimeError(
                f"Git command timed out after {self._timeout_seconds}s: {' '.join(command)}"
            ) from error
        except subprocess.CalledProcessError as error:
            stderr = (error.stderr or "").strip()
            stdout = (error.stdout or "").strip()
            details = stderr or stdout or "No command output"
            self._logger.error(
                "git command failed",
                extra={
                    "event": "git.command.error",
                    "command": " ".join(command),
                    "cwd": str(cwd),
                    "return_code": error.returncode,
                    "details": details,
                },
            )
            raise RuntimeError(
                f"Git command failed ({error.returncode}): {' '.join(command)}\n{details}"
            ) from error
