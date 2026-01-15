from __future__ import annotations

import types

import pytest

from ghmon_cli.notifications import NotificationManager


class DummyResponse:
    def __init__(self, status_code=200, json_payload=None, headers=None, text="ok") -> None:
        self.status_code = status_code
        self._json = json_payload or {}
        self.headers = headers or {}
        self.text = text

    def json(self):
        return self._json

    def raise_for_status(self):
        if self.status_code >= 400:
            err = Exception("HTTPError")
            err.response = self  # type: ignore[attr-defined]
            raise err


class DummySession:
    def __init__(self, response: DummyResponse) -> None:
        self.response = response
        self.calls = []
        self.headers = {}

    def post(self, url, json=None, data=None, timeout=15):
        self.calls.append((url, json, data, timeout))
        return self.response


@pytest.fixture()
def notify_manager(monkeypatch) -> NotificationManager:
    monkeypatch.setattr("ghmon_cli.notifications.REQUESTS_AVAILABLE", True)
    mgr = NotificationManager({"telegram": {"enabled": False}, "discord": {"enabled": False}}, suppress_init_logging=True)
    mgr.session = DummySession(DummyResponse())
    return mgr


def test_escape_telegram_markdown_v2(notify_manager) -> None:
    escaped = notify_manager._escape_telegram_markdown_v2("hello_world")
    assert "\\_" in escaped


def test_parse_discord_retry_after(notify_manager) -> None:
    response = DummyResponse(json_payload={"retry_after": 5000})
    assert notify_manager._parse_discord_retry_after(response, 1.5, 30.0) == 5.0


def test_parse_telegram_retry_after_header(notify_manager) -> None:
    response = DummyResponse(headers={"Retry-After": "3"})
    assert notify_manager._parse_telegram_retry_after(response, 1.0, 10.0) == 3.0


def test_post_with_retries_success(monkeypatch, notify_manager, dummy_requests_module) -> None:
    notify_manager.session = DummySession(DummyResponse())
    monkeypatch.setattr("ghmon_cli.notifications.requests", dummy_requests_module)
    response = notify_manager._post_with_retries("Discord", "https://example.com", payload_json={})
    assert response.status_code == 200


def test_send_discord_message_truncates(monkeypatch, notify_manager) -> None:
    notify_manager.discord_enabled = True
    notify_manager.discord_webhook_url = "https://discord.com/api/webhooks/test"
    notify_manager.session = DummySession(DummyResponse())
    monkeypatch.setattr("ghmon_cli.notifications.REQUESTS_AVAILABLE", True)
    message = "x" * (notify_manager.DISCORD_MAX_MESSAGE_LENGTH + 20)
    assert notify_manager.send_discord_message(message, embeds=[{"description": "y" * 2000}])
