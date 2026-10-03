from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_probe_score as probe_score  # noqa: E402

REFACTOR_HASH = "8adde67f95bbeec5342ba29880e982dcb30adade419a471e6509c31e8b9f5a00"
RELEASE_HASH = "93213ff481c8b41b7a500a9b7f04bf7388d88e06b06811d6ca39da86f77b2cc1"


def _write(path: Path, value: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")


def _probe_run(run_dir: Path, *, release: bool = False) -> None:
    fixture_id = (
        "release-policy-interaction" if release else "refactor-superseded-path"
    )
    workspace_hash = RELEASE_HASH if release else REFACTOR_HASH
    findings = (
        [
            {
                "finding_id": "f1",
                "severity": "blocking",
                "summary": "Digest equality is not constant-time.",
                "evidence": "policy.py should use compare_digest for the digest.",
                "claim_ids": ["x1"],
            },
            {
                "finding_id": "f2",
                "severity": "blocking",
                "summary": "Paths use an unsafe string prefix.",
                "evidence": "Normalize the path and compare root segments.",
                "claim_ids": ["x2", "x3"],
            },
            {
                "finding_id": "f3",
                "severity": "blocking",
                "summary": "Rename source is outside the allowed scope.",
                "evidence": "Validate rename from_path as well as the target.",
                "claim_ids": ["x4"],
            },
            {
                "finding_id": "f4",
                "severity": "blocking",
                "summary": "Malformed records do not fail closed.",
                "evidence": "Unknown records need an exception or explicit deny.",
                "claim_ids": ["x5"],
            },
        ]
        if release
        else [
            {
                "finding_id": "f1",
                "severity": "blocking",
                "summary": "Production dispatch still calls legacy_route.",
                "evidence": "routing.py: dispatch and dispatch_batch",
                "claim_ids": ["s1", "c1"],
            },
            {
                "finding_id": "f2",
                "severity": "blocking",
                "summary": "legacy_route duplicates route_request.",
                "evidence": "routing.py: legacy_route should directly delegate",
                "claim_ids": ["d1", "x1"],
            },
        ]
    )
    _write(
        run_dir / "workflow-result.json",
        {
            "run_id": "probe-run",
            "fixture_id": fixture_id,
            "replay_source_id": f"fixture-baseline:{fixture_id}",
            "critic_context": "claim-capsule-candidate-v1",
            "phases": [{"record": "phases/01-critic/worker-run.json"}],
        },
    )
    _write(
        run_dir / "source-primary-ref.json",
        {
            "source_kind": "fixture_baseline",
            "source_id": f"fixture-baseline:{fixture_id}",
            "workspace_tree_sha256": workspace_hash,
        },
    )
    _write(
        run_dir / "score-candidate.json",
        {
            "fixture_id": fixture_id,
            "workspace_tree_sha256": workspace_hash,
            "accepted": False,
        },
    )
    _write(
        run_dir / "critique.json",
        {
            "schema_version": 1,
            "verdict": "changes_requested",
            "findings": findings,
        },
    )
    _write(
        run_dir / "phases" / "01-critic" / "worker-run.json",
        {
            "provider": "codex",
            "model": "gpt-6-sol",
            "effort": "low",
            "tool_mode": "none",
            "harness_version": "codex-cli 0.159.3",
            "prompt_bytes": 5000,
            "usage": {"input_tokens": 13000, "output_tokens": 200},
            "timing": {"completion_ms": 6000.0},
        },
    )


def test_probe_scorer_measures_preregistered_defect_recall(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _probe_run(run_dir)

    result = probe_score.score_run(
        run_dir=run_dir,
        candidate_id="refactor-baseline-v1",
    )

    assert result["changes_requested_correct"] is True
    assert result["required_defect_area_count"] == 2
    assert result["covered_defect_area_count"] == 2
    assert result["defect_area_recall"] == 1.0
    assert result["valid_claim_citation_count"] == 4
    assert result["unsupported_finding_count"] == 0


def test_probe_scorer_covers_release_candidate_rules(tmp_path: Path) -> None:
    run_dir = tmp_path / "run"
    _probe_run(run_dir, release=True)

    result = probe_score.score_run(
        run_dir=run_dir,
        candidate_id="release-policy-baseline-v1",
    )

    assert result["changes_requested_correct"] is True
    assert result["required_defect_area_count"] == 4
    assert result["defect_area_recall"] == 1.0
    assert result["valid_claim_citation_count"] == 5
    assert result["unsupported_finding_count"] == 0


def test_probe_scorer_fails_closed_on_candidate_hash_mismatch(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "run"
    _probe_run(run_dir)
    _write(
        run_dir / "score-candidate.json",
        {
            "fixture_id": "refactor-superseded-path",
            "workspace_tree_sha256": "b" * 64,
            "accepted": False,
        },
    )

    with pytest.raises(probe_score.CriticProbeScoreError, match="workspace hash"):
        probe_score.score_run(
            run_dir=run_dir,
            candidate_id="refactor-baseline-v1",
        )
