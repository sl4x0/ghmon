from __future__ import annotations

from pathlib import Path

from ghmon_cli.scanner import Scanner


def _minimal_config(tmp_path) -> dict:
    return {
        "general": {"log_level": "info", "output_dir": str(tmp_path), "api_concurrency": 1},
        "trufflehog": {"concurrency": 1},
        "notifications": {"telegram": {"enabled": False}, "discord": {"enabled": False}},
        "operation": {"filtering": {"skip_repos_older_than_days": 0}},
        "github": {"enabled": False, "tokens": []},
        "gitlab": {"enabled": False, "tokens": []},
        "organizations": [],
    }


def test_markdown_summary_generation(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr(Scanner, "_init_components", lambda self: None)
    scanner = Scanner(config_dict=_minimal_config(tmp_path))
    stats = {"scan_mode": "SHALLOW", "total_orgs_processed": 1, "duration": 0.1}
    scanner._generate_markdown_summary(stats)
    summary_files = list(Path(scanner.output_dir).glob("scan_summary_*.md"))
    assert summary_files
