from __future__ import annotations
"""Hexagonal architecture port interfaces.

Core use cases depend only on these abstractions. Adapters provide concrete
implementations for filesystem, git provider APIs, shell commands, etc.
"""

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable

from .entities import Repository, WorkspaceId


class GitProviderPort(ABC):
    """Repository discovery provider (Bitbucket/GitHub/GitLab adapters)."""

    @abstractmethod
    def list_repositories(self, workspace: WorkspaceId) -> list[Repository]:
        """List all repositories visible in the given workspace scope."""
        raise NotImplementedError

    @abstractmethod
    def get_clone_url(self, repository: Repository) -> str:
        """Return preferred clone URL for the repository (typically SSH)."""
        raise NotImplementedError


class GitClientPort(ABC):
    """Local git operations used by orchestration (clone/pull)."""

    @abstractmethod
    def clone(self, clone_url: str, local_path: Path) -> None:
        """Clone remote repository into local path."""
        raise NotImplementedError

    @abstractmethod
    def pull(self, local_path: Path) -> None:
        """Update an existing local repository."""
        raise NotImplementedError


class FileSystemPort(ABC):
    """Filesystem operations abstracted for testability and portability."""

    @abstractmethod
    def ensure_directory(self, path: Path) -> None:
        """Ensure target directory exists (create recursively if needed)."""
        raise NotImplementedError

    @abstractmethod
    def path_exists(self, path: Path) -> bool:
        """Return whether a path exists."""
        raise NotImplementedError

    @abstractmethod
    def list_files_recursive(self, path: Path) -> Iterable[Path]:
        """Yield recursive file paths under a directory root."""
        raise NotImplementedError
