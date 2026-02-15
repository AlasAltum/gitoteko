from __future__ import annotations
"""Application use case for workspace repository synchronization and action execution."""

from dataclasses import dataclass
import logging
from pathlib import Path
import random

from git_workspace_tool.domain.actions import ActionPipeline
from git_workspace_tool.domain.entities import ActionResult, RepoContext, WorkspaceId
from git_workspace_tool.domain.ports import FileSystemPort, GitClientPort, GitProviderPort


LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class RepositoryExecutionSummary:
    """Per-repository execution snapshot returned by `GitWorkspaceScanner`."""

    repo_slug: str
    local_path: Path
    sync_operation: str
    dry_run: bool
    planned_actions: tuple[str, ...]
    action_results: tuple[ActionResult, ...]
    success: bool
    error: str | None


@dataclass(slots=True)
class ScanExecutionSummary:
    """Workspace-level execution summary for one scanner run."""

    workspace: WorkspaceId
    base_dir: Path
    dry_run: bool
    repositories: tuple[RepositoryExecutionSummary, ...]
    failed_repositories: int
    successful_repositories: int


@dataclass(slots=True)
class GitWorkspaceScanner:
    """Core orchestration use case.

    Responsibilities:
    - list repositories from `GitProviderPort`
    - determine clone/pull operation
    - execute git sync through `GitClientPort`
    - build `RepoContext` and run `ActionPipeline`
    - support dry-run planning with no side effects
    """

    git_provider: GitProviderPort
    git_client: GitClientPort
    filesystem: FileSystemPort
    action_pipeline: ActionPipeline

    def execute(
        self,
        workspace: WorkspaceId,
        base_dir: Path,
        dry_run: bool = False,
        only_repo_slug: str | None = None,
        max_repos: int | None = None,
        repo_selection: str = "first",
        random_seed: int | None = None,
        stop_on_error: bool = False,
    ) -> ScanExecutionSummary:
        """Execute one workspace scan/sync run.

        Args:
            workspace: Workspace identifier to scan.
            base_dir: Base local directory where repositories are synchronized.
            dry_run: When `True`, do not mutate filesystem or run git/actions.
            only_repo_slug: Optional repository slug filter for single-repo runs.
            max_repos: Optional repository count limit.
            repo_selection: Selection mode when limiting (`first` or `random`).
            random_seed: Optional seed for deterministic random selection.

        Returns:
            `ScanExecutionSummary` describing planned or executed operations.
        """
        repositories = self.git_provider.list_repositories(workspace)
        LOGGER.info(
            "repositories listed",
            extra={"event": "scanner.repositories.listed", "workspace": workspace, "count": len(repositories)},
        )

        if only_repo_slug:
            repositories = [repo for repo in repositories if repo.slug == only_repo_slug]
            LOGGER.info(
                "repository slug filter applied",
                extra={
                    "event": "scanner.repositories.filtered.slug",
                    "workspace": workspace,
                    "repo_slug": only_repo_slug,
                    "count": len(repositories),
                },
            )

        if max_repos is not None and len(repositories) > max_repos:
            if repo_selection == "random":
                rng = random.Random(random_seed)
                repositories = rng.sample(repositories, max_repos)
            else:
                repositories = repositories[:max_repos]
            LOGGER.info(
                "repository limit applied",
                extra={
                    "event": "scanner.repositories.filtered.limit",
                    "workspace": workspace,
                    "max_repos": max_repos,
                    "selection": repo_selection,
                    "random_seed": random_seed,
                    "count": len(repositories),
                },
            )

        planned_actions = tuple(action.name for action in self.action_pipeline.actions)
        summaries: list[RepositoryExecutionSummary] = []

        if not dry_run:
            self.filesystem.ensure_directory(base_dir)
            LOGGER.info(
                "base directory ensured",
                extra={"event": "scanner.base_dir.ensure", "base_dir": str(base_dir)},
            )

        for repository in repositories:
            local_path = base_dir / repository.slug
            already_exists = self.filesystem.path_exists(local_path)
            sync_operation = "pull" if already_exists else "clone"

            LOGGER.info(
                "repository processing started",
                extra={
                    "event": "scanner.repository.start",
                    "workspace": workspace,
                    "repo_slug": repository.slug,
                    "local_path": str(local_path),
                    "sync_operation": sync_operation,
                    "dry_run": dry_run,
                },
            )

            if dry_run:
                summaries.append(
                    RepositoryExecutionSummary(
                        repo_slug=repository.slug,
                        local_path=local_path,
                        sync_operation=sync_operation,
                        dry_run=True,
                        planned_actions=planned_actions,
                        action_results=(),
                        success=True,
                        error=None,
                    )
                )
                LOGGER.info(
                    "repository dry-run planned",
                    extra={
                        "event": "scanner.repository.dry_run",
                        "repo_slug": repository.slug,
                        "sync_operation": sync_operation,
                    },
                )
                continue

            try:
                if already_exists:
                    self.git_client.pull(local_path)
                else:
                    self.git_client.clone(self.git_provider.get_clone_url(repository), local_path)

                context = RepoContext(
                    workspace_id=workspace,
                    repository=repository,
                    local_path=local_path,
                )
                action_results = tuple(self.action_pipeline.run(context))

                action_failed = any(not result.success for result in action_results)
                repo_success = not action_failed
                repo_error = None
                if action_failed:
                    failed_actions = [result.action_name for result in action_results if not result.success]
                    repo_error = f"One or more actions failed: {', '.join(failed_actions)}"

                LOGGER.info(
                    "repository actions completed",
                    extra={
                        "event": "scanner.repository.actions.completed",
                        "repo_slug": repository.slug,
                        "action_count": len(action_results),
                        "action_names": [result.action_name for result in action_results],
                        "success": repo_success,
                    },
                )

                summaries.append(
                    RepositoryExecutionSummary(
                        repo_slug=repository.slug,
                        local_path=local_path,
                        sync_operation=sync_operation,
                        dry_run=False,
                        planned_actions=planned_actions,
                        action_results=action_results,
                        success=repo_success,
                        error=repo_error,
                    )
                )

                if action_failed and stop_on_error:
                    LOGGER.error(
                        "repository failed and stop_on_error is enabled",
                        extra={
                            "event": "scanner.repository.failed.stop",
                            "repo_slug": repository.slug,
                            "error": repo_error,
                        },
                    )
                    break
            except Exception as error:  # noqa: BLE001
                error_message = str(error)
                LOGGER.exception(
                    "repository processing failed",
                    extra={
                        "event": "scanner.repository.failed",
                        "repo_slug": repository.slug,
                        "error": error_message,
                    },
                )
                summaries.append(
                    RepositoryExecutionSummary(
                        repo_slug=repository.slug,
                        local_path=local_path,
                        sync_operation=sync_operation,
                        dry_run=False,
                        planned_actions=planned_actions,
                        action_results=(),
                        success=False,
                        error=error_message,
                    )
                )
                if stop_on_error:
                    LOGGER.error(
                        "stop_on_error triggered after repository failure",
                        extra={
                            "event": "scanner.stop_on_error.triggered",
                            "repo_slug": repository.slug,
                        },
                    )
                    break

        failed_repositories = sum(1 for item in summaries if not item.success)
        successful_repositories = len(summaries) - failed_repositories

        summary = ScanExecutionSummary(
            workspace=workspace,
            base_dir=base_dir,
            dry_run=dry_run,
            repositories=tuple(summaries),
            failed_repositories=failed_repositories,
            successful_repositories=successful_repositories,
        )

        LOGGER.info(
            "scanner execution completed",
            extra={
                "event": "scanner.completed",
                "workspace": workspace,
                "dry_run": dry_run,
                "repo_count": len(summary.repositories),
                "successful_repositories": successful_repositories,
                "failed_repositories": failed_repositories,
            },
        )

        return summary
