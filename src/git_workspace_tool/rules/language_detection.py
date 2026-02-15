from __future__ import annotations
"""Rule action to detect programming languages from file extensions."""

from typing import Iterable

from git_workspace_tool.domain.actions import Action
from git_workspace_tool.domain.entities import ActionResult, RepoContext


class DetectLanguagesAction(Action):
    """Detect configured file extensions inside a repository.

    Expected usage:
    - Construct once with allowed extensions (e.g. [".py", ".ts"]).
    - Execute for each `RepoContext` in the pipeline.
    - Read detected values from `repo_context.detected_extensions`.
    """

    def __init__(self, extensions: Iterable[str]) -> None:
        """Initialize rule with allowed extension list.

        Args:
            extensions: Iterable of extensions with or without leading dot.
                Examples: [".py", "ts", ".java"].
        """
        self._extensions = self._normalize_extensions(extensions)

    def execute(self, repo_context: RepoContext) -> ActionResult:
        """Scan repository files and populate `RepoContext.detected_extensions`.

        Args:
            repo_context: Context containing repository local path to scan.

        Returns:
            ActionResult indicating success and detected extension metadata.
        """
        if not self._extensions:
            return ActionResult(
                action_name=self.name,
                success=False,
                message="No extensions configured for language detection",
            )

        detected: set[str] = set()

        for path in repo_context.local_path.rglob("*"):
            if not path.is_file():
                continue
            if ".git" in path.parts:
                continue

            suffix = path.suffix.lower().strip()
            if suffix in self._extensions:
                detected.add(suffix)

        repo_context.detected_extensions = detected

        return ActionResult(
            action_name=self.name,
            success=True,
            message=f"Detected {len(detected)} extensions",
            metadata={"extensions": sorted(detected)},
        )

    @staticmethod
    def _normalize_extensions(extensions: Iterable[str]) -> tuple[str, ...]:
        """Normalize extension input to deduplicated lowercase dot-prefixed tuple."""
        normalized: list[str] = []
        seen: set[str] = set()

        for item in extensions:
            ext = item.strip().lower()
            if not ext:
                continue
            if not ext.startswith("."):
                ext = f".{ext}"
            if ext not in seen:
                seen.add(ext)
                normalized.append(ext)

        return tuple(normalized)
