from __future__ import annotations

import json
import os

import pytest

from ghmon_cli import state


def test_full_scan_state_roundtrip(temp_output_dir) -> None:
    orgs = {"Acme", "Beta"}
    state.save_full_scan_state(temp_output_dir, orgs)
    loaded = state.load_full_scan_state(temp_output_dir)
    assert loaded == {"acme", "beta"}


def test_notified_finding_roundtrip(temp_output_dir) -> None:
    finding_id = ("repo", "file.py", 10, "snippet", "Detector")
    state.save_notified_finding_ids(temp_output_dir, {finding_id})
    loaded = state.load_notified_finding_ids(temp_output_dir)
    assert finding_id in loaded


def test_repo_commit_state_roundtrip(temp_output_dir) -> None:
    commit_state = {"acme": {"repo": "a" * 40}}
    state.save_repo_commit_state(temp_output_dir, commit_state)
    loaded = state.load_repo_commit_state(temp_output_dir)
    assert loaded == commit_state


def test_parse_invalid_finding_id_item() -> None:
    assert state._parse_finding_id_item(["repo", "file", "bad", "snippet", "Detector"]) is None
    assert state._parse_finding_id_item("bad") is None


def test_load_state_corrupt_json(temp_output_dir) -> None:
    path = state.get_finding_state_path(temp_output_dir)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("{")
    assert state.load_notified_finding_ids(temp_output_dir) == set()


def test_ensure_output_dir_failure(monkeypatch) -> None:
    def raise_error(_path, exist_ok=True):
        raise OSError("nope")

    monkeypatch.setattr(os, "makedirs", raise_error)
    with pytest.raises(IOError):
        state._ensure_output_dir("/invalid")
