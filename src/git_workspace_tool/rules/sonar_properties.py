from __future__ import annotations
"""Rule action to generate `sonar-project.properties` from detected languages."""

from pathlib import Path

from git_workspace_tool.domain.actions import Action
from git_workspace_tool.domain.entities import ActionResult, RepoContext


class GenerateSonarPropertiesAction(Action):
    """Generate sonar configuration file at repository root.

    Language priority when multiple extensions are detected:
    1. Java (`.java`)
    2. TypeScript (`.ts`)
    3. JavaScript (`.js`)
    4. Python (`.py`)
    """

    def __init__(
        self,
        *,
        overwrite: bool = False,
        java_binaries_path: str = "target/classes",
        filename: str = "sonar-project.properties",
    ) -> None:
        """Initialize action.

        Args:
            overwrite: Replace file if it already exists. Default False.
            java_binaries_path: Value used by Java template.
            filename: Sonar properties filename at repository root.
        """
        self._overwrite = overwrite
        self._java_binaries_path = java_binaries_path
        self._filename = filename

    def execute(self, repo_context: RepoContext) -> ActionResult:
        """Create sonar properties file based on `RepoContext.detected_extensions`."""
        target_path = repo_context.local_path / self._filename

        if target_path.exists() and not self._overwrite:
            return ActionResult(
                action_name=self.name,
                success=True,
                message="sonar-project.properties already exists, skipped",
                metadata={"path": str(target_path), "written": False, "reason": "exists"},
            )

        language = self._select_language(repo_context.detected_extensions)
        content = self._build_content(repo_context, language)
        target_path.write_text(content, encoding="utf-8")

        return ActionResult(
            action_name=self.name,
            success=True,
            message="sonar-project.properties written",
            metadata={
                "path": str(target_path),
                "written": True,
                "language_template": language,
            },
        )

    def _select_language(self, extensions: set[str]) -> str:
        normalized = {ext.lower() for ext in extensions}
        if ".java" in normalized:
            return "java"
        if ".ts" in normalized:
            return "typescript"
        if ".js" in normalized:
            return "javascript"
        if ".py" in normalized:
            return "python"
        return "generic"

    def _build_content(self, repo_context: RepoContext, language: str) -> str:
        project_key = self._sanitize_key(f"{repo_context.workspace_id}_{repo_context.repository.slug}")
        lines = [
            f"sonar.projectKey={project_key}",
            f"sonar.projectName={repo_context.repository.name}",
            "sonar.sources=.",
            "sonar.sourceEncoding=UTF-8",
        ]

        if language == "java":
            lines.append(f"sonar.java.binaries={self._java_binaries_path}")

        return "\n".join(lines) + "\n"

    @staticmethod
    def _sanitize_key(value: str) -> str:
        allowed = []
        for char in value:
            if char.isalnum() or char in {"_", "-", ".", ":"}:
                allowed.append(char)
            else:
                allowed.append("_")
        return "".join(allowed)
