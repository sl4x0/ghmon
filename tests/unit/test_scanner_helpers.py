from __future__ import annotations

import logging
import types
from pathlib import Path

import pytest

from ghmon_cli.scanner import SimpleProgress, ScanContext, ScanResult, Scanner


def _minimal_config(tmp_path) -> dict:
    return {
        "general": {
            "log_level": "info",
            "output_dir": str(tmp_path),
            "api_concurrency": 2,
        },
        "trufflehog": {"concurrency": 1},
        "notifications": {"telegram": {"enabled": False}, "discord": {"enabled": False}},
        "operation": {"filtering": {"skip_repos_older_than_days": 0}},
        "github": {"enabled": False, "tokens": []},
        "gitlab": {"enabled": False, "tokens": []},
        "organizations": [],
    }


def test_simple_progress_update(monkeypatch) -> None:
    monkeypatch.setattr("ghmon_cli.scanner.shutil.get_terminal_size", lambda *_args, **_kwargs: types.SimpleNamespace(columns=80))
    progress = SimpleProgress("Testing", total=2)
    with progress:
        progress.update(advance=1)
    assert progress.completed_tasks == 1


def test_scan_context_init(tmp_path) -> None:
    context = ScanContext(_minimal_config(tmp_path), Path(tmp_path), shutdown_event=types.SimpleNamespace(is_set=lambda: False))
    assert context.stats["successful_scans"] == 0


def test_scan_result_to_dict() -> None:
    result = ScanResult(success=True)
    data = result.to_dict()
    assert data["success"] is True


def test_scanner_init_concurrency(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(Scanner, "_init_components", lambda self: None)
    config = _minimal_config(tmp_path)
    config["trufflehog"]["concurrency"] = "bad"
    config["general"]["api_concurrency"] = "bad"
    scanner = Scanner(config_dict=config)
    assert scanner.scan_threads == 5
    assert scanner.api_threads == 10


def test_should_skip_repository(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(Scanner, "_init_components", lambda self: None)
    scanner = Scanner(config_dict=_minimal_config(tmp_path))
    assert scanner._should_skip_repository({"name": "demo"}) is True
    assert scanner._should_skip_repository({"name": "docs"}) is True
    assert scanner._should_skip_repository({"name": "real", "size": 600 * 1024}) is True
    assert scanner._should_skip_repository({"name": "real", "language": "css"}) is True
    assert scanner._should_skip_repository({"name": "real"}) is False


def test_get_skip_reason(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(Scanner, "_init_components", lambda self: None)
    scanner = Scanner(config_dict=_minimal_config(tmp_path))
    assert scanner._get_skip_reason({"name": "demo"}) == "test/demo repository"


def test_prioritize_repositories(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(Scanner, "_init_components", lambda self: None)
    scanner = Scanner(config_dict=_minimal_config(tmp_path))
    repos = [
        {"full_name": "a", "name": "a", "private": False, "size": 10, "updated_at": "2024-01-01T00:00:00Z"},
        {"full_name": "b", "name": "b", "private": True, "size": 20, "updated_at": "2024-01-01T00:00:00Z"},
    ]
    prioritized = scanner._prioritize_repositories(repos)
    assert prioritized[0]["full_name"] == "b"


def test_process_scan_results(monkeypatch, tmp_path, sample_finding, sample_repo) -> None:
    monkeypatch.setattr(Scanner, "_init_components", lambda self: None)
    scanner = Scanner(config_dict=_minimal_config(tmp_path))
    notified = set()
    context = ScanContext(scanner.config, Path(scanner.output_dir), shutdown_event=types.SimpleNamespace(is_set=lambda: False))

    class DummyNotifier:
        def notify_newly_verified_repo_findings(self, repo_info, new_findings):
            return None

    scanner.notifier = DummyNotifier()

    scan_results = [
        {"success": True, "repository": sample_repo, "findings": [sample_finding]},
    ]
    result = scanner._process_scan_results(scan_results, notified, context)
    assert result.newly_notified_ids


def test_fetch_sha_for_repo(monkeypatch, tmp_path, sample_repo) -> None:
    monkeypatch.setattr(Scanner, "_init_components", lambda self: None)
    scanner = Scanner(config_dict=_minimal_config(tmp_path))

    class DummyIdentifier:
        def get_latest_commit_sha(self, _repo):
            return "a" * 40

    scanner.repo_identifier = DummyIdentifier()
    repo_name, sha = scanner._fetch_sha_for_repo(sample_repo)
    assert repo_name == "acme/widgets"
    assert sha == "a" * 40


def test_generate_markdown_summary(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(Scanner, "_init_components", lambda self: None)
    scanner = Scanner(config_dict=_minimal_config(tmp_path))
    stats = {"scan_mode": "SHALLOW", "total_orgs_processed": 1, "duration": 1.2}
    scanner._generate_markdown_summary(stats)
    summaries = list(Path(scanner.output_dir).glob("scan_summary_*.md"))
    assert summaries
