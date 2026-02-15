from __future__ import annotations
"""Rule action to persist detected repository languages into a CSV report."""

import csv
from pathlib import Path

from git_workspace_tool.domain.actions import Action
from git_workspace_tool.domain.entities import ActionResult, RepoContext


class WriteLanguageReportCsvAction(Action):
    """Write one language summary row per repository into a configurable CSV file.

    Idempotency strategy:
    - default (`regenerate=False`): skip write when workspace+repo_slug already exists.
    - regenerate (`regenerate=True`): rewrite report replacing existing row for repo.
    """

    _FIELDNAMES = ("workspace", "repo_name", "repo_slug", "local_path", "extensions")

    def __init__(
        self,
        report_csv_path: Path,
        *,
        regenerate: bool = False,
        extensions_delimiter: str = ";",
    ) -> None:
        """Initialize CSV reporting action.

        Args:
            report_csv_path: Destination report path.
            regenerate: Whether to rewrite existing row for current repository.
            extensions_delimiter: Delimiter used to serialize extension list.
        """
        self._report_csv_path = report_csv_path
        self._regenerate = regenerate
        self._extensions_delimiter = extensions_delimiter

    def execute(self, repo_context: RepoContext) -> ActionResult:
        """Persist current repository language snapshot into CSV."""
        self._report_csv_path.parent.mkdir(parents=True, exist_ok=True)

        target_row = {
            "workspace": repo_context.workspace_id,
            "repo_name": repo_context.repository.name,
            "repo_slug": repo_context.repository.slug,
            "local_path": str(repo_context.local_path),
            "extensions": self._serialize_extensions(repo_context.detected_extensions),
        }

        existing_rows = self._read_rows()
        row_key = (repo_context.workspace_id, repo_context.repository.slug)

        existing_index = self._find_row_index(existing_rows, row_key)

        if existing_index is not None and not self._regenerate:
            return ActionResult(
                action_name=self.name,
                success=True,
                message="CSV row already exists, skipped",
                metadata={
                    "csv_path": str(self._report_csv_path),
                    "row_written": False,
                    "regenerate": False,
                },
            )

        if existing_index is not None:
            existing_rows[existing_index] = target_row
        else:
            existing_rows.append(target_row)

        self._write_rows(existing_rows)

        return ActionResult(
            action_name=self.name,
            success=True,
            message="CSV row written",
            metadata={
                "csv_path": str(self._report_csv_path),
                "row_written": True,
                "regenerate": self._regenerate,
            },
        )

    def _serialize_extensions(self, extensions: set[str]) -> str:
        return self._extensions_delimiter.join(sorted(extensions))

    def _read_rows(self) -> list[dict[str, str]]:
        if not self._report_csv_path.exists():
            return []

        with self._report_csv_path.open("r", encoding="utf-8", newline="") as csv_file:
            reader = csv.DictReader(csv_file)
            rows: list[dict[str, str]] = []
            for row in reader:
                rows.append({key: row.get(key, "") for key in self._FIELDNAMES})
            return rows

    def _write_rows(self, rows: list[dict[str, str]]) -> None:
        with self._report_csv_path.open("w", encoding="utf-8", newline="") as csv_file:
            writer = csv.writer(csv_file)
            writer.writerow(self._FIELDNAMES)
            for row in rows:
                writer.writerow([row.get(field, "") for field in self._FIELDNAMES])

    @staticmethod
    def _find_row_index(rows: list[dict[str, str]], row_key: tuple[str, str]) -> int | None:
        workspace, repo_slug = row_key
        for index, row in enumerate(rows):
            if row.get("workspace") == workspace and row.get("repo_slug") == repo_slug:
                return index
        return None
