from __future__ import annotations

from pathlib import Path

from git_workspace_tool.domain.ports import GitClientPort


class ShellGitClientAdapter(GitClientPort):
    def clone(self, clone_url: str, local_path: Path) -> None:
        # Placeholder for Task 5 implementation.
        raise NotImplementedError

    def pull(self, local_path: Path) -> None:
        # Placeholder for Task 5 implementation.
        raise NotImplementedError
