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
from urllib.error import HTTPError, URLError
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
        scanner: SonarScannerRunner | None = None,
        *,
        sonar_url: str | None = None,
        sonar_token: str | None = None,
        execution_mode: str = "cloud",
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
            scanner: Optional rule-scoped scanner runner implementation (required in local mode).
            sonar_url: Optional explicit SonarQube URL override.
            sonar_token: Optional explicit token override.
            execution_mode: `cloud` queries Sonar server APIs; `local` executes `sonar-scanner`.
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
        self._execution_mode = execution_mode.strip().lower()
        if self._execution_mode not in {"cloud", "local", "ci"}:
            raise ValueError("execution_mode must be one of: cloud, local, ci")
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
        branch_name = self._resolve_git_branch(repo_context.local_path)
        branch_analysis_enabled = self._is_truthy(self._env.get("SONAR_ENABLE_BRANCH_ANALYSIS", "false"))
        scanner_branch_name = branch_name if branch_analysis_enabled else None
        revision = self._resolve_git_revision(repo_context.local_path)
        if self._skip_unchanged and not self._force_scan and revision:
            state_entry = self._load_state_entry(
                repo_path=repo_context.local_path,
                sonar_url=sonar_url,
                project_key=project_key,
                branch_name=scanner_branch_name,
            )
            if state_entry and state_entry.get("revision") == revision and state_entry.get("status") == "SUCCESS":
                return ActionResult(
                    action_name=self.name,
                    success=True,
                    message="Sonar scan skipped (repository unchanged)",
                    metadata={
                        "repo_slug": repo_context.repository.slug,
                        "project_key": project_key,
                        "branch_name": branch_name,
                        "branch_analysis_enabled": branch_analysis_enabled,
                        "revision": revision,
                        "reason": "unchanged",
                        "wait_mode": self._wait_mode,
                    },
                )

        self._throttle_submission_if_needed()
        if self._execution_mode == "cloud":
            success, message, final_status, metadata = self._execute_cloud_status_check(
                sonar_url=sonar_url,
                token=sonar_token,
                repo_context=repo_context,
                project_key=project_key,
            )
        elif self._execution_mode == "ci":
            success, message, final_status, metadata = self._execute_ci_trigger(
                sonar_url=sonar_url,
                token=sonar_token,
                repo_context=repo_context,
                project_key=project_key,
            )
        else:
            if self._scanner is None:
                raise RuntimeError("Local Sonar execution requires a scanner runner")

            exit_code, stdout, stderr = self._scanner.run(
                repo_path=repo_context.local_path,
                sonar_url=sonar_url,
                token=sonar_token,
                branch_name=scanner_branch_name,
            )
            self._last_submission_monotonic = time.monotonic()

            analysis_url = self._extract_analysis_url(stdout) or self._extract_analysis_url(stderr)
            ce_task_id = self._extract_ce_task_id(stdout) or self._extract_ce_task_id(stderr)
            success = exit_code == 0
            metadata = {
                "repo_slug": repo_context.repository.slug,
                "execution_mode": self._execution_mode,
                "exit_code": exit_code,
                "analysis_url": analysis_url,
                "ce_task_id": ce_task_id,
                "branch_name": branch_name,
                "branch_analysis_enabled": branch_analysis_enabled,
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

        analysis_url_value = metadata.get("analysis_url")
        analysis_url = analysis_url_value if isinstance(analysis_url_value, str) else None
        ce_task_id_value = metadata.get("ce_task_id")
        ce_task_id = ce_task_id_value if isinstance(ce_task_id_value, str) else None

        if success and revision:
            self._save_state_entry(
                repo_path=repo_context.local_path,
                sonar_url=sonar_url,
                project_key=project_key,
                branch_name=scanner_branch_name,
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

    def _execute_ci_trigger(
        self,
        *,
        sonar_url: str,
        token: str,
        repo_context: RepoContext,
        project_key: str,
    ) -> tuple[bool, str, str, dict[str, object]]:
        self._last_submission_monotonic = time.monotonic()

        provider = (self._env.get("SONAR_CI_PROVIDER") or "bitbucket").strip().lower()
        if provider != "bitbucket":
            raise RuntimeError("SONAR_CI_PROVIDER must be 'bitbucket' for CI execution mode")

        pipeline_data = self._trigger_bitbucket_pipeline(
            workspace_id=repo_context.workspace_id,
            repo_slug=repo_context.repository.slug,
            project_key=project_key,
            sonar_url=sonar_url,
            sonar_token=token,
        )

        verify_sonar_step = self._is_truthy(self._env.get("SONAR_CI_VERIFY_SONAR_STEP", "true"))
        sonar_step_detected = None
        fallback_triggered = False
        fallback_selector = (self._env.get("SONAR_CI_SONAR_SELECTOR") or "sonar-scan").strip()

        if verify_sonar_step:
            sonar_step_detected = self._pipeline_has_sonar_step(
                workspace_id=repo_context.workspace_id,
                repo_slug=repo_context.repository.slug,
                pipeline_uuid=pipeline_data.get("uuid"),
            )

            used_selector = pipeline_data.get("selector")
            if (
                sonar_step_detected is False
                and fallback_selector
                and fallback_selector != used_selector
            ):
                fallback_triggered = True
                pipeline_data = self._trigger_bitbucket_pipeline(
                    workspace_id=repo_context.workspace_id,
                    repo_slug=repo_context.repository.slug,
                    project_key=project_key,
                    sonar_url=sonar_url,
                    sonar_token=token,
                    selector_override=fallback_selector,
                )
                sonar_step_detected = self._pipeline_has_sonar_step(
                    workspace_id=repo_context.workspace_id,
                    repo_slug=repo_context.repository.slug,
                    pipeline_uuid=pipeline_data.get("uuid"),
                )

            if sonar_step_detected is False:
                raise RuntimeError(
                    "Triggered CI pipeline did not include a Sonar step. "
                    "Configure SONAR_CI_PIPELINE_SELECTOR/SONAR_CI_SONAR_SELECTOR to a Sonar pipeline."
                )

        metadata = {
            "repo_slug": repo_context.repository.slug,
            "execution_mode": self._execution_mode,
            "ci_provider": provider,
            "ci_pipeline_uuid": pipeline_data.get("uuid"),
            "ci_pipeline_build_number": pipeline_data.get("build_number"),
            "ci_pipeline_state": pipeline_data.get("state"),
            "ci_pipeline_url": pipeline_data.get("url"),
            "ci_pipeline_selector": pipeline_data.get("selector"),
            "ci_sonar_step_detected": sonar_step_detected,
            "ci_fallback_triggered": fallback_triggered,
            "analysis_url": f"{sonar_url}/dashboard?id={quote(project_key)}",
        }
        return True, "Sonar CI pipeline triggered", "SUBMITTED", metadata

    def _trigger_bitbucket_pipeline(
        self,
        *,
        workspace_id: str,
        repo_slug: str,
        project_key: str,
        sonar_url: str,
        sonar_token: str,
        selector_override: str | None = None,
    ) -> dict[str, object]:
        api_base = (self._env.get("BITBUCKET_API_BASE_URL") or "https://api.bitbucket.org/2.0").rstrip("/")
        encoded_workspace = quote(workspace_id, safe="")
        encoded_slug = quote(repo_slug, safe="")
        repository_url = f"{api_base}/repositories/{encoded_workspace}/{encoded_slug}"
        pipelines_url = f"{repository_url}/pipelines/"

        ref_name = (self._env.get("SONAR_CI_REF_NAME") or "").strip() or self._fetch_bitbucket_main_branch(repository_url)
        selector_pattern = (selector_override or (self._env.get("SONAR_CI_PIPELINE_SELECTOR") or "")).strip()
        forward_sonar_env = self._is_truthy(self._env.get("SONAR_CI_FORWARD_SONAR_ENV", "false"))

        target: dict[str, object] = {
            "type": "pipeline_ref_target",
            "ref_type": "branch",
            "ref_name": ref_name,
        }
        if selector_pattern:
            target["selector"] = {
                "type": "custom",
                "pattern": selector_pattern,
            }

        payload: dict[str, object] = {"target": target}
        variables: list[dict[str, object]] = [
            {"key": "SONAR_PROJECT_KEY", "value": project_key, "secured": False},
        ]
        if forward_sonar_env:
            variables.extend(
                [
                    {"key": "SONAR_HOST_URL", "value": sonar_url, "secured": False},
                    {"key": "SONAR_TOKEN", "value": sonar_token, "secured": True},
                ]
            )
        payload["variables"] = variables

        headers = self._build_bitbucket_auth_headers()
        headers.update({"Accept": "application/json", "Content-Type": "application/json"})
        request = Request(
            pipelines_url,
            data=json.dumps(payload).encode("utf-8"),
            headers=headers,
            method="POST",
        )

        try:
            with urlopen(request, timeout=self._poll_interval_seconds + 10.0) as response:
                body = response.read().decode("utf-8")
        except HTTPError as error:
            details = ""
            try:
                details = error.read().decode("utf-8")
            except Exception:
                details = ""
            raise RuntimeError(
                f"Unable to trigger Bitbucket pipeline for {workspace_id}/{repo_slug}: HTTP {error.code} {details}".strip()
            ) from error
        except URLError as error:
            raise RuntimeError(f"Unable to trigger Bitbucket pipeline: {error}") from error

        try:
            data = json.loads(body)
        except json.JSONDecodeError as error:
            raise RuntimeError("Invalid JSON response from Bitbucket pipelines API") from error

        links = data.get("links") if isinstance(data, dict) else None
        html = links.get("html") if isinstance(links, dict) else None
        pipeline_url = html.get("href") if isinstance(html, dict) else None
        state = data.get("state") if isinstance(data, dict) else None
        state_name = state.get("name") if isinstance(state, dict) else None
        return {
            "uuid": data.get("uuid") if isinstance(data, dict) else None,
            "build_number": data.get("build_number") if isinstance(data, dict) else None,
            "state": state_name,
            "url": pipeline_url,
            "selector": selector_pattern or None,
        }

    def _pipeline_has_sonar_step(
        self,
        *,
        workspace_id: str,
        repo_slug: str,
        pipeline_uuid: object,
    ) -> bool | None:
        if not isinstance(pipeline_uuid, str) or not pipeline_uuid.strip():
            return None

        api_base = (self._env.get("BITBUCKET_API_BASE_URL") or "https://api.bitbucket.org/2.0").rstrip("/")
        encoded_workspace = quote(workspace_id, safe="")
        encoded_slug = quote(repo_slug, safe="")
        encoded_uuid = quote(pipeline_uuid.strip(), safe="{}-")
        steps_url = f"{api_base}/repositories/{encoded_workspace}/{encoded_slug}/pipelines/{encoded_uuid}/steps/"

        request = Request(
            steps_url,
            headers={**self._build_bitbucket_auth_headers(), "Accept": "application/json"},
            method="GET",
        )

        try:
            with urlopen(request, timeout=self._poll_interval_seconds + 10.0) as response:
                body = response.read().decode("utf-8")
        except HTTPError:
            return None
        except URLError:
            return None

        try:
            data = json.loads(body)
        except json.JSONDecodeError:
            return None

        values = data.get("values") if isinstance(data, dict) else None
        if not isinstance(values, list):
            return None

        for item in values:
            item_blob = json.dumps(item).lower()
            if "sonar" in item_blob or "sonar-scanner" in item_blob:
                return True

        return False

    def _fetch_bitbucket_main_branch(self, repository_url: str) -> str:
        request = Request(
            repository_url,
            headers={**self._build_bitbucket_auth_headers(), "Accept": "application/json"},
            method="GET",
        )
        try:
            with urlopen(request, timeout=self._poll_interval_seconds + 10.0) as response:
                body = response.read().decode("utf-8")
        except HTTPError as error:
            raise RuntimeError(f"Unable to resolve repository main branch: HTTP {error.code}") from error
        except URLError as error:
            raise RuntimeError(f"Unable to resolve repository main branch: {error}") from error

        try:
            data = json.loads(body)
        except json.JSONDecodeError as error:
            raise RuntimeError("Invalid JSON response from Bitbucket repository API") from error

        mainbranch = data.get("mainbranch") if isinstance(data, dict) else None
        branch_name = mainbranch.get("name") if isinstance(mainbranch, dict) else None
        if isinstance(branch_name, str) and branch_name.strip():
            return branch_name.strip()

        return "main"

    def _build_bitbucket_auth_headers(self) -> dict[str, str]:
        token = (self._env.get("BITBUCKET_TOKEN") or "").strip()
        if token:
            return {"Authorization": f"Bearer {token}"}

        username = (self._env.get("BITBUCKET_USERNAME") or "").strip()
        app_password = (self._env.get("BITBUCKET_APP_PASSWORD") or "").strip()
        if username and app_password:
            encoded = base64.b64encode(f"{username}:{app_password}".encode("utf-8")).decode("ascii")
            return {"Authorization": f"Basic {encoded}"}

        raise RuntimeError(
            "Missing Bitbucket authentication for CI trigger. Set BITBUCKET_TOKEN or BITBUCKET_USERNAME/BITBUCKET_APP_PASSWORD"
        )

    def _is_truthy(self, value: str) -> bool:
        return value.strip().lower() in {"1", "true", "yes", "on"}

    def _execute_cloud_status_check(
        self,
        *,
        sonar_url: str,
        token: str,
        repo_context: RepoContext,
        project_key: str,
    ) -> tuple[bool, str, str, dict[str, object]]:
        self._last_submission_monotonic = time.monotonic()

        quality_gate = self._fetch_quality_gate_status(
            sonar_url=sonar_url,
            token=token,
            project_key=project_key,
        )

        status = str(quality_gate.get("status") or "UNKNOWN")
        endpoint_error = quality_gate.get("endpoint_error")
        success = status in {"OK", "NONE"}
        message = "Sonar cloud status fetched"
        if status == "ERROR":
            message = "Sonar cloud quality gate failed"
        elif status == "UNKNOWN" and endpoint_error:
            success = True
            message = "Sonar quality gate endpoint unavailable; status check skipped"

        metadata = {
            "repo_slug": repo_context.repository.slug,
            "execution_mode": self._execution_mode,
            "wait_mode": self._wait_mode,
            "project_key": project_key,
            "quality_gate_status": status,
            "quality_gate_url": f"{sonar_url}/api/qualitygates/project_status?projectKey={quote(project_key)}",
            "quality_gate_conditions": quality_gate.get("conditions"),
            "quality_gate_endpoint_error": endpoint_error,
            "analysis_url": f"{sonar_url}/dashboard?id={quote(project_key)}",
        }

        if status == "UNKNOWN" and endpoint_error:
            final_status = "SKIPPED_STATUS_CHECK"
        else:
            final_status = "SUCCESS" if success else status
        return success, message, final_status, metadata

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

    def _fetch_quality_gate_status(self, *, sonar_url: str, token: str, project_key: str) -> dict[str, object]:
        endpoint = f"{sonar_url}/api/qualitygates/project_status?projectKey={quote(project_key)}"
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
        except HTTPError as error:
            if error.code == 404:
                return {
                    "status": "UNKNOWN",
                    "conditions": [],
                    "endpoint_error": "HTTP 404",
                }
            raise RuntimeError(f"Unable to query Sonar quality gate status: {error}") from error
        except URLError as error:
            raise RuntimeError(f"Unable to query Sonar quality gate status: {error}") from error

        try:
            data = json.loads(payload)
        except json.JSONDecodeError as error:
            raise RuntimeError("Invalid JSON response from Sonar quality gate API") from error

        project_status = data.get("projectStatus")
        if not isinstance(project_status, dict):
            raise RuntimeError("Unexpected Sonar quality gate API response: missing projectStatus object")
        return project_status

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

    def _resolve_git_branch(self, repo_path: Path) -> str | None:
        try:
            current = subprocess.run(
                ["git", "rev-parse", "--abbrev-ref", "HEAD"],
                cwd=str(repo_path),
                check=False,
                text=True,
                capture_output=True,
            )
        except OSError:
            current = None

        if current and current.returncode == 0:
            branch = (current.stdout or "").strip()
            if branch and branch != "HEAD":
                return branch

        try:
            remote_head = subprocess.run(
                ["git", "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
                cwd=str(repo_path),
                check=False,
                text=True,
                capture_output=True,
            )
        except OSError:
            return None

        if remote_head.returncode != 0:
            return None

        value = (remote_head.stdout or "").strip()
        if value.startswith("origin/"):
            return value.split("/", 1)[1] or None
        return None

    def _state_key(self, sonar_url: str, project_key: str, branch_name: str | None) -> str:
        branch_value = branch_name or "default"
        return f"{sonar_url}|{project_key}|{branch_value}"

    def _state_file_path(self, repo_path: Path) -> Path:
        return repo_path / self._state_file_relative_path

    def _load_state_entry(
        self,
        *,
        repo_path: Path,
        sonar_url: str,
        project_key: str,
        branch_name: str | None,
    ) -> dict[str, object] | None:
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
        entry = scans.get(self._state_key(sonar_url, project_key, branch_name))
        return entry if isinstance(entry, dict) else None

    def _save_state_entry(
        self,
        *,
        repo_path: Path,
        sonar_url: str,
        project_key: str,
        branch_name: str | None,
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

        scans[self._state_key(sonar_url, project_key, branch_name)] = {
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
