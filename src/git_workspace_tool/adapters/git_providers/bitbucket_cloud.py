from __future__ import annotations

import base64
import json
from typing import Any, Callable
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from git_workspace_tool.domain.entities import Repository, WorkspaceId
from git_workspace_tool.domain.ports import GitProviderPort


class BitbucketCloudGitProviderAdapter(GitProviderPort):
    def __init__(
        self,
        *,
        api_base_url: str = "https://api.bitbucket.org/2.0",
        token: str | None = None,
        username: str | None = None,
        app_password: str | None = None,
        timeout_seconds: float = 30.0,
        urlopen_fn: Callable[..., Any] = urlopen,
    ) -> None:
        self._api_base_url = api_base_url.rstrip("/")
        self._token = token
        self._username = username
        self._app_password = app_password
        self._timeout_seconds = timeout_seconds
        self._urlopen_fn = urlopen_fn

    def list_repositories(self, workspace: WorkspaceId) -> list[Repository]:
        encoded_workspace = quote(workspace, safe="")
        next_url: str | None = f"{self._api_base_url}/repositories/{encoded_workspace}"
        repositories: list[Repository] = []

        while next_url:
            payload = self._request_json(next_url)
            items = payload.get("values", [])
            if not isinstance(items, list):
                raise RuntimeError("Unexpected Bitbucket API payload: 'values' must be a list")

            for item in items:
                if not isinstance(item, dict):
                    continue
                repository = self._map_repository(item)
                if repository is not None:
                    repositories.append(repository)

            next_value = payload.get("next")
            next_url = next_value if isinstance(next_value, str) and next_value else None

        return repositories

    def get_clone_url(self, repository: Repository) -> str:
        return repository.clone_url

    def _request_json(self, url: str) -> dict[str, Any]:
        request = Request(url, headers=self._build_headers())
        try:
            with self._urlopen_fn(request, timeout=self._timeout_seconds) as response:
                content = response.read()
        except HTTPError as error:
            raise RuntimeError(
                f"Bitbucket API request failed with HTTP {error.code} for URL: {url}"
            ) from error
        except URLError as error:
            raise RuntimeError(f"Bitbucket API request failed for URL: {url}: {error.reason}") from error

        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as error:
            raise RuntimeError(f"Invalid JSON received from Bitbucket API for URL: {url}") from error

        if not isinstance(parsed, dict):
            raise RuntimeError("Unexpected Bitbucket API payload: top-level object must be a JSON object")

        return parsed

    def _build_headers(self) -> dict[str, str]:
        headers: dict[str, str] = {"Accept": "application/json"}

        if self._token:
            headers["Authorization"] = f"Bearer {self._token}"
            return headers

        if self._username and self._app_password:
            credentials = f"{self._username}:{self._app_password}".encode("utf-8")
            encoded = base64.b64encode(credentials).decode("ascii")
            headers["Authorization"] = f"Basic {encoded}"

        return headers

    def _map_repository(self, payload: dict[str, Any]) -> Repository | None:
        slug = payload.get("slug")
        name = payload.get("name")

        if not isinstance(slug, str) or not slug.strip():
            return None

        repo_name = name.strip() if isinstance(name, str) and name.strip() else slug.strip()
        repo_slug = slug.strip()

        clone_url = self._extract_ssh_clone_url(payload)
        if not clone_url:
            clone_url = self._build_fallback_ssh_url(payload, repo_slug)

        if not clone_url:
            return None

        return Repository(name=repo_name, slug=repo_slug, clone_url=clone_url)

    def _extract_ssh_clone_url(self, payload: dict[str, Any]) -> str | None:
        links = payload.get("links")
        if not isinstance(links, dict):
            return None

        clone_links = links.get("clone")
        if not isinstance(clone_links, list):
            return None

        for link in clone_links:
            if not isinstance(link, dict):
                continue
            if link.get("name") != "ssh":
                continue
            href = link.get("href")
            if isinstance(href, str) and href.strip():
                return href.strip()

        return None

    def _build_fallback_ssh_url(self, payload: dict[str, Any], slug: str) -> str | None:
        full_name = payload.get("full_name")
        if isinstance(full_name, str) and "/" in full_name:
            return f"git@bitbucket.org:{full_name}.git"

        workspace = payload.get("workspace")
        if isinstance(workspace, dict):
            workspace_slug = workspace.get("slug")
            if isinstance(workspace_slug, str) and workspace_slug.strip():
                return f"git@bitbucket.org:{workspace_slug.strip()}/{slug}.git"

        return None
