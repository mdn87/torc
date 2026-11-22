import json
import re
from pathlib import Path

import pytest

from torc.canonical import payload_sha256
from torc.claude_continuation_evidence import analyze
from torc.claude_continuation_schedule import freeze_schedule

EVIDENCE = Path(__file__).resolve().parents[1] / "docs" / "evidence"
SCHEDULE = EVIDENCE / "2026-11-21-continuation-schedule.json"
FROZEN_SHA256 = "e02a67e8d80e859d630b7941ee9fbd951cc9de34fd5fa875b52ace2bb3830977"
# Autowork's dispatch contract accepts correlation IDs of this shape.
SAFE_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:@+\-/]{0,255}")


def _inputs():
    prep = json.loads((EVIDENCE / "2026-11-20-continuation-scorer-preparation.json").read_text())
    qual = json.loads((EVIDENCE / "2026-11-20-claude-accounting-qualification.json").read_text())
    return prep, qual


def test_frozen_schedule_rebuilds_from_its_recorded_seed():
    prep, qual = _inputs()
    frozen = json.loads(SCHEDULE.read_text())
    assert payload_sha256(frozen) == FROZEN_SHA256
    rebuilt = freeze_schedule(prep, qual, frozen["order_seed"])
    assert json.dumps(rebuilt, indent=2) + "\n" == SCHEDULE.read_text()


def test_frozen_schedule_satisfies_the_analyzer_before_any_result():
    prep, _ = _inputs()
    frozen = json.loads(SCHEDULE.read_text())
    trials = frozen["trials"]
    assert [t["sequence"] for t in trials] == list(range(1, 33))
    assert len({t["trial_id"] for t in trials}) == 32
    assert all(SAFE_ID.fullmatch(t["trial_id"]) for t in trials)
    assert frozen["policy"]["client_version"] == "2.1.325"
    assert frozen["policy"]["auxiliary_models"] == []
    report = analyze(frozen, prep, {"schedule_sha256": FROZEN_SHA256, "trials": []}, EVIDENCE)
    assert report["decision"] == "incomplete_usage"
    assert report["unresolved_tasks"] == 8
    assert report["acceptance"]["torc"] == {"passed": 0, "scheduled": 16, "unscored": 16}


def test_each_task_reverses_its_order_and_repetition_two_follows_repetition_one():
    prep, qual = _inputs()
    trials = freeze_schedule(prep, qual, "any-recorded-seed")["trials"]
    assert [t["repetition"] for t in trials] == [1] * 16 + [2] * 16
    for case in {t["case"] for t in trials}:
        lead = {
            t["repetition"]: t["arm"] for t in trials if t["case"] == case and t["position"] == 1
        }
        assert lead[1] != lead[2]
    assert trials != freeze_schedule(prep, qual, "another-seed")["trials"]


def test_freeze_refuses_unqualified_or_already_admitted_inputs():
    prep, qual = _inputs()
    with pytest.raises(ValueError, match="not qualified"):
        freeze_schedule(prep, {**qual, "benchmark_admissions": 1}, "seed")
    with pytest.raises(ValueError, match="not qualified"):
        freeze_schedule(prep, {**qual, "qualified": False}, "seed")
    with pytest.raises(ValueError, match="scorer receipt"):
        freeze_schedule({**prep, "status": "edited"}, qual, "seed")
    with pytest.raises(ValueError, match="seed"):
        freeze_schedule(prep, qual, " ")
