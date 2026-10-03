from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import native_context_response as native  # noqa: E402

CANDIDATE = "refactor-baseline-v1"
MODEL = "gpt-6.1-sol"


def _critique() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "verdict": "changes_requested",
        "findings": [
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
        ],
    }


def _usage() -> dict[str, Any]:
    return {
        "input_tokens": 1200,
        "input_tokens_details": {"cached_tokens": 200},
        "output_tokens": 300,
        "output_tokens_details": {"reasoning_tokens": 100},
        "total_tokens": 1500,
    }


def _response(arm: str) -> dict[str, Any]:
    final = {
        "type": "message",
        "id": "msg_final",
        "content": [{"type": "output_text", "text": json.dumps(_critique())}],
    }
    output: list[dict[str, Any]] = []
    if arm != "portable_direct":
        fork_turns = "none" if arm == "native_isolated" else "all"
        output.extend(
            [
                {
                    "type": "multi_agent_call",
                    "id": "mac_spawn",
                    "action": "spawn_agent",
                    "arguments": json.dumps(
                        {
                            "task_name": "critic",
                            "fork_turns": fork_turns,
                            "message": "enc_spawn_payload",
                        }
                    ),
                    "agent": {"agent_name": "/root"},
                },
                {
                    "type": "agent_message",
                    "id": "amsg_critic",
                    "author": "/root/critic",
                    "recipient": "/root",
                    "content": [
                        {
                            "type": "encrypted_content",
                            "encrypted_content": "enc_critic_result",
                        }
                    ],
                    "agent": {"agent_name": "/root"},
                },
            ]
        )
        final["phase"] = "final_answer"
        final["agent"] = {"agent_name": "/root"}
    output.append(final)
    return {
        "id": "resp_test",
        "status": "completed",
        "model": MODEL,
        "usage": _usage(),
        "output": output,
    }


@pytest.mark.parametrize(
    "arm", ["portable_direct", "native_isolated", "native_inherited"]
)
def test_response_is_validated_scored_and_sanitized(arm: str) -> None:
    result = native.validate_response(
        _response(arm),
        candidate_id=CANDIDATE,
        arm=arm,
        model=MODEL,
        completion_ms=1234.5,
    )

    assert result["score"]["defect_area_recall"] == 1.0
    assert result["usage"]["uncached_input_tokens"] == 1000
    assert result["timing"]["completion_ms"] == 1234.5
    assert result["transport"]["spawn_call_count"] == (
        0 if arm == "portable_direct" else 1
    )
    serialized = json.dumps(result)
    assert "enc_spawn_payload" not in serialized
    assert "enc_critic_result" not in serialized
    if arm != "portable_direct":
        assert len(result["transport"]["opaque_artifacts"]) == 2


def test_wrong_fork_turns_is_rejected() -> None:
    response = _response("native_isolated")
    response["output"][0]["arguments"] = json.dumps(
        {"task_name": "critic", "fork_turns": "all", "message": "enc_value"}
    )

    with pytest.raises(native.NativeContextResponseError, match="wrong critic shape"):
        native.validate_response(
            response,
            candidate_id=CANDIDATE,
            arm="native_isolated",
            model=MODEL,
        )


def test_extra_subagent_is_rejected() -> None:
    response = _response("native_inherited")
    response["output"].insert(1, dict(response["output"][0]))

    with pytest.raises(native.NativeContextResponseError, match="spawn count"):
        native.validate_response(
            response,
            candidate_id=CANDIDATE,
            arm="native_inherited",
            model=MODEL,
        )


def test_missing_usage_is_rejected() -> None:
    response = _response("portable_direct")
    del response["usage"]

    with pytest.raises(native.NativeContextResponseError, match="usage is missing"):
        native.validate_response(
            response,
            candidate_id=CANDIDATE,
            arm="portable_direct",
            model=MODEL,
        )


def test_unknown_claim_is_rejected() -> None:
    response = _response("portable_direct")
    critique = _critique()
    critique["findings"][0]["claim_ids"] = ["not-a-claim"]
    response["output"][0]["content"][0]["text"] = json.dumps(critique)

    with pytest.raises(native.NativeContextResponseError, match="unknown claim"):
        native.validate_response(
            response,
            candidate_id=CANDIDATE,
            arm="portable_direct",
            model=MODEL,
        )
