"""A real local handoff connects deterministic Mirror delivery fixtures."""

import json
from pathlib import Path

import pytest

from torc.errors import InvalidInputError
from torc.mirror_experiment import run_experiment
from torc.store import Store
from torc.verify import verify_store

NOW = "2026-11-06T12:00:00Z"


def read(root, path):
    return json.loads((root / path).read_text(encoding="utf-8"))


def test_experiment_preserves_full_result_and_commitments_through_real_handoff(tmp_path):
    output = tmp_path / "run"
    report = run_experiment(output, now=NOW)
    assert report["passed"] is True
    assert report["synthetic"] is True
    assert report["measurements"]["added_model_calls"] == 0
    assert report["checks"]["required_facts_preserved"] is True
    assert report["checks"]["complete_written_result_preserved"] is True
    assert report["checks"]["temporary_inference_expired"] is True
    assert report["checks"]["temporary_settings_not_canonical"] is True
    assert report["handoff"]["before_acceptance"] == "mirror-source"
    assert report["handoff"]["after_acceptance"] == "mirror-target"
    assert report["handoff"]["disposition"] == "accepted"
    assert report["handoff"]["commitments_preserved"] is True
    assert [turn["name"] for turn in report["turns"]] == [
        "desktop", "away", "repair", "handoff", "returned",
    ]
    records = [read(output, turn["delivery_file"]) for turn in report["turns"]]
    settings = [read(output, turn["settings_file"]) for turn in report["turns"]]
    assert settings[1]["values"]["turn_length"] == "brief"
    assert settings[1]["values"]["explanation_depth"] == "detailed"
    assert settings[2]["values"]["interaction"] == "repair"
    assert settings[-1]["values"]["screen"] == "available"
    assert settings[-1]["values"]["turn_length"] == "full"
    assert len({record["written"] for record in records}) == 1
    assert len(records[1]["speech"]["fact_ids"]) < len(records[-1]["speech"]["fact_ids"])
    assert report["measurements"]["required_facts_retained"] == (
        report["measurements"]["required_facts_expected"]
    )
    for turn, record in zip(report["turns"], records, strict=True):
        assert (output / turn["context_file"]).read_text(encoding="utf-8")
        assert (output / turn["written_file"]).read_text(encoding="utf-8") == record["written"]
        assert turn["resolver_ms"] >= 0 and turn["render_ms"] >= 0
    with Store(output / "lineage", read_only=True) as store:
        assert verify_store(store, "mirror-experiment")["valid"] is True
        assert len(store.list_hashed_records("handoffs", "mirror-experiment")) == 1
        assert store.current_authority("mirror-experiment")["activation_id"] == "mirror-target"
    assert read(output, "report.json") == report
    assert "hardware_playback" in report["unverified"]
    assert "native_model_behavior" in report["unverified"]


def test_existing_evidence_is_never_overwritten(tmp_path):
    output = tmp_path / "run"
    output.mkdir()
    sentinel = output / "report.json"
    sentinel.write_text("original", encoding="utf-8")
    with pytest.raises(InvalidInputError, match="empty"):
        run_experiment(output, now=NOW)
    assert sentinel.read_text(encoding="utf-8") == "original"
    assert list(output.iterdir()) == [sentinel]


@pytest.mark.parametrize("now", ["bad", "2026-11-06T12:00:00-05:00"])
def test_bad_clock_is_rejected_before_creating_output(tmp_path, now):
    output = tmp_path / "run"
    with pytest.raises(InvalidInputError):
        run_experiment(output, now=now)
    assert not output.exists()


def test_expired_and_superseded_output_is_rejected_by_experiment_checks(tmp_path):
    report = run_experiment(Path(tmp_path), now=NOW)
    assert report["checks"]["expired_delivery_rejected"] is True
    assert report["checks"]["superseded_delivery_rejected"] is True
    assert report["checks"]["echoed_evidence_deduplicated"] is True
    assert report["checks"]["quoted_input_ignored"] is True
