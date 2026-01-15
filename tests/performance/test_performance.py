from __future__ import annotations

import time

from ghmon_cli.utils import create_finding_id


def test_create_finding_id_performance() -> None:
    finding = {
        "SourceMetadata": {"Data": {"Filesystem": {"file": "src/app.py", "line": 10}}},
        "DetectorName": "Detector",
        "Raw": "secret",
    }
    start = time.perf_counter()
    for _ in range(1000):
        create_finding_id("acme/widgets", finding)
    duration = time.perf_counter() - start
    assert duration < 1.0
