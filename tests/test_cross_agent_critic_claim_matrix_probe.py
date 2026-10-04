from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_claim_matrix_probe as matrix  # noqa: E402


def _finding(finding_id: str, claim_ids: list[str]) -> dict[str, object]:
    return {
        "finding_id": finding_id,
        "severity": "blocking",
        "summary": "candidate contradicts the cited claim",
        "evidence": "candidate.py:1 is a testable observation",
        "claim_ids": claim_ids,
    }


def _candidate_item(
    candidate_id: str,
    statuses: dict[str, str],
) -> dict[str, object]:
    unmet = [claim_id for claim_id, status in statuses.items() if status == "unmet"]
    findings = [_finding(f"f{index}", [claim_id]) for index, claim_id in enumerate(unmet, start=1)]
    finding_ids = {claim_id: f"f{index}" for index, claim_id in enumerate(unmet, start=1)}
    return {
        "candidate_id": candidate_id,
        "claim_assessments": [
            {
                "claim_id": claim_id,
                "status": status,
                "evidence": "candidate.py:1 is a testable observation",
                "finding_ids": [finding_ids[claim_id]] if status == "unmet" else [],
            }
            for claim_id, status in statuses.items()
        ],
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


def test_claim_matrix_probe_exposes_exact_reviewable_claims_without_oracle() -> None:
    probe = matrix.build_probe()

    assert probe["reviewable_claim_ids"] == {
        "refactor-baseline-v1": ["c1", "x1", "x2", "x3", "d1", "s1"],
        "release-policy-baseline-v1": ["c1", "c2", "x1", "x2", "x3", "x4", "x5"],
    }
    assert "required_defect_areas" not in probe["prompt"]
    assert "oracle.json" not in probe["prompt"]


def test_claim_matrix_validator_accepts_complete_linked_assessments() -> None:
    plan = json.loads(matrix.PLAN_PATH.read_text(encoding="utf-8"))

    results = matrix.validate_output(_valid_output(plan), plan=plan)

    assert len(results) == 2
    assert all(item["claim_matrix_correct"] for item in results)


def test_claim_matrix_validator_rejects_missing_claim() -> None:
    plan = json.loads(matrix.PLAN_PATH.read_text(encoding="utf-8"))
    output = _valid_output(plan)
    output["critiques"][0]["claim_assessments"].pop()

    with pytest.raises(matrix.CriticClaimMatrixProbeError, match="coverage drifted"):
        matrix.validate_output(output, plan=plan)


def test_claim_matrix_validator_rejects_cross_claim_finding_link() -> None:
    plan = json.loads(matrix.PLAN_PATH.read_text(encoding="utf-8"))
    output = copy.deepcopy(_valid_output(plan))
    assessment = output["critiques"][0]["claim_assessments"][0]
    finding_id = assessment["finding_ids"][0]
    finding = next(
        item
        for item in output["critiques"][0]["result"]["findings"]
        if item["finding_id"] == finding_id
    )
    finding["claim_ids"] = ["x1"]

    with pytest.raises(matrix.CriticClaimMatrixProbeError, match="same claim"):
        matrix.validate_output(output, plan=plan)


def test_claim_matrix_live_probe_requires_frozen_apparatus() -> None:
    with pytest.raises(matrix.CriticClaimMatrixProbeError, match="inputs are missing"):
        matrix._verify_apparatus({"apparatus_inputs": []})
