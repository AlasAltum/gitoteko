from __future__ import annotations
"""Core domain entities shared by use cases and rule actions.

These data models are intentionally framework-agnostic and can be reused across
different adapters (CLI, tests, future APIs).
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


WorkspaceId = str


@dataclass(slots=True)
class Repository:
    """Repository metadata used by orchestration and rules.

    Attributes:
        name: Human-readable repository name.
        slug: Stable slug used for local folder naming.
        clone_url: SSH/HTTPS URL that `GitClientPort` can clone from.
    """

    name: str
    slug: str
    clone_url: str


@dataclass(slots=True)
class RepoContext:
    """Mutable per-repository context passed through the action pipeline.

    Rules read and write this object to share intermediate information.

    Attributes:
        workspace_id: Workspace identifier where the repository belongs.
        repository: Repository metadata for the current pipeline execution.
        local_path: Local checked-out repository path.
        detected_extensions: Set of detected file extensions (e.g. {".py"}).
        metadata: Generic key/value bag for cross-rule communication.
    """

    workspace_id: WorkspaceId
    repository: Repository
    local_path: Path
    detected_extensions: set[str] = field(default_factory=set)
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class ActionResult:
    """Standard result returned by each `Action.execute()` call.

    Attributes:
        action_name: Action identifier for logs and summaries.
        success: Whether the action succeeded.
        message: Human-readable action outcome.
        metadata: Optional structured result payload for downstream consumers.
    """

    action_name: str
    success: bool
    message: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
