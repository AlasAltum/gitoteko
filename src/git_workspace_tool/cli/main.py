from __future__ import annotations

import argparse


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="gitoteko",
        description="Scan a Git workspace and execute a pluggable action pipeline per repository.",
    )

    parser.add_argument(
        "--provider",
        choices=["bitbucket", "github", "gitlab"],
        required=True,
        help="Git provider to use (only bitbucket is implemented in this version).",
    )
    parser.add_argument("--workspace", required=True, help="Workspace identifier.")
    parser.add_argument("--base-dir", required=True, help="Local base directory for repositories.")

    parser.add_argument("--languages", help="Override LANGUAGE_EXTENSIONS.")
    parser.add_argument("--language-report-csv", help="Override LANGUAGE_REPORT_CSV.")
    parser.add_argument("--sonar-url", help="Override SONARQUBE_URL/SONAR_HOST_URL.")
    parser.add_argument("--sonar-token", help="Override SONARQUBE_TOKEN/SONAR_TOKEN.")

    parser.add_argument("--skip-sonar", action="store_true")
    parser.add_argument("--skip-language-detection", action="store_true")
    parser.add_argument("--skip-sonar-file-generation", action="store_true")
    parser.add_argument("--dry-run", action="store_true")

    return parser


def main() -> int:
    parser = build_parser()
    parser.parse_args()
    return 0
