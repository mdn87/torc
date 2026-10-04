from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_claim_link_probe as link  # noqa: E402


def _candidate_item(candidate_id: str, statuses: dict[str, str]) -> dict[str, object]:
    unmet = [claim_id for claim_id, status in statuses.items() if status == "unmet"]
    findings = [
        {
            "finding_id": f"f{index}",
            "severity": "blocking",
            "summary": "candidate contradicts the claim",
            "evidence": "candidate.py:1 is a testable observation",
            "claim_ids": [claim_id],
        }
        for index, claim_id in enumerate(unmet, start=1)
    ]
    ids = {claim_id: f"f{index}" for index, claim_id in enumerate(unmet, start=1)}
    return {
        "candidate_id": candidate_id,
        "claim_links": {
            claim_id: [ids[claim_id]] if status == "unmet" else []
            for claim_id, status in statuses.items()
        },
        "result": {
            "schema_version": 1,
            "verdict": "changes_requested",
            "findings": findings,
        },
    }


def _valid_output(plan: dict[str, object]) -> dict[str, object]:
    return {
        "schema_version": 1,
        "critiques": [
            _candidate_item(candidate_id, plan["expected_claim_statuses"][candidate_id])
            for candidate_id in plan["candidates"]
        ],
    }


def test_claim_link_probe_is_smaller_than_verbose_matrix() -> None:
    probe = link.build_probe()

    assert probe["prompt_bytes"] < 7000
    assert probe["reviewable_claim_ids"] == {
        "refactor-baseline-v1": ["c1", "x1", "x2", "x3", "d1", "s1"],
        "release-policy-baseline-v1": ["c1", "c2", "x1", "x2", "x3", "x4", "x5"],
    }
    assert "required_defect_areas" not in probe["prompt"]
    assert "expected_claim_statuses" not in probe["prompt"]


def test_claim_link_validator_accepts_complete_compact_map() -> None:
    plan = json.loads(link.PLAN_PATH.read_text(encoding="utf-8"))

    results = link.validate_output(_valid_output(plan), plan=plan)

    assert len(results) == 2
    assert all(item["claim_map_correct"] for item in results)
    assert all(item["structured_finding_linkage_complete"] for item in results)


def test_claim_link_validator_rejects_missing_claim() -> None:
    plan = json.loads(link.PLAN_PATH.read_text(encoding="utf-8"))
    output = _valid_output(plan)
    del output["critiques"][0]["claim_links"]["c1"]

    with pytest.raises(link.CriticClaimLinkProbeError, match="coverage"):
        link.validate_output(output, plan=plan)


def test_claim_link_validator_rejects_cross_claim_reference() -> None:
    plan = json.loads(link.PLAN_PATH.read_text(encoding="utf-8"))
    output = copy.deepcopy(_valid_output(plan))
    output["critiques"][0]["result"]["findings"][0]["claim_ids"] = ["x1"]

    with pytest.raises(link.CriticClaimLinkProbeError, match="same claim"):
        link.validate_output(output, plan=plan)


def test_claim_link_validator_marks_unlinked_finding() -> None:
    plan = json.loads(link.PLAN_PATH.read_text(encoding="utf-8"))
    output = _valid_output(plan)
    output["critiques"][0]["result"]["findings"].append(
        {
            "finding_id": "extra",
            "severity": "blocking",
            "summary": "extra issue",
            "evidence": "candidate.py:2",
            "claim_ids": ["x1"],
        }
    )

    results = link.validate_output(output, plan=plan)

    assert results[0]["structured_finding_linkage_complete"] is False
    assert results[0]["unlinked_finding_ids"] == ["extra"]


def test_claim_link_live_probe_requires_frozen_apparatus() -> None:
    with pytest.raises(link.CriticClaimLinkProbeError, match="inputs are missing"):
        link._verify_apparatus({"apparatus_inputs": []})


def test_committed_claim_link_probe_is_frozen_and_reproducible() -> None:
    plan = json.loads(link.PLAN_PATH.read_text(encoding="utf-8"))
    probe = link.build_probe()

    assert plan["status"] == "ready"
    assert len(link._verify_apparatus(plan)) == 14
    assert (
        probe["plan_sha256"] == "a0589397007769b59aa58be4d2bfabe901bfab3d1ec097b3659526a42483cff8"
    )
    assert (
        probe["prompt_sha256"] == "4cbc8a217fe98dcd401f21e76edba8023c1bd96682556fa3e3017ff20776641f"
    )
