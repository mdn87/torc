from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_claim_link_controls as controls  # noqa: E402
import critic_claim_link_probe as link  # noqa: E402


def _plan() -> dict[str, object]:
    return json.loads(controls.PLAN_PATH.read_text(encoding="utf-8"))


def _valid_output(run_id: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    plan = _plan()
    cell = controls._cell(plan, run_id)
    candidates = controls._selected_candidates(plan, cell)
    critiques = []
    for candidate in candidates:
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
    return {"schema_version": 1, "critiques": critiques}, candidates


def test_direct_probe_contains_only_the_scheduled_candidate() -> None:
    probe = controls.build_probe("01-header-direct")

    assert probe["mode"] == "direct"
    assert probe["candidate_order"] == ["header-merge-baseline-v1"]
    assert "Review the candidate payload." in probe["prompt"]
    assert "header_merge.py" in probe["prompt"]
    assert "decision.json" not in probe["prompt"]
    assert "expected_claim_statuses" not in probe["prompt"]


def test_reversed_batch_probe_preserves_the_existing_two_candidate_contract() -> None:
    probe = controls.build_probe("03-cutover-first-batch")
    plan = _plan()
    cell = controls._cell(plan, "03-cutover-first-batch")
    candidates = controls._selected_candidates(plan, cell)
    claim_ids = controls.source._claim_ids(plan, candidates)
    payloads = controls.source._payloads(plan, candidates)

    assert probe["mode"] == "batch"
    assert probe["candidate_order"] == [
        "cutover-plan-baseline-v1",
        "header-merge-baseline-v1",
    ]
    assert probe["prompt"] == link._prompt(payloads=payloads, claim_ids=claim_ids)


@pytest.mark.parametrize(
    "run_id",
    ["01-header-direct", "02-cutover-direct", "03-cutover-first-batch"],
)
def test_validate_output_accepts_complete_structural_evidence(run_id: str) -> None:
    value, candidates = _valid_output(run_id)

    validated = controls._validate_output(value, plan=_plan(), candidates=candidates)

    assert all(item["claim_map_correct"] for item in validated)
    assert all(item["verdict_correct"] for item in validated)
    assert all(item["structured_finding_linkage_complete"] for item in validated)


def test_series_resumes_after_the_committed_first_control() -> None:
    assert controls.report() == {
        "schema_version": 1,
        "series_id": "critic-claim-link-controls-007",
        "status": "incomplete",
        "completed_calls": 1,
        "planned_calls": 3,
    }
    next_cell = controls.next_cell()
    assert next_cell["completed_calls"] == 1
    assert next_cell["next"]["run_id"] == "02-cutover-direct"
    assert next_cell["next"]["prompt_sha256"] == (
        "b3c70735b9ddd4060c65779979d25267412add0f4d3be41fa44d4f3fc5bf1dcc"
    )


def test_resume_checkpoint_matches_the_next_cell() -> None:
    checkpoint = json.loads(
        (EXPERIMENT / "critic-claim-link-controls-007-next.json").read_text(encoding="utf-8")
    )
    next_probe = controls.next_cell()["next"]

    assert checkpoint["completed_calls"] == 1
    assert checkpoint["next_cell"]["run_id"] == next_probe["run_id"]
    assert checkpoint["next_cell"]["prompt_sha256"] == next_probe["prompt_sha256"]
    assert checkpoint["frozen_controls"]["plan_sha256"] == next_probe["plan_sha256"]


def test_execute_rejects_the_wrong_frozen_plan_hash(tmp_path: Path) -> None:
    with pytest.raises(controls.CriticClaimLinkControlsError, match="plan hash does not match"):
        controls.execute_cell(
            run_id="02-cutover-direct",
            run_dir=tmp_path / "unused",
            expected_plan_sha256="unused",
            expected_prompt_sha256="unused",
        )
