from __future__ import annotations

import json

from torc import HANDOFF_REASON_CODES, __version__
from torc.cli import main


def test_seed_version_is_explicit() -> None:
    assert __version__ == "0.0.1"


def test_handoff_reasons_cover_explicit_control_boundaries() -> None:
    assert "capability_escalation" in HANDOFF_REASON_CODES
    assert "context_degradation" in HANDOFF_REASON_CODES
    assert "policy_boundary" in HANDOFF_REASON_CODES
    assert "lineage_branch" in HANDOFF_REASON_CODES
    assert len(HANDOFF_REASON_CODES) == len(set(HANDOFF_REASON_CODES))


def test_doctor_reports_intact_seed(capsys) -> None:
    exit_code = main(["doctor", "--json"])
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["status"] == "seed"
    assert payload["implementation_status"] == "vertical_slice_not_implemented"
    assert payload["missing_required_paths"] == []
