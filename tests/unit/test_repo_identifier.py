from __future__ import annotations

from datetime import datetime, timedelta

from ghmon_cli.repo_identifier import TokenPool


def test_token_pool_get_token_available() -> None:
    pool = TokenPool(["token1", "token2"])
    token = pool.get_token()
    assert token in {"token1", "token2"}


def test_token_pool_waits_for_reset(monkeypatch) -> None:
    pool = TokenPool(["token1"])
    future = datetime.now() + timedelta(seconds=1)
    pool.tokens[0].available = False
    pool.tokens[0].reset_time = future
    monkeypatch.setattr("ghmon_cli.repo_identifier.time.sleep", lambda *_args, **_kwargs: None)
    token = pool.get_token()
    assert token == "token1"


def test_mark_token_rate_limited() -> None:
    pool = TokenPool(["token1"])
    reset_time = datetime.now() + timedelta(seconds=5)
    pool.mark_token_rate_limited("token1", reset_time, remaining=0, limit=5000)
    assert pool.tokens[0].available is False
