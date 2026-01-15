from __future__ import annotations

import logging

from click.testing import CliRunner

from ghmon_cli import cli as cli_module


def test_colored_formatter() -> None:
    formatter = cli_module.ColoredFormatter(fmt="%(message)s")
    record = logging.LogRecord("test", logging.INFO, __file__, 10, "hello", args=(), exc_info=None)
    message = formatter.format(record)
    assert "hello" in message


def test_cli_help(monkeypatch) -> None:
    monkeypatch.setattr(cli_module.shutil, "which", lambda _cmd: "/usr/bin/tool")
    runner = CliRunner()
    result = runner.invoke(cli_module.cli, ["--help"])
    assert result.exit_code == 0
