from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_batch_probe as batch  # noqa: E402


def _critique(candidate_id: str) -> dict[str, object]:
    if candidate_id == "refactor-baseline-v1":
        findings = [
            {
                "finding_id": "f1",
                "severity": "blocking",
                "summary": "legacy_route duplicates route_request logic",
                "evidence": "routing.py: legacy_route owns a duplicate route table",
                "claim_ids": ["x1", "d1"],
            },
            {
                "finding_id": "f2",
                "severity": "blocking",
                "summary": "production dispatch uses legacy_route",
                "evidence": "routing.py: dispatch and dispatch_batch call legacy_route",
                "claim_ids": ["c1", "s1"],
            },
        ]
    else:
        findings = [
            {
                "finding_id": "f1",
                "severity": "blocking",
                "summary": "digest comparison is not constant-time",
                "evidence": "release_policy.py: use compare_digest for the digest",
                "claim_ids": ["x1"],
            },
            {
                "finding_id": "f2",
                "severity": "blocking",
                "summary": "path prefix matching permits segment confusion",
                "evidence": "release_policy.py: normalize paths and match root segments",
                "claim_ids": ["x2", "x3"],
            },
            {
                "finding_id": "f3",
                "severity": "blocking",
                "summary": "rename source path is not validated",
                "evidence": "release_policy.py: validate from_path against allowed scope",
                "claim_ids": ["x4"],
            },
            {
                "finding_id": "f4",
                "severity": "blocking",
                "summary": "malformed or unknown records do not fail closed",
                "evidence": "release_policy.py: deny missing fields and unknown actions",
                "claim_ids": ["x5"],
            },
        ]
    return {
        "schema_version": 1,
        "verdict": "changes_requested",
        "findings": findings,
    }


def test_batch_probe_reconstructs_two_compact_payloads_without_oracle() -> None:
    probe = batch.build_probe()
    prompt = probe["prompt"]

    assert probe["candidate_count"] == 2
    assert [item["payload_bytes"] for item in probe["candidates"]] == [2540, 2347]
    assert "refactor-baseline-v1" in prompt
    assert "release-policy-baseline-v1" in prompt
    assert "oracle.json" not in prompt
    assert "required_defect_areas" not in prompt
    assert probe["prompt_bytes"] < 6200


def test_batch_validator_keeps_candidate_findings_isolated_and_scoreable() -> None:
    candidate_ids = ["refactor-baseline-v1", "release-policy-baseline-v1"]
    value = {
        "schema_version": 1,
        "critiques": [
            {"candidate_id": candidate_id, "result": _critique(candidate_id)}
            for candidate_id in candidate_ids
        ],
    }

    scored = batch.validate_batch(
        value,
        candidate_ids=candidate_ids,
        model="gpt-6-sol",
    )

    assert [item["candidate_id"] for item in scored] == candidate_ids
    assert all(item["score"]["defect_area_recall"] == 1.0 for item in scored)


def test_batch_baseline_reconstructs_frozen_summed_medians() -> None:
    plan = json.loads(batch.PLAN_PATH.read_text(encoding="utf-8"))

    baseline = batch._baseline(plan)

    assert baseline["summed_median_input_tokens"] == 25107
    assert baseline["summed_median_completion_ms"] == 23397.869
