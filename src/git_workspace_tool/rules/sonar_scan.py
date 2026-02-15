from __future__ import annotations
"""Rule action to run SonarScanner analysis for a repository."""

import base64
import json
import os
from pathlib import Path
import re
import subprocess
import time
from collections.abc import Mapping
from urllib.error import URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from git_workspace_tool.domain.actions import Action
from git_workspace_tool.domain.entities import ActionResult, RepoContext
from git_workspace_tool.rules.sonar_runtime import SonarScannerRunner


class RunSonarScannerAction(Action):
    """Execute sonar scanner for one repository context.

    Configuration precedence:
    1. Explicit constructor arguments (`sonar_url`, `sonar_token`)
    2. Environment variables for URL: `SONARQUBE_URL` then `SONAR_HOST_URL`
    3. Environment variables for token: `SONARQUBE_TOKEN` then `SONAR_TOKEN`
    """

    _ANALYSIS_URL_PATTERN = re.compile(r"https?://[^\s]*dashboard\?id=[^\s]+")
    _CE_TASK_URL_PATTERN = re.compile(r"https?://[^\s]*/api/ce/task\?id=([A-Za-z0-9\-]+)")

    def __init__(
        self,
        scanner: SonarScannerRunner,
        *,
        sonar_url: str | None = None,
        sonar_token: str | None = None,
        wait_mode: str = "sync",
        submission_delay_seconds: float = 0.0,
        poll_interval_seconds: float = 5.0,
        wait_timeout_seconds: float = 1800.0,
        skip_unchanged: bool = True,
        force_scan: bool = False,
        state_file_relative_path: str = ".git/gitoteko_sonar_state.json",
        env: Mapping[str, str] | None = None,
    ) -> None:
        """Initialize sonar execution rule.

        Args:
            scanner: Rule-scoped scanner runner implementation.
            sonar_url: Optional explicit SonarQube URL override.
            sonar_token: Optional explicit token override.
            wait_mode: `sync` waits for CE task completion; `async` submits and continues.
            submission_delay_seconds: Minimum delay between submissions to avoid backpressure.
            poll_interval_seconds: Poll interval used in synchronous CE waiting.
            wait_timeout_seconds: Maximum wait time for one CE task in synchronous mode.
            skip_unchanged: Skip scanning when repository revision already scanned successfully.
            force_scan: Force scan even when revision did not change.
            state_file_relative_path: Per-repo file path used to persist last scanned revision.
            env: Optional environment mapping for tests/custom runtime.
        """
        self._scanner = scanner
        self._sonar_url = sonar_url.strip().rstrip("/") if sonar_url else None
        self._sonar_token = sonar_token.strip() if sonar_token else None
        self._wait_mode = wait_mode.strip().lower()
        if self._wait_mode not in {"sync", "async"}:
            raise ValueError("wait_mode must be one of: sync, async")

        self._submission_delay_seconds = max(0.0, submission_delay_seconds)
        self._poll_interval_seconds = max(0.1, poll_interval_seconds)
        self._wait_timeout_seconds = max(1.0, wait_timeout_seconds)
        self._skip_unchanged = skip_unchanged
        self._force_scan = force_scan
        self._state_file_relative_path = state_file_relative_path.strip() or ".git/gitoteko_sonar_state.json"
        self._env = env or os.environ
        self._last_submission_monotonic: float | None = None

    def execute(self, repo_context: RepoContext) -> ActionResult:
        """Run scanner and return per-repo execution summary."""
        sonar_url = self._resolve_sonar_url()
        sonar_token = self._resolve_sonar_token()

        if not sonar_url:
            return ActionResult(
                action_name=self.name,
                success=False,
                message="Missing Sonar URL (SONARQUBE_URL or SONAR_HOST_URL)",
            )

        if not sonar_token:
            return ActionResult(
                action_name=self.name,
                success=False,
                message="Missing Sonar token (SONARQUBE_TOKEN or SONAR_TOKEN)",
            )

        project_key = self._project_key(repo_context)
        revision = self._resolve_git_revision(repo_context.local_path)
        if self._skip_unchanged and not self._force_scan and revision:
            state_entry = self._load_state_entry(
                repo_path=repo_context.local_path,
                sonar_url=sonar_url,
                project_key=project_key,
            )
            if state_entry and state_entry.get("revision") == revision and state_entry.get("status") == "SUCCESS":
                return ActionResult(
                    action_name=self.name,
                    success=True,
                    message="Sonar scan skipped (repository unchanged)",
                    metadata={
                        "repo_slug": repo_context.repository.slug,
                        "project_key": project_key,
                        "revision": revision,
                        "reason": "unchanged",
                        "wait_mode": self._wait_mode,
                    },
                )

        self._throttle_submission_if_needed()

        exit_code, stdout, stderr = self._scanner.run(
            repo_path=repo_context.local_path,
            sonar_url=sonar_url,
            token=sonar_token,
        )
        self._last_submission_monotonic = time.monotonic()

        analysis_url = self._extract_analysis_url(stdout) or self._extract_analysis_url(stderr)
        ce_task_id = self._extract_ce_task_id(stdout) or self._extract_ce_task_id(stderr)
        success = exit_code == 0
        metadata: dict[str, object] = {
            "repo_slug": repo_context.repository.slug,
            "exit_code": exit_code,
            "analysis_url": analysis_url,
            "ce_task_id": ce_task_id,
            "wait_mode": self._wait_mode,
            "stdout": stdout,
            "stderr": stderr,
        }

        message = "Sonar scan completed" if success else "Sonar scan failed"
        final_status = "FAILED"

        if success and self._wait_mode == "sync":
            if not ce_task_id:
                success = False
                message = "Sonar scan submitted but CE task id was not found"
            else:
                wait_result = self._wait_for_ce_task(
                    sonar_url=sonar_url,
                    token=sonar_token,
                    ce_task_id=ce_task_id,
                )
                metadata.update(wait_result)
                ce_status = str(wait_result.get("ce_task_status", ""))
                if ce_status == "SUCCESS":
                    message = "Sonar scan completed and processed"
                    final_status = "SUCCESS"
                elif ce_status == "TIMEOUT":
                    success = False
                    message = "Sonar scan submitted but CE processing wait timed out"
                    final_status = "TIMEOUT"
                else:
                    success = False
                    message = f"Sonar scan submitted but CE processing ended with status {ce_status or 'UNKNOWN'}"
                    final_status = ce_status or "UNKNOWN"
        else:
            if success:
                final_status = "SUBMITTED"

        metadata.update(
            {
                "project_key": project_key,
                "revision": revision,
                "skip_unchanged": self._skip_unchanged,
                "force_scan": self._force_scan,
                "final_status": final_status,
            }
        )

        if success and revision:
            self._save_state_entry(
                repo_path=repo_context.local_path,
                sonar_url=sonar_url,
                project_key=project_key,
                revision=revision,
                final_status=final_status,
                analysis_url=analysis_url,
                ce_task_id=ce_task_id,
            )

        return ActionResult(
            action_name=self.name,
            success=success,
            message=message,
            metadata=metadata,
        )

    def _resolve_sonar_url(self) -> str | None:
        value = self._sonar_url or self._env.get("SONARQUBE_URL") or self._env.get("SONAR_HOST_URL")
        return value.rstrip("/") if value else None

    def _resolve_sonar_token(self) -> str | None:
        return self._sonar_token or self._env.get("SONARQUBE_TOKEN") or self._env.get("SONAR_TOKEN")

    def _extract_analysis_url(self, text: str) -> str | None:
        match = self._ANALYSIS_URL_PATTERN.search(text)
        return match.group(0) if match else None

    def _extract_ce_task_id(self, text: str) -> str | None:
        match = self._CE_TASK_URL_PATTERN.search(text)
        return match.group(1) if match else None

    def _throttle_submission_if_needed(self) -> None:
        if self._submission_delay_seconds <= 0 or self._last_submission_monotonic is None:
            return

        elapsed = time.monotonic() - self._last_submission_monotonic
        remaining = self._submission_delay_seconds - elapsed
        if remaining > 0:
            time.sleep(remaining)

    def _wait_for_ce_task(self, *, sonar_url: str, token: str, ce_task_id: str) -> dict[str, object]:
        deadline = time.monotonic() + self._wait_timeout_seconds
        last_error: str | None = None

        while time.monotonic() < deadline:
            try:
                task = self._fetch_ce_task(sonar_url=sonar_url, token=token, ce_task_id=ce_task_id)
            except RuntimeError as error:
                last_error = str(error)
                time.sleep(self._poll_interval_seconds)
                continue

            status = task.get("status")
            if status in {"SUCCESS", "FAILED", "CANCELED"}:
                return {
                    "ce_task_status": status,
                    "ce_task_url": f"{sonar_url}/api/ce/task?id={ce_task_id}",
                    "ce_analysis_id": task.get("analysisId"),
                    "ce_component_key": task.get("componentKey"),
                    "ce_error_message": task.get("errorMessage"),
                }

            time.sleep(self._poll_interval_seconds)

        return {
            "ce_task_status": "TIMEOUT",
            "ce_task_url": f"{sonar_url}/api/ce/task?id={ce_task_id}",
            "ce_poll_error": last_error,
        }

    def _fetch_ce_task(self, *, sonar_url: str, token: str, ce_task_id: str) -> dict[str, object]:
        endpoint = f"{sonar_url}/api/ce/task?id={quote(ce_task_id)}"
        auth_bytes = base64.b64encode(f"{token}:".encode("utf-8")).decode("ascii")
        request = Request(
            endpoint,
            headers={
                "Authorization": f"Basic {auth_bytes}",
                "Accept": "application/json",
            },
            method="GET",
        )

        try:
            with urlopen(request, timeout=self._poll_interval_seconds + 5.0) as response:
                payload = response.read().decode("utf-8")
        except URLError as error:
            raise RuntimeError(f"Unable to query Sonar CE task: {error}") from error

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as error:
            raise RuntimeError("Invalid JSON response from Sonar CE task API") from error

        task = data.get("task")
        if not isinstance(task, dict):
            raise RuntimeError("Unexpected Sonar CE task API response: missing task object")
        return task

    def _project_key(self, repo_context: RepoContext) -> str:
        value = f"{repo_context.workspace_id}_{repo_context.repository.slug}"
        allowed: list[str] = []
        for char in value:
            if char.isalnum() or char in {"_", "-", ".", ":"}:
                allowed.append(char)
            else:
                allowed.append("_")
        return "".join(allowed)

    def _resolve_git_revision(self, repo_path: Path) -> str | None:
        try:
            completed = subprocess.run(
                ["git", "rev-parse", "HEAD"],
                cwd=str(repo_path),
                check=False,
                text=True,
                capture_output=True,
            )
        except OSError:
            return None
        if completed.returncode != 0:
            return None
        revision = (completed.stdout or "").strip()
        return revision or None

    def _state_key(self, sonar_url: str, project_key: str) -> str:
        return f"{sonar_url}|{project_key}"

    def _state_file_path(self, repo_path: Path) -> Path:
        return repo_path / self._state_file_relative_path

    def _load_state_entry(self, *, repo_path: Path, sonar_url: str, project_key: str) -> dict[str, object] | None:
        state_path = self._state_file_path(repo_path)
        if not state_path.exists():
            return None
        try:
            payload = state_path.read_text(encoding="utf-8")
            data = json.loads(payload)
        except (OSError, json.JSONDecodeError):
            return None
        scans = data.get("scans")
        if not isinstance(scans, dict):
            return None
        entry = scans.get(self._state_key(sonar_url, project_key))
        return entry if isinstance(entry, dict) else None

    def _save_state_entry(
        self,
        *,
        repo_path: Path,
        sonar_url: str,
        project_key: str,
        revision: str,
        final_status: str,
        analysis_url: str | None,
        ce_task_id: str | None,
    ) -> None:
        state_path = self._state_file_path(repo_path)
        state_path.parent.mkdir(parents=True, exist_ok=True)

        data: dict[str, object]
        if state_path.exists():
            try:
                data = json.loads(state_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                data = {}
        else:
            data = {}

        scans = data.get("scans")
        if not isinstance(scans, dict):
            scans = {}

        scans[self._state_key(sonar_url, project_key)] = {
            "revision": revision,
            "status": final_status,
            "analysis_url": analysis_url,
            "ce_task_id": ce_task_id,
            "updated_at_epoch": int(time.time()),
        }
        data["scans"] = scans

        try:
            state_path.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        except OSError:
            # Non-fatal: scanning result should still be returned to caller.
            return
