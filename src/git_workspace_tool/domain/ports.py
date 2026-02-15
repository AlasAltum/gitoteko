from __future__ import annotations

from abc import ABC, abstractmethod
from pathlib import Path
from typing import Iterable

from .entities import Repository, WorkspaceId


class GitProviderPort(ABC):
    @abstractmethod
    def list_repositories(self, workspace: WorkspaceId) -> list[Repository]:
        raise NotImplementedError

    @abstractmethod
    def get_clone_url(self, repository: Repository) -> str:
        raise NotImplementedError


class GitClientPort(ABC):
    @abstractmethod
    def clone(self, clone_url: str, local_path: Path) -> None:
        raise NotImplementedError

    @abstractmethod
    def pull(self, local_path: Path) -> None:
        raise NotImplementedError


class SonarScannerPort(ABC):
    @abstractmethod
    def run(self, repo_path: Path, sonar_url: str, token: str) -> tuple[int, str, str]:
        raise NotImplementedError


class FileSystemPort(ABC):
    @abstractmethod
    def ensure_directory(self, path: Path) -> None:
        raise NotImplementedError

    @abstractmethod
    def list_files_recursive(self, path: Path) -> Iterable[Path]:
        raise NotImplementedError
