from __future__ import annotations

from pathlib import Path

from git_workspace_tool.domain.ports import FileSystemPort


class LocalFileSystemAdapter(FileSystemPort):
    def ensure_directory(self, path: Path) -> None:
        path.mkdir(parents=True, exist_ok=True)

    def list_files_recursive(self, path: Path):
        return path.rglob("*")
