"""Validate and score one in-memory Series 003 Responses API result."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import critic_probe_score as probe_score  # noqa: E402
import native_context_request as request_builder  # noqa: E402
import workflow_runner as workflow  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

ROOT_AGENT = "/root"
SUBAGENT = "/root/critic"
_ALLOWED_NATIVE_ACTIONS = {"spawn_agent", "wait_agent"}


class NativeContextResponseError(RuntimeError):
    """Raised when a response violates the frozen Series 003 controls."""


def _nonnegative_int(value: Any, label: str) -> int:
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise NativeContextResponseError(f"response usage {label} is invalid")
    return value


def _normalize_usage(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        raise NativeContextResponseError("response-level usage is missing")
    input_tokens = _nonnegative_int(value.get("input_tokens"), "input_tokens")
    output_tokens = _nonnegative_int(value.get("output_tokens"), "output_tokens")
    total_tokens = _nonnegative_int(value.get("total_tokens"), "total_tokens")
    if total_tokens != input_tokens + output_tokens:
        raise NativeContextResponseError("response usage total is inconsistent")
    input_details = value.get("input_tokens_details", {})
    output_details = value.get("output_tokens_details", {})
    if not isinstance(input_details, dict) or not isinstance(output_details, dict):
        raise NativeContextResponseError("response usage detail shape is invalid")
    cached_tokens = _nonnegative_int(input_details.get("cached_tokens", 0), "cached_tokens")
    reasoning_tokens = _nonnegative_int(
        output_details.get("reasoning_tokens", 0), "reasoning_tokens"
    )
    if cached_tokens > input_tokens or reasoning_tokens > output_tokens:
        raise NativeContextResponseError("response usage detail exceeds its total")
    return {
        "input_tokens": input_tokens,
        "cached_input_tokens": cached_tokens,
        "uncached_input_tokens": input_tokens - cached_tokens,
        "output_tokens": output_tokens,
        "reasoning_output_tokens": reasoning_tokens,
        "total_tokens": total_tokens,
    }


def _agent_name(item: dict[str, Any]) -> str:
    agent = item.get("agent")
    if agent is None:
        return ROOT_AGENT
    if not isinstance(agent, dict) or not isinstance(agent.get("agent_name"), str):
        raise NativeContextResponseError("response item has an invalid agent attribution")
    return agent["agent_name"]


def _output_text(item: dict[str, Any]) -> str:
    content = item.get("content")
    if not isinstance(content, list):
        raise NativeContextResponseError("response message content is invalid")
    parts = []
    for part in content:
        if not isinstance(part, dict):
            raise NativeContextResponseError("response message part is invalid")
        if part.get("type") == "output_text":
            text = part.get("text")
            if not isinstance(text, str):
                raise NativeContextResponseError("response output text is invalid")
            parts.append(text)
    if not parts:
        raise NativeContextResponseError("response message has no output text")
    return "".join(parts)


def _decode_arguments(item: dict[str, Any]) -> dict[str, Any]:
    arguments = item.get("arguments")
    if not isinstance(arguments, str):
        raise NativeContextResponseError("multi-agent call arguments are invalid")
    try:
        decoded = json.loads(arguments)
    except json.JSONDecodeError as exc:
        raise NativeContextResponseError("multi-agent call arguments are not JSON") from exc
    if not isinstance(decoded, dict):
        raise NativeContextResponseError("multi-agent call arguments are not an object")
    return decoded


def _opaque_digest(
    *, value: str, item_id: Any, source: str, artifacts: list[dict[str, Any]]
) -> None:
    artifacts.append(
        {
            "source": source,
            "item_id": item_id if isinstance(item_id, str) else None,
            "bytes": len(value.encode("utf-8")),
            "sha256": hashlib.sha256(value.encode("utf-8")).hexdigest(),
        }
    )


def _inspect_items(
    output: list[Any], *, arm: str
) -> tuple[str, dict[str, Any]]:
    expected_fork = request_builder._FORK_TURNS_BY_ARM.get(arm)
    expected_spawn_count = 0 if arm == "portable_direct" else 1
    actions: list[str] = []
    spawn_arguments: list[dict[str, Any]] = []
    agent_counts: Counter[str] = Counter()
    observed_agents: set[str] = set()
    opaque_artifacts: list[dict[str, Any]] = []
    root_final_texts: list[str] = []

    for raw_item in output:
        if not isinstance(raw_item, dict):
            raise NativeContextResponseError("response output contains a non-object item")
        item_type = raw_item.get("type")
        agent = _agent_name(raw_item)
        agent_counts[agent] += 1
        observed_agents.add(agent)

        if item_type == "message":
            phase = raw_item.get("phase")
            if agent == ROOT_AGENT and (
                phase == "final_answer" or (arm == "portable_direct" and phase is None)
            ):
                root_final_texts.append(_output_text(raw_item))
        elif item_type == "multi_agent_call":
            action = raw_item.get("action")
            if not isinstance(action, str):
                raise NativeContextResponseError("multi-agent call has no action")
            actions.append(action)
            arguments = _decode_arguments(raw_item)
            if action == "spawn_agent":
                spawn_arguments.append(arguments)
                message = arguments.get("message")
                if isinstance(message, str) and message.startswith("enc_"):
                    _opaque_digest(
                        value=message,
                        item_id=raw_item.get("id"),
                        source="spawn_agent.message",
                        artifacts=opaque_artifacts,
                    )
        elif item_type == "agent_message":
            author = raw_item.get("author")
            recipient = raw_item.get("recipient")
            if isinstance(author, str):
                observed_agents.add(author)
            if isinstance(recipient, str):
                observed_agents.add(recipient)
            content = raw_item.get("content")
            if not isinstance(content, list):
                raise NativeContextResponseError("agent message content is invalid")
            for part in content:
                if not isinstance(part, dict):
                    raise NativeContextResponseError("agent message part is invalid")
                encrypted = part.get("encrypted_content")
                if part.get("type") == "encrypted_content":
                    if not isinstance(encrypted, str):
                        raise NativeContextResponseError(
                            "agent message encrypted content is invalid"
                        )
                    _opaque_digest(
                        value=encrypted,
                        item_id=raw_item.get("id"),
                        source="agent_message.content",
                        artifacts=opaque_artifacts,
                    )

    if len(spawn_arguments) != expected_spawn_count:
        raise NativeContextResponseError("response has an unexpected subagent spawn count")
    if arm == "portable_direct":
        if actions or observed_agents != {ROOT_AGENT}:
            raise NativeContextResponseError("portable response contains agent delegation")
    else:
        if not set(actions) <= _ALLOWED_NATIVE_ACTIONS:
            raise NativeContextResponseError("native response used an unplanned agent action")
        spawn = spawn_arguments[0]
        if spawn.get("task_name") != "critic" or spawn.get("fork_turns") != expected_fork:
            raise NativeContextResponseError("native response spawned the wrong critic shape")
        non_root_agents = observed_agents - {ROOT_AGENT}
        if non_root_agents != {SUBAGENT}:
            raise NativeContextResponseError("native response agent attribution is incomplete")
    if len(root_final_texts) != 1:
        raise NativeContextResponseError("response has no unique root final answer")
    return root_final_texts[0], {
        "multi_agent_actions": actions,
        "spawn_call_count": len(spawn_arguments),
        "agent_output_item_counts": dict(sorted(agent_counts.items())),
        "observed_agents": sorted(observed_agents),
        "opaque_artifacts": opaque_artifacts,
    }


def _critique(text: str, *, candidate_id: str, model: str) -> dict[str, Any]:
    try:
        value = json.loads(text)
    except json.JSONDecodeError as exc:
        raise NativeContextResponseError("root final answer is not one JSON object") from exc
    if not isinstance(value, dict):
        raise NativeContextResponseError("root final answer is not a JSON object")
    candidate = request_builder._candidate(candidate_id)
    capsule, control = workflow._compile_handoff(
        candidate["fixture_id"],
        f"critic-transport-003-{candidate_id}",
        f"candidate-{candidate['candidate_workspace_tree_sha256'][:16]}",
        f"openai-responses/{model}",
    )
    try:
        workflow._validate_critique(value, control)
    except workflow.WorkflowRunnerError as exc:
        raise NativeContextResponseError(f"critic result is invalid: {exc}") from exc
    expected_capsule = request_builder._critic_payload(
        candidate, "portable_direct", model
    )
    if canonical_json(capsule) not in expected_capsule:
        raise NativeContextResponseError("critic capsule reconstruction is inconsistent")
    return value


def _score(critique: dict[str, Any], *, candidate_id: str, arm: str) -> dict[str, Any]:
    plan = probe_score._object(probe_score.DEFAULT_PLAN)
    candidate = probe_score._candidate(plan, candidate_id)
    findings = critique["findings"]
    areas = candidate["required_defect_areas"]
    covered: list[str] = []
    matched_findings: set[str] = set()
    for area in areas:
        matches = [
            finding
            for finding in findings
            if probe_score._finding_matches_area(finding, area)
        ]
        if matches:
            covered.append(area["area_id"])
            matched_findings.update(finding["finding_id"] for finding in matches)
    finding_ids = {finding["finding_id"] for finding in findings}
    acceptable_claim_ids = {
        claim_id for area in areas for claim_id in area["acceptable_claim_ids"]
    }
    required_count = len(areas)
    return {
        "schema_version": 1,
        "series_id": "critic-transport-series-003",
        "candidate_id": candidate_id,
        "arm": arm,
        "critic_verdict": critique["verdict"],
        "changes_requested_correct": critique["verdict"] == "changes_requested",
        "required_defect_area_count": required_count,
        "covered_defect_area_count": len(covered),
        "defect_area_recall": round(len(covered) / required_count, 6),
        "covered_defect_area_ids": covered,
        "missed_defect_area_ids": [
            area["area_id"] for area in areas if area["area_id"] not in covered
        ],
        "finding_count": len(findings),
        "valid_claim_citation_count": sum(
            1
            for finding in findings
            for claim_id in finding["claim_ids"]
            if claim_id in acceptable_claim_ids
        ),
        "unsupported_finding_count": len(finding_ids - matched_findings),
        "unsupported_finding_ids": sorted(finding_ids - matched_findings),
        "candidate_workspace_tree_sha256": candidate[
            "candidate_workspace_tree_sha256"
        ],
    }


def validate_response(
    response: dict[str, Any],
    *,
    candidate_id: str,
    arm: str,
    model: str,
    completion_ms: float | None = None,
) -> dict[str, Any]:
    """Fail closed and return sanitized evidence for one completed response."""
    request_plan = request_builder.request_plan(
        candidate_id=candidate_id, arm=arm, model=model
    )
    if response.get("status") != "completed":
        raise NativeContextResponseError("response did not complete")
    response_id = response.get("id")
    if not isinstance(response_id, str) or not response_id:
        raise NativeContextResponseError("response identifier is missing")
    if response.get("model") != model:
        raise NativeContextResponseError("response model does not match the request")
    output = response.get("output")
    if not isinstance(output, list):
        raise NativeContextResponseError("response output is invalid")
    text, transport = _inspect_items(output, arm=arm)
    critique = _critique(text, candidate_id=candidate_id, model=model)
    if completion_ms is not None and (
        not isinstance(completion_ms, (int, float))
        or isinstance(completion_ms, bool)
        or completion_ms < 0
    ):
        raise NativeContextResponseError("completion timing is invalid")
    sanitized = {
        "schema_version": 1,
        "series_id": "critic-transport-series-003",
        "status": "validated",
        "candidate_id": candidate_id,
        "arm": arm,
        "model": model,
        "response_id": response_id,
        "request": {
            "input_bytes": request_plan["request_input_bytes"],
            "input_sha256": request_plan["request_input_sha256"],
            "body_sha256": request_plan["request_body_sha256"],
            "plan_sha256": request_plan["plan_sha256"],
        },
        "usage": _normalize_usage(response.get("usage")),
        "timing": {"completion_ms": completion_ms},
        "transport": transport,
        "critique": critique,
        "score": _score(critique, candidate_id=candidate_id, arm=arm),
    }
    serialized = canonical_json(sanitized)
    if "encrypted_content" in serialized or "enc_" in serialized:
        raise NativeContextResponseError("sanitized evidence retained opaque content")
    return sanitized


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--response", type=Path, required=True)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--arm", choices=request_builder.ARMS, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument("--completion-ms", type=float)
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        response = json.loads(args.response.read_text(encoding="utf-8"))
        if not isinstance(response, dict):
            raise NativeContextResponseError("response file is not a JSON object")
        print(
            canonical_json(
                validate_response(
                    response,
                    candidate_id=args.candidate,
                    arm=args.arm,
                    model=args.model,
                    completion_ms=args.completion_ms,
                )
            )
        )
        return 0
    except (OSError, json.JSONDecodeError, NativeContextResponseError) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
