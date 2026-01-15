from __future__ import annotations

from ghmon_cli.exceptions import ConfigError, ConfigValidationError, RateLimitError, CloneError, TruffleHogError, NotificationError


def test_config_error_chaining() -> None:
    original = ValueError("bad")
    err = ConfigError("oops", original_error=original)
    assert err.__cause__ is original


def test_config_validation_error_includes_path() -> None:
    err = ConfigValidationError("bad", config_path="/tmp/config.yaml")
    assert err.config_path == "/tmp/config.yaml"


def test_rate_limit_error_message() -> None:
    err = RateLimitError("GitHub", reset_time=1700000000)
    assert "Rate limit exceeded" in str(err)


def test_clone_error_message() -> None:
    err = CloneError("https://example.com", "boom", exit_code=128)
    assert "CloneError" in str(err)


def test_trufflehog_error_message() -> None:
    err = TruffleHogError("/repo", "cmd", 1, "stderr")
    assert "TruffleHogError" in str(err)


def test_notification_error_message() -> None:
    err = NotificationError("Discord", "fail", status_code=500, response_body="oops")
    assert "Discord" in str(err)
