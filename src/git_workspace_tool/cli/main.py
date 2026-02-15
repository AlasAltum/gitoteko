from __future__ import annotations

import argparse
import logging
import os
from collections.abc import Mapping
from pathlib import Path

from git_workspace_tool.adapters.filesystem.local_filesystem import LocalFileSystemAdapter
from git_workspace_tool.adapters.git_client.shell_git_client import ShellGitClientAdapter
from git_workspace_tool.adapters.git_providers.bitbucket_cloud import BitbucketCloudGitProviderAdapter
from git_workspace_tool.application.use_cases.git_workspace_scanner import (
    GitWorkspaceScanner,
    ScanExecutionSummary,
)
from git_workspace_tool.cli.config import load_config
from git_workspace_tool.domain.actions import ActionPipeline
from git_workspace_tool.logging_utils import configure_logging
from git_workspace_tool.rules import (
    DetectLanguagesAction,
    GenerateSonarPropertiesAction,
    RunSonarScannerAction,
    ShellSonarScannerRunner,
    WriteLanguageReportCsvAction,
)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitoteko",
        description="Scan a Git workspace and execute a pluggable action pipeline per repository.",
    )

    parser.add_argument(
        "--provider",
        choices=["bitbucket", "github", "gitlab"],
        required=False,
        help="Git provider to use. Falls back to GIT_PROVIDER.",
    )
    parser.add_argument("--workspace", required=False, help="Workspace identifier. Falls back to GIT_WORKSPACE.")
    parser.add_argument("--base-dir", required=False, help="Local base directory for repositories. Falls back to BASE_DIR.")
    parser.add_argument(
        "--repo-slug",
        required=False,
        help="Optional single repository slug filter. Falls back to GIT_REPO_SLUG.",
    )
    parser.add_argument(
        "--max-repos",
        type=int,
        required=False,
        help="Optional limit of repositories to process. Falls back to GIT_MAX_REPOS.",
    )
    parser.add_argument(
        "--repo-selection",
        choices=["first", "random"],
        required=False,
        help="Repository selection mode when limiting: first or random. Falls back to GIT_REPO_SELECTION.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        required=False,
        help="Optional random seed used when --repo-selection=random. Falls back to GIT_RANDOM_SEED.",
    )
    parser.add_argument("--dry-run", action="store_true")

    return parser


def main() -> int:
    configure_logging(os.environ.get("LOG_LEVEL", "INFO"))
    logger = logging.getLogger(__name__)

    parser = build_parser()
    args = parser.parse_args()
    try:
        config = load_config(args=args, env=os.environ)
    except ValueError as error:
        parser.error(str(error))

    logger.info(
        "cli configuration resolved",
        extra={
            "event": "cli.config.resolved",
            "provider": config.provider,
            "workspace": config.workspace,
            "base_dir": str(config.base_dir),
            "dry_run": config.dry_run,
            "repo_slug": config.repo_slug,
            "max_repos": config.max_repos,
            "repo_selection": config.repo_selection,
            "random_seed": config.random_seed,
            "stop_on_error": _parse_bool(os.environ.get("GIT_STOP_ON_ERROR", "false"), "GIT_STOP_ON_ERROR"),
        },
    )

    try:
        scanner = _build_scanner(config.provider, config)
        summary = scanner.execute(
            workspace=config.workspace,
            base_dir=config.base_dir,
            dry_run=config.dry_run,
            only_repo_slug=config.repo_slug,
            max_repos=config.max_repos,
            repo_selection=config.repo_selection,
            random_seed=config.random_seed,
            stop_on_error=_parse_bool(os.environ.get("GIT_STOP_ON_ERROR", "false"), "GIT_STOP_ON_ERROR"),
        )
    except RuntimeError as error:
        logger.exception("cli execution failed", extra={"event": "cli.execution.failed"})
        parser.error(str(error))

    _print_summary(summary)
    return 0


def _build_scanner(provider: str, config) -> GitWorkspaceScanner:
    if provider != "bitbucket":
        raise RuntimeError(f"Provider '{provider}' is not implemented yet")

    provider_adapter = BitbucketCloudGitProviderAdapter(
        api_base_url=config.bitbucket_api_base_url,
        token=config.bitbucket_token,
        username=config.bitbucket_username,
        app_password=config.bitbucket_app_password,
        timeout_seconds=config.bitbucket_timeout_seconds,
    )

    return GitWorkspaceScanner(
        git_provider=provider_adapter,
        git_client=ShellGitClientAdapter(),
        filesystem=LocalFileSystemAdapter(),
        action_pipeline=_build_action_pipeline(config.base_dir, os.environ),
    )


def _build_action_pipeline(base_dir: Path, env: Mapping[str, str]) -> ActionPipeline:
    raw_actions = (env.get("GIT_ACTIONS") or "").strip()
    if not raw_actions:
        return ActionPipeline([])

    action_names = [item.strip().lower() for item in raw_actions.split(",") if item.strip()]
    actions = []

    for action_name in action_names:
        if action_name == "detect-languages":
            raw_extensions = env.get(
                "LANGUAGE_DETECTION_EXTENSIONS",
                ".py,.ts,.js,.java,.tf,.yml,.yaml,.json,.xml,.go,.cs,.rb,.php,.kt,.scala,.sql,.sh,.dockerfile",
            )
            extensions = [item.strip() for item in raw_extensions.split(",") if item.strip()]
            actions.append(DetectLanguagesAction(extensions=extensions))
            continue

        if action_name == "write-language-csv":
            csv_path = Path(env.get("LANGUAGE_REPORT_CSV", str(base_dir / "language_report.csv"))).expanduser()
            regenerate = _parse_bool(env.get("LANGUAGE_REPORT_REGENERATE", "false"), "LANGUAGE_REPORT_REGENERATE")
            actions.append(WriteLanguageReportCsvAction(report_csv_path=csv_path, regenerate=regenerate))
            continue

        if action_name == "generate-sonar-properties":
            overwrite = _parse_bool(env.get("SONAR_PROPERTIES_OVERWRITE", "false"), "SONAR_PROPERTIES_OVERWRITE")
            java_binaries_path = (env.get("SONAR_JAVA_BINARIES_PATH") or "target/classes").strip()
            actions.append(
                GenerateSonarPropertiesAction(
                    overwrite=overwrite,
                    java_binaries_path=java_binaries_path,
                )
            )
            continue

        if action_name == "run-sonar-scan":
            scanner_executable = (env.get("SONAR_SCANNER_EXECUTABLE") or "sonar-scanner").strip()
            scanner_timeout_seconds = _parse_float(
                env.get("SONAR_SCANNER_TIMEOUT_SECONDS", "1800"),
                "SONAR_SCANNER_TIMEOUT_SECONDS",
                minimum=1.0,
            )
            wait_mode = (env.get("SONAR_WAIT_MODE") or "sync").strip().lower()
            if wait_mode not in {"sync", "async"}:
                raise RuntimeError("SONAR_WAIT_MODE must be one of: sync, async")

            submission_delay_seconds = _parse_float(
                env.get("SONAR_SUBMISSION_DELAY_SECONDS", "0"),
                "SONAR_SUBMISSION_DELAY_SECONDS",
                minimum=0.0,
            )
            poll_interval_seconds = _parse_float(
                env.get("SONAR_SYNC_POLL_INTERVAL_SECONDS", "5"),
                "SONAR_SYNC_POLL_INTERVAL_SECONDS",
                minimum=0.1,
            )
            wait_timeout_seconds = _parse_float(
                env.get("SONAR_SYNC_TIMEOUT_SECONDS", "1800"),
                "SONAR_SYNC_TIMEOUT_SECONDS",
                minimum=1.0,
            )
            skip_unchanged = _parse_bool(
                env.get("SONAR_SKIP_UNCHANGED", "true"),
                "SONAR_SKIP_UNCHANGED",
            )
            force_scan = _parse_bool(
                env.get("SONAR_FORCE_SCAN", "false"),
                "SONAR_FORCE_SCAN",
            )
            state_file_relative_path = (env.get("SONAR_STATE_FILE") or ".git/gitoteko_sonar_state.json").strip()

            scanner = ShellSonarScannerRunner(
                scanner_executable=scanner_executable,
                timeout_seconds=scanner_timeout_seconds,
            )
            actions.append(
                RunSonarScannerAction(
                    scanner=scanner,
                    wait_mode=wait_mode,
                    submission_delay_seconds=submission_delay_seconds,
                    poll_interval_seconds=poll_interval_seconds,
                    wait_timeout_seconds=wait_timeout_seconds,
                    skip_unchanged=skip_unchanged,
                    force_scan=force_scan,
                    state_file_relative_path=state_file_relative_path,
                    env=env,
                )
            )
            continue

        raise RuntimeError(
            "Unknown action in GIT_ACTIONS: "
            f"'{action_name}'. Allowed values: detect-languages, write-language-csv, "
            "generate-sonar-properties, run-sonar-scan"
        )

    return ActionPipeline(actions)


def _parse_bool(value: str, name: str) -> bool:
    normalized = value.strip().lower()
    if normalized in {"1", "true", "yes", "on"}:
        return True
    if normalized in {"0", "false", "no", "off"}:
        return False
    raise RuntimeError(f"{name} must be a boolean (true/false)")


def _parse_float(value: str, name: str, *, minimum: float) -> float:
    try:
        parsed = float(value)
    except ValueError as error:
        raise RuntimeError(f"{name} must be a number") from error
    if parsed < minimum:
        raise RuntimeError(f"{name} must be >= {minimum}")
    return parsed


def _print_summary(summary: ScanExecutionSummary) -> None:
    mode = "DRY-RUN" if summary.dry_run else "RUN"
    print(f"[{mode}] Workspace: {summary.workspace}")
    print(f"Base directory: {summary.base_dir}")
    print(f"Repositories discovered: {len(summary.repositories)}")
    print(f"Successful repositories: {summary.successful_repositories}")
    print(f"Failed repositories: {summary.failed_repositories}")

    for item in summary.repositories:
        action_list = ", ".join(item.planned_actions) if item.planned_actions else "(no actions configured)"
        status = "ok" if item.success else "failed"
        print(f"- {item.repo_slug}: {item.sync_operation} -> {item.local_path} [{status}]")
        print(f"  planned actions: {action_list}")
        if item.error:
            print(f"  error: {item.error}")
