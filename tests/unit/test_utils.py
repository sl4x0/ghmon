from __future__ import annotations

from ghmon_cli import utils


def test_create_finding_id_valid(sample_finding) -> None:
    finding_id = utils.create_finding_id("acme/widgets", sample_finding)
    assert finding_id is not None
    assert finding_id[0] == "acme/widgets"
    assert finding_id[1] == "src/app.py"


def test_create_finding_id_missing_path() -> None:
    finding_id = utils.create_finding_id("acme/widgets", {"line": 1, "Raw": "x"})
    assert finding_id is None


def test_create_finding_id_invalid_line() -> None:
    finding = {
        "SourceMetadata": {"Data": {"Filesystem": {"file": "a/b.py", "line": "nope"}}},
        "Raw": "secret",
        "DetectorName": "Detector",
    }
    assert utils.create_finding_id("acme/widgets", finding) is None


def test_parse_line_number() -> None:
    assert utils._parse_line_number("5", "repo") == 5
    assert utils._parse_line_number(-1, "repo") == -1
    assert utils._parse_line_number(None, "repo") == -1


def test_extract_and_truncate_snippet() -> None:
    finding = {"Raw": "x" * 200}
    snippet = utils._extract_and_truncate_snippet(finding)
    assert "..." in snippet
    assert len(snippet) == utils.MAX_SNIPPET_LEN


def test_normalize_file_path_windows_style() -> None:
    path = utils._normalize_file_path("\\tmp\\repo\\file.txt", "repo")
    assert path == "tmp/repo/file.txt"
