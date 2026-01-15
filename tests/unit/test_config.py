from __future__ import annotations

import textwrap
from pathlib import Path

import pytest

from ghmon_cli.config import AppConfig, ConfigManager, GeneralConfig


def test_general_config_resolves_paths(tmp_path) -> None:
    config = GeneralConfig(output_dir=tmp_path / "out", trufflehog_path=tmp_path / "bin")
    assert isinstance(config.output_dir, Path)
    assert config.output_dir.exists() is False


def test_config_manager_with_yaml(tmp_path) -> None:
    yaml_content = textwrap.dedent(
        """
        general:
          log_level: INFO
          output_dir: ./scan_results
        github:
          enabled: true
          tokens:
            - ghp_abcdefghijklmnopqrstuvwxyz0123456789
        organizations:
          - acme
        """
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml_content, encoding="utf-8")

    manager = ConfigManager(config_path)
    config = manager.get_config_model()
    assert config.github.enabled is True
    assert config.organizations == ["acme"]


def test_config_manager_disables_missing_tokens(tmp_path, caplog) -> None:
    yaml_content = textwrap.dedent(
        """
        github:
          enabled: true
          tokens: []
        organizations:
          - acme
        """
    )
    config_path = tmp_path / "config.yaml"
    config_path.write_text(yaml_content, encoding="utf-8")

    manager = ConfigManager(config_path)
    config = manager.get_config_model()
    assert config.github.enabled is False


def test_app_config_rejects_bad_org() -> None:
    with pytest.raises(ValueError):
        AppConfig(organizations=[""])
