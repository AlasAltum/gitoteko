from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Mapping


SUPPORTED_PROVIDERS = {"bitbucket", "github", "gitlab"}


@dataclass(slots=True)
class AppConfig:
    provider: str
    workspace: str
    base_dir: Path
    dry_run: bool
    repo_slug: str | None
    max_repos: int | None
    repo_selection: str
    random_seed: int | None
    bitbucket_token: str | None
    bitbucket_username: str | None
    bitbucket_app_password: str | None
    bitbucket_api_base_url: str
    bitbucket_timeout_seconds: float


def load_config(args, env: Mapping[str, str]) -> AppConfig:
    provider = _normalize_empty(args.provider) or _normalize_empty(env.get("GIT_PROVIDER"))
    workspace = _normalize_empty(args.workspace) or _normalize_empty(env.get("GIT_WORKSPACE"))
    base_dir_raw = _normalize_empty(args.base_dir) or _normalize_empty(env.get("BASE_DIR"))
    repo_slug = _normalize_empty(args.repo_slug) or _normalize_empty(env.get("GIT_REPO_SLUG"))
    raw_max_repos = _normalize_empty(str(args.max_repos) if args.max_repos is not None else None) or _normalize_empty(
        env.get("GIT_MAX_REPOS")
    )
    repo_selection = _normalize_empty(args.repo_selection) or _normalize_empty(env.get("GIT_REPO_SELECTION")) or "first"
    raw_random_seed = _normalize_empty(str(args.random_seed) if args.random_seed is not None else None) or _normalize_empty(
        env.get("GIT_RANDOM_SEED")
    )

    if not provider:
        raise ValueError("Missing provider. Use --provider or set GIT_PROVIDER")

    if provider not in SUPPORTED_PROVIDERS:
        valid = ", ".join(sorted(SUPPORTED_PROVIDERS))
        raise ValueError(f"Unsupported provider '{provider}'. Allowed values: {valid}")

    if not workspace:
        raise ValueError("Missing workspace. Use --workspace or set GIT_WORKSPACE")

    if not base_dir_raw:
        raise ValueError("Missing base directory. Use --base-dir or set BASE_DIR")

    if repo_selection not in {"first", "random"}:
        raise ValueError("Invalid repository selection mode. Allowed values: first, random")

    max_repos: int | None = None
    if raw_max_repos is not None:
        try:
            max_repos = int(raw_max_repos)
        except ValueError as error:
            raise ValueError("GIT_MAX_REPOS/--max-repos must be an integer") from error
        if max_repos <= 0:
            raise ValueError("GIT_MAX_REPOS/--max-repos must be greater than 0")

    random_seed: int | None = None
    if raw_random_seed is not None:
        try:
            random_seed = int(raw_random_seed)
        except ValueError as error:
            raise ValueError("GIT_RANDOM_SEED/--random-seed must be an integer") from error

    base_dir = Path(base_dir_raw).expanduser()

    bitbucket_token = _normalize_empty(env.get("BITBUCKET_TOKEN"))
    bitbucket_username = _normalize_empty(env.get("BITBUCKET_USERNAME"))
    bitbucket_app_password = _normalize_empty(env.get("BITBUCKET_APP_PASSWORD"))
    bitbucket_api_base_url = _normalize_empty(env.get("BITBUCKET_API_BASE_URL")) or "https://api.bitbucket.org/2.0"

    raw_timeout = _normalize_empty(env.get("BITBUCKET_TIMEOUT_SECONDS"))
    try:
        bitbucket_timeout_seconds = float(raw_timeout) if raw_timeout else 30.0
    except ValueError as error:
        raise ValueError("BITBUCKET_TIMEOUT_SECONDS must be a number") from error

    return AppConfig(
        provider=provider,
        workspace=workspace,
        base_dir=base_dir,
        dry_run=args.dry_run,
        repo_slug=repo_slug,
        max_repos=max_repos,
        repo_selection=repo_selection,
        random_seed=random_seed,
        bitbucket_token=bitbucket_token,
        bitbucket_username=bitbucket_username,
        bitbucket_app_password=bitbucket_app_password,
        bitbucket_api_base_url=bitbucket_api_base_url,
        bitbucket_timeout_seconds=bitbucket_timeout_seconds,
    )


def _normalize_empty(value: str | None) -> str | None:
    if value is None:
        return None
    stripped = value.strip()
    return stripped if stripped else None
