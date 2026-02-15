from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from git_workspace_tool.domain.actions import ActionPipeline
from git_workspace_tool.domain.entities import RepoContext, WorkspaceId
from git_workspace_tool.domain.ports import FileSystemPort, GitClientPort, GitProviderPort


@dataclass(slots=True)
class GitWorkspaceScanner:
    git_provider: GitProviderPort
    git_client: GitClientPort
    filesystem: FileSystemPort
    action_pipeline: ActionPipeline

    def execute(self, workspace: WorkspaceId, base_dir: Path, dry_run: bool = False) -> None:
        repositories = self.git_provider.list_repositories(workspace)

        if dry_run:
            return

        self.filesystem.ensure_directory(base_dir)

        for repository in repositories:
            local_path = base_dir / repository.slug

            if local_path.exists():
                self.git_client.pull(local_path)
            else:
                self.git_client.clone(self.git_provider.get_clone_url(repository), local_path)

            context = RepoContext(
                workspace_id=workspace,
                repository=repository,
                local_path=local_path,
            )
            self.action_pipeline.run(context)
