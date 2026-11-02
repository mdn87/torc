from __future__ import annotations

import json
from pathlib import Path

from torc.demo import run_demo
from torc.store import TUAN_CORRELATION_SIDECAR, Store


def test_projections_compiled_under_a_correlation_are_indexed_without_payload(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.setenv("TUAN_CORRELATION_ID", "req-abc123")
    run_demo(tmp_path)
    sidecar = tmp_path / TUAN_CORRELATION_SIDECAR
    lines = [json.loads(line) for line in sidecar.read_text(encoding="utf-8").splitlines()]
    assert lines, "the demo compiles at least one projection"
    with Store(tmp_path, read_only=True) as store:
        rows = store.connection.execute(
            "SELECT projection_id, lineage_id, payload_json FROM projections"
        ).fetchall()
    by_id = {row["projection_id"]: row for row in rows}
    for line in lines:
        assert set(line) == {
            "correlation_id", "projection_id", "lineage_id", "record_sha256", "recorded_at"
        }
        assert line["correlation_id"] == "req-abc123"
        assert line["lineage_id"] == by_id[line["projection_id"]]["lineage_id"]
        sealed = json.loads(by_id[line["projection_id"]]["payload_json"])
        assert line["record_sha256"] == sealed["integrity"]["canonical_payload_sha256"]
    assert len(lines) == len(rows)
    # Identifiers only: no section content from any projection reaches the sidecar.
    text = sidecar.read_text(encoding="utf-8")
    assert "included_sections" not in text and "payload" not in text


def test_without_correlation_no_sidecar_is_written(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("TUAN_CORRELATION_ID", raising=False)
    run_demo(tmp_path)
    assert not (tmp_path / TUAN_CORRELATION_SIDECAR).exists()
