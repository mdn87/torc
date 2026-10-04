from __future__ import annotations

import json
import sys
from copy import deepcopy
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_claim_link_generalization as generalization  # noqa: E402


def _plan() -> dict[str, object]:
    return json.loads(generalization.PLAN_PATH.read_text(encoding="utf-8"))


def _valid_output() -> dict[str, object]:
    plan = _plan()
    critiques = []
    for candidate in plan["candidates"]:
        links = {}
        findings = []
        for claim_id, status in candidate["expected_claim_statuses"].items():
            finding_ids = []
            if status == "unmet":
                finding_id = f"finding-{claim_id}"
                finding_ids.append(finding_id)
                findings.append(
                    {
                        "finding_id": finding_id,
                        "severity": "blocking",
                        "summary": f"Candidate violates {claim_id}.",
                        "evidence": "candidate artifact:1 testable observation",
                        "claim_ids": [claim_id],
                    }
                )
            links[claim_id] = finding_ids
        critiques.append(
            {
                "candidate_id": candidate["candidate_id"],
                "claim_links": links,
                "result": {
                    "schema_version": 1,
                    "verdict": candidate["expected_verdict"],
                    "findings": findings,
                },
            }
        )
    return {"schema_version": 1, "critiques": critiques}


def test_build_probe_uses_two_new_fixture_shapes_without_oracle_content() -> None:
    probe = generalization.build_probe()

    assert probe["plan_status"] == "draft"
    assert probe["candidate_order"] == [
        "header-merge-baseline-v1",
        "cutover-plan-baseline-v1",
    ]
    assert {tuple(value) for value in probe["reviewable_claim_ids"].values()} == {
        ("c1", "c2", "x1", "x2", "x3", "x4")
    }
    assert "header_merge.py" in probe["prompt"]
    assert "decision.json" in probe["prompt"]
    assert "test_header_merge_hidden.py" not in probe["prompt"]
    assert "EXPECTED_OPERATIONS" not in probe["prompt"]
    assert "expected_claim_statuses" not in probe["prompt"]


def test_validate_output_accepts_complete_structural_evidence() -> None:
    validated = generalization.validate_output(_valid_output(), plan=_plan())

    assert len(validated) == 2
    assert all(item["claim_map_correct"] for item in validated)
    assert all(item["verdict_correct"] for item in validated)
    assert all(item["structured_finding_linkage_complete"] for item in validated)
    assert all(not item["unlinked_finding_ids"] for item in validated)


def test_validate_output_detects_unlinked_finding() -> None:
    value = _valid_output()
    value["critiques"][0]["result"]["findings"].append(
        {
            "finding_id": "finding-extra",
            "severity": "blocking",
            "summary": "Extra finding.",
            "evidence": "header_merge.py:1 testable observation",
            "claim_ids": ["x1"],
        }
    )

    validated = generalization.validate_output(value, plan=_plan())

    assert validated[0]["structured_finding_linkage_complete"] is False
    assert validated[0]["unlinked_finding_ids"] == ["finding-extra"]


def test_validate_output_rejects_candidate_order_drift() -> None:
    value = _valid_output()
    drifted = deepcopy(value)
    drifted["critiques"].reverse()

    with pytest.raises(
        generalization.CriticClaimLinkGeneralizationError,
        match="identity or order drifted",
    ):
        generalization.validate_output(drifted, plan=_plan())


def test_execute_requires_a_frozen_ready_plan(tmp_path: Path) -> None:
    with pytest.raises(
        generalization.CriticClaimLinkGeneralizationError,
        match="not ready",
    ):
        generalization.execute_probe(
            run_dir=tmp_path / "unused",
            expected_plan_sha256="unused",
            expected_prompt_sha256="unused",
        )
