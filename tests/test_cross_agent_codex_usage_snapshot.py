from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import codex_usage_snapshot as usage_snapshot  # noqa: E402


def _raw_snapshot(used_percent: int) -> dict[str, object]:
    return {
        "ordinaryUsageAllowed": True,
        "accountId": "must-not-leak",
        "rateLimits": {
            "planType": "plus",
            "primary": {
                "usedPercent": used_percent,
                "windowDurationMins": 300,
                "resetsAt": 1_800_000_000,
            },
            "secondary": {
                "usedPercent": 14,
                "windowDurationMins": 10_080,
                "resetsAt": 1_800_500_000,
            },
        },
        "rateLimitResetCredits": {
            "availableCount": 2,
            "credits": [{"id": "must-not-leak", "status": "available"}],
        },
    }


def test_usage_snapshot_is_sanitized_and_stops_at_threshold() -> None:
    result = usage_snapshot.sanitize_snapshot(
        _raw_snapshot(90), stop_threshold_percent=75
    )
    rendered = json.dumps(result)

    assert result["decision"] == "stop"
    assert result["primary"]["used_percent"] == 90
    assert result["reset_credits_available"] == 2
    assert "accountId" not in rendered
    assert "must-not-leak" not in rendered


def test_usage_snapshot_allows_work_below_threshold() -> None:
    result = usage_snapshot.sanitize_snapshot(
        _raw_snapshot(12), stop_threshold_percent=75
    )

    assert result["decision"] == "proceed"


def test_usage_snapshot_cli_distinguishes_stop_from_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    def fake_read_snapshot(**kwargs: Any) -> dict[str, object]:
        return usage_snapshot.sanitize_snapshot(
            _raw_snapshot(90),
            stop_threshold_percent=kwargs["stop_threshold_percent"],
        )

    monkeypatch.setattr(usage_snapshot, "read_snapshot", fake_read_snapshot)

    assert usage_snapshot.main([]) == 3


def test_usage_snapshot_rejects_an_unresolved_executable(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(usage_snapshot.shutil, "which", lambda _value: None)

    with pytest.raises(
        usage_snapshot.CodexUsageSnapshotError,
        match="executable is unavailable",
    ):
        usage_snapshot.read_snapshot(executable="missing-codex")
