from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import native_context_request as native  # noqa: E402

CANDIDATE = "refactor-baseline-v1"
MODEL = "gpt-6.1-sol"


def test_portable_request_reuses_compact_critic_payload() -> None:
    request = native.build_request(
        candidate_id=CANDIDATE, arm="portable_direct", model=MODEL
    )
    plan = native.request_plan(
        candidate_id=CANDIDATE, arm="portable_direct", model=MODEL
    )

    assert request["store"] is False
    assert request["reasoning"] == {"effort": "low"}
    assert "multi_agent" not in request
    assert "def legacy_route" in request["input"]
    assert "ARCHITECTURE.md" not in request["input"]
    assert plan["expected_subagent_count"] == 0
    assert plan["required_beta"] is None
    assert plan["execute"] is False


def test_isolated_request_requires_one_non_inheriting_subagent() -> None:
    direct = native.build_request(
        candidate_id=CANDIDATE, arm="portable_direct", model=MODEL
    )
    request = native.build_request(
        candidate_id=CANDIDATE, arm="native_isolated", model=MODEL
    )
    plan = native.request_plan(
        candidate_id=CANDIDATE, arm="native_isolated", model=MODEL
    )

    assert request["multi_agent"] == {
        "enabled": True,
        "max_concurrent_subagents": 1,
    }
    assert "fork_turns set to 'none'" in request["input"]
    assert "include the complete payload" in request["input"].lower()
    assert direct["input"] in request["input"]
    assert plan["critic_payload_sha256"] == native._sha256_text(direct["input"])
    assert plan["expected_subagent_count"] == 1
    assert plan["required_beta"] == "responses_multi_agent=v1"


def test_inherited_request_contains_full_visible_bundle() -> None:
    request = native.build_request(
        candidate_id=CANDIDATE, arm="native_inherited", model=MODEL
    )
    plan = native.request_plan(
        candidate_id=CANDIDATE, arm="native_inherited", model=MODEL
    )

    assert "fork_turns set to 'all'" in request["input"]
    assert "ARCHITECTURE.md" in request["input"]
    assert plan["fork_turns"] == "all"
    assert plan["critic_context"] == "full-visible-bundle-v1"
    assert plan["request_input_bytes"] > plan["critic_payload_bytes"]


def test_request_inputs_exclude_oracle_and_scorer_contract() -> None:
    forbidden = (
        "oracle.json",
        "critic_probe_score.py",
        "required_defect_areas",
        "evidence_term_groups",
    )

    for arm in native.ARMS:
        request = native.build_request(candidate_id=CANDIDATE, arm=arm, model=MODEL)
        assert all(marker not in request["input"] for marker in forbidden)


def test_only_preregistered_pilot_candidate_is_accepted() -> None:
    with pytest.raises(
        native.NativeContextRequestError,
        match="not the preregistered pilot candidate",
    ):
        native.build_request(
            candidate_id="release-policy-baseline-v1",
            arm="portable_direct",
            model=MODEL,
        )


def test_plan_and_source_candidate_are_hash_pinned() -> None:
    plan = json.loads(
        (EXPERIMENT / "native-context-series-003-plan.json").read_text(encoding="utf-8")
    )
    source = json.loads(
        (EXPERIMENT / "critic-transport-series-002-plan.json").read_text(
            encoding="utf-8"
        )
    )
    candidate = next(
        item
        for item in source["candidates"]
        if item["candidate_id"] == plan["candidate_policy"]["pilot_candidate_id"]
    )
    request_plan = native.request_plan(
        candidate_id=CANDIDATE, arm="portable_direct", model=MODEL
    )

    assert request_plan["candidate_workspace_tree_sha256"] == candidate[
        "candidate_workspace_tree_sha256"
    ]
    assert request_plan["plan_sha256"]
    assert request_plan["source_candidate_plan_sha256"]
