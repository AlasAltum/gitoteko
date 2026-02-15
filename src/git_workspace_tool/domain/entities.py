from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


WorkspaceId = str


@dataclass(slots=True)
class Repository:
    name: str
    slug: str
    clone_url: str


@dataclass(slots=True)
class RepoContext:
    workspace_id: WorkspaceId
    repository: Repository
    local_path: Path
    detected_extensions: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ActionResult:
    action_name: str
    success: bool
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
