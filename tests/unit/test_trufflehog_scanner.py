from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

from ghmon_cli.trufflehog_scanner import TruffleHogScanner


def _config(tmp_path) -> dict:
    return {
        "general": {"output_dir": str(tmp_path)},
        "trufflehog": {},
    }


def test_trufflehog_scanner_init(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("ghmon_cli.trufflehog_scanner.shutil.which", lambda _cmd: "/usr/bin/tool")
    scanner = TruffleHogScanner(output_dir=tmp_path, config=_config(tmp_path))
    assert scanner.output_dir.exists()


def test_clean_finding_path(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("ghmon_cli.trufflehog_scanner.shutil.which", lambda _cmd: "/usr/bin/tool")
    scanner = TruffleHogScanner(output_dir=tmp_path, config=_config(tmp_path))
    repo_root = tmp_path / "repo"
    repo_root.mkdir()
    file_path = repo_root / "file.txt"
    file_path.write_text("x", encoding="utf-8")
    finding = {
        "SourceMetadata": {"Data": {"Filesystem": {"file": str(file_path)}}}
    }
    cleaned = scanner._clean_finding_path(finding, str(repo_root))
    assert cleaned["SourceMetadata"]["Data"]["Filesystem"]["file"] == "file.txt"


def test_run_git_command_handles_nonzero(monkeypatch, tmp_path) -> None:
    monkeypatch.setattr("ghmon_cli.trufflehog_scanner.shutil.which", lambda _cmd: "/usr/bin/tool")
    scanner = TruffleHogScanner(output_dir=tmp_path, config=_config(tmp_path))

    class DummyResult:
        returncode = 1
        stderr = "error"
        stdout = ""

    def fake_run(*_args, **_kwargs):
        return DummyResult()

    monkeypatch.setattr(subprocess, "run", fake_run)
    result = scanner._run_git_command(tmp_path, ["status"], "test")
    assert result.returncode == 1
