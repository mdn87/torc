from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import critic_replay as replay  # noqa: E402
import workflow_runner as workflow  # noqa: E402

SOURCE_RUN = (
    EXPERIMENT
    / "runs"
    / "smoke-001"
    / "22-design-cutover-codex-artifact-review-compact"
)
SERIES_PLAN = EXPERIMENT / "critic-transport-series-002-plan.json"


def _record() -> dict[str, Any]:
    return {
        "provider": "codex",
        "role": "critic",
        "tool_mode": "none",
        "session": {
            "mode": "fresh-ephemeral",
            "requested_id": None,
            "observed_id": "critic-session",
        },
        "usage": {
            "schema_version": 1,
            "source": "test",
            "supplied": False,
            "input_tokens": None,
            "cached_input_tokens": None,
            "cache_write_input_tokens": None,
            "reasoning_output_tokens": None,
            "output_tokens": None,
            "reported_fields": [],
            "unreported_fields": [],
            "provider_usage": {},
        },
        "timing": {
            "startup_ms": 1.0,
            "time_to_first_output_ms": 2.0,
            "completion_ms": 3.0,
        },
    }


def test_replay_plan_is_one_call_and_does_not_create_output(tmp_path: Path) -> None:
    plan = replay.replay_plan(
        manifest=workflow.load_manifest(),
        fixture_id="design-cutover-plan",
        source_run=SOURCE_RUN,
        critic_provider="codex",
        critic_context=workflow.FULL_CRITIC_CONTEXT,
    )

    assert plan["model_call_count"] == 1
    assert plan["source_run_id"] == SOURCE_RUN.name
    assert plan["critic_context"] == workflow.FULL_CRITIC_CONTEXT
    assert list(tmp_path.iterdir()) == []


def test_baseline_replay_plan_uses_the_pinned_fixture_tree() -> None:
    plan = replay.replay_plan(
        manifest=workflow.load_manifest(),
        fixture_id="refactor-superseded-path",
        source_baseline=True,
        critic_provider="codex",
        critic_context=workflow.COMPACT_CRITIC_CONTEXT,
    )

    assert plan["source_kind"] == "fixture_baseline"
    assert plan["source_id"] == "fixture-baseline:refactor-superseded-path"
    assert plan["source_run_id"] is None
    assert plan["source_workspace_tree_sha256"] == (
        "8adde67f95bbeec5342ba29880e982dcb30adade419a471e6509c31e8b9f5a00"
    )


def test_replay_reconstructs_exact_candidate_and_calls_only_critic(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(workflow, "_apparatus_revision", lambda: "d" * 40)

    def fake_worker(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        kwargs["output_dir"].mkdir(parents=True)
        event = {
            "type": "item.completed",
            "item": {
                "type": "agent_message",
                "text": json.dumps(
                    {"schema_version": 1, "verdict": "approve", "findings": []}
                ),
            },
        }
        (kwargs["output_dir"] / "stdout.jsonl").write_text(
            json.dumps(event) + "\n", encoding="utf-8"
        )
        return _record()

    monkeypatch.setattr(workflow, "_run_worker", fake_worker)
    result = replay.run_critic_replay(
        manifest=workflow.load_manifest(),
        fixture_id="design-cutover-plan",
        source_run=SOURCE_RUN,
        critic_provider="codex",
        critic_context=workflow.FULL_CRITIC_CONTEXT,
        run_dir=tmp_path / "replay",
    )

    assert len(calls) == 1
    assert calls[0]["role"] == "critic"
    assert "Choose and plan a tenant-store cutover" in calls[0]["prompt"]
    assert result["accepted_final"] is True
    assert result["replay_source_run_id"] == SOURCE_RUN.name
    source = json.loads(
        (tmp_path / "replay" / "source-primary-ref.json").read_text(encoding="utf-8")
    )
    score = json.loads(
        (tmp_path / "replay" / "score-candidate.json").read_text(encoding="utf-8")
    )
    assert score["workspace_tree_sha256"] == source["workspace_tree_sha256"]


def test_baseline_replay_scores_without_a_primary_model_call(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls: list[dict[str, Any]] = []
    monkeypatch.setattr(workflow, "_apparatus_revision", lambda: "e" * 40)

    def fake_worker(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        kwargs["output_dir"].mkdir(parents=True)
        critique = {
            "schema_version": 1,
            "verdict": "changes_requested",
            "findings": [
                {
                    "finding_id": "f1",
                    "severity": "blocking",
                    "summary": "Production dispatch still uses legacy_route.",
                    "evidence": "routing.py: dispatch and dispatch_batch",
                    "claim_ids": ["s1", "c1"],
                }
            ],
        }
        event = {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": json.dumps(critique)},
        }
        (kwargs["output_dir"] / "stdout.jsonl").write_text(
            json.dumps(event) + "\n", encoding="utf-8"
        )
        return _record()

    monkeypatch.setattr(workflow, "_run_worker", fake_worker)
    result = replay.run_critic_replay(
        manifest=workflow.load_manifest(),
        fixture_id="refactor-superseded-path",
        source_baseline=True,
        critic_provider="codex",
        critic_context=workflow.COMPACT_CRITIC_CONTEXT,
        run_dir=tmp_path / "baseline-replay",
    )

    assert len(calls) == 1
    assert "def legacy_route" in calls[0]["prompt"]
    assert "ARCHITECTURE.md" not in calls[0]["prompt"]
    assert result["accepted_final"] is False
    assert result["replay_source_id"] == (
        "fixture-baseline:refactor-superseded-path"
    )
    source = json.loads(
        (tmp_path / "baseline-replay" / "source-primary-ref.json").read_text(
            encoding="utf-8"
        )
    )
    assert source["source_kind"] == "fixture_baseline"


def test_confirmation_plan_references_pinned_candidates_and_claims() -> None:
    plan = json.loads(SERIES_PLAN.read_text(encoding="utf-8"))
    fixture_manifest = json.loads(
        (EXPERIMENT / "fixtures-manifest.json").read_text(encoding="utf-8")
    )

    assert plan["status"] == "frozen_before_live_runs"
    assert plan["apparatus_revision"] == (
        "188568bf4b8dddf02e7b1fcd4ea012785bda5881"
    )
    for apparatus_input in plan["apparatus_inputs"]:
        path = ROOT / apparatus_input["path"]
        assert hashlib.sha256(path.read_bytes()).hexdigest() == apparatus_input["sha256"]
    assert len(plan["counterbalanced_order_per_candidate"]) == 6
    assert set(plan["counterbalanced_order_per_candidate"]) == set(
        plan["transports"]
    )
    for candidate in plan["candidates"]:
        fixture_id = candidate["fixture_id"]
        assert candidate["candidate_workspace_tree_sha256"] == fixture_manifest[
            "fixtures"
        ][fixture_id]["agent_visible_sha256"]
        capsule, _ = workflow._compile_handoff(
            fixture_id,
            "plan-validation",
            "candidate-plan-validation",
            "codex/gpt-6-sol",
        )
        claim_ids = {
            claim_id
            for section in capsule["claims"].values()
            for claim_id in section
        }
        for area in candidate["required_defect_areas"]:
            assert set(area["acceptable_claim_ids"]) <= claim_ids


def test_confirmation_critic_prompts_exclude_oracle_and_scoring_contract(
    tmp_path: Path,
) -> None:
    manifest = workflow.load_manifest()
    plan = json.loads(SERIES_PLAN.read_text(encoding="utf-8"))
    forbidden = (
        "oracle.json",
        "critic_probe_score.py",
        "required_defect_areas",
        "evidence_term_groups",
    )

    for candidate in plan["candidates"]:
        fixture_id = candidate["fixture_id"]
        workspace = tmp_path / fixture_id
        replay.fixture_control.stage_fixture(fixture_id, workspace)
        capsule, _ = workflow._compile_handoff(
            fixture_id,
            "isolation-validation",
            "candidate-isolation-validation",
            "codex/gpt-6-sol",
        )
        for transport in plan["transports"]:
            prompt = workflow._critic_prompt(
                capsule,
                workspace,
                workflow._editable_paths(manifest, fixture_id),
                transport,
            )
            assert all(marker not in prompt for marker in forbidden)
