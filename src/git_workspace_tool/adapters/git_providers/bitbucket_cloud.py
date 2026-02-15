from __future__ import annotations

from git_workspace_tool.domain.entities import Repository, WorkspaceId
from git_workspace_tool.domain.ports import GitProviderPort


class BitbucketCloudGitProviderAdapter(GitProviderPort):
    def list_repositories(self, workspace: WorkspaceId) -> list[Repository]:
        # Placeholder for Task 4 implementation (Bitbucket API pagination).
        return []

    def get_clone_url(self, repository: Repository) -> str:
        return repository.clone_url
