"""Global test configuration and fixtures for ghmon-cli."""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import types
import time
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))


@dataclass
class DummyResponse:
    status_code: int = 200
    text: str = "ok"
    headers: Dict[str, str] = None
    json_payload: Optional[Dict[str, Any]] = None

    def __post_init__(self) -> None:
        if self.headers is None:
            self.headers = {}

    def json(self) -> Dict[str, Any]:
        return self.json_payload or {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            error = Exception("HTTP error")
            error.response = self  # type: ignore[attr-defined]
            raise error


class DummySession:
    def __init__(self, responses: Optional[List[DummyResponse]] = None) -> None:
        self.responses = responses or [DummyResponse()]
        self.calls: List[Dict[str, Any]] = []

    def post(self, url: str, json: Optional[Dict[str, Any]] = None, data: Optional[Dict[str, Any]] = None, timeout: int = 15) -> DummyResponse:
        self.calls.append({"url": url, "json": json, "data": data, "timeout": timeout})
        if self.responses:
            return self.responses.pop(0)
        return DummyResponse()


@pytest.fixture()
def dummy_requests_module() -> types.SimpleNamespace:
    class DummyRequestException(Exception):
        def __init__(self, message: str, response: Optional[DummyResponse] = None) -> None:
            super().__init__(message)
            self.response = response

    class DummyHTTPError(DummyRequestException):
        pass

    class DummyTimeout(DummyRequestException):
        pass

    return types.SimpleNamespace(
        exceptions=types.SimpleNamespace(
            RequestException=DummyRequestException,
            HTTPError=DummyHTTPError,
            Timeout=DummyTimeout,
        )
    )


@pytest.fixture()
def temp_output_dir(tmp_path) -> str:
    return str(tmp_path)


@pytest.fixture()
def sample_repo() -> Dict[str, Any]:
    return {
        "full_name": "acme/widgets",
        "name": "widgets",
        "clone_url": "https://example.com/acme/widgets.git",
        "organization": "acme",
        "platform": "github",
        "private": True,
        "updated_at": "2024-01-01T00:00:00Z",
        "language": "python",
        "size": 2048,
        "stargazers_count": 42,
        "forks_count": 3,
    }


@pytest.fixture()
def sample_finding() -> Dict[str, Any]:
    return {
        "SourceMetadata": {
            "Data": {
                "Filesystem": {
                    "file": "src/app.py",
                    "line": 12,
                }
            }
        },
        "DetectorName": "TestDetector",
        "Redacted": "secret_****",
        "Raw": "secret_value",
        "Verified": True,
    }


@pytest.fixture(autouse=True)
def fast_sleep(monkeypatch) -> None:
    monkeypatch.setattr(time, "sleep", lambda *_args, **_kwargs: None)
