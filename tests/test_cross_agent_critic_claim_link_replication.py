from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_claim_link_replication as replication  # noqa: E402


def test_replication_probes_are_counterbalanced_and_hash_stable() -> None:
    header = replication.build_probe("01-header-first")
    cutover = replication.build_probe("02-cutover-first")

    assert header["candidate_order"] == list(reversed(cutover["candidate_order"]))
    assert header["prompt_bytes"] == cutover["prompt_bytes"] == 6669
    assert header["prompt_sha256"] == (
        "394425d79ff5bc2fcd4c5975fafa03f621d8c7c9c7224fcb941f157d5000ab49"
    )
    assert cutover["prompt_sha256"] == (
        "6ad4714cbbb5f7371740eb2a31b5214437bb635b26bb1f2509ae1a879891677a"
    )


def test_replication_starts_incomplete() -> None:
    assert replication.report() == {
        "schema_version": 1,
        "series_id": "critic-claim-link-replication-008",
        "status": "incomplete",
        "completed_calls": 0,
        "planned_calls": 2,
    }


def test_wrong_frozen_plan_hash_cannot_execute(tmp_path: Path) -> None:
    with pytest.raises(replication.CriticClaimLinkReplicationError, match="plan hash"):
        replication.execute_cell(
            run_id="01-header-first",
            run_dir=tmp_path / "unused",
            expected_plan_sha256="unused",
            expected_prompt_sha256="unused",
        )
