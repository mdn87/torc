"""Build a model-free request plan for native context Series 003."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import fixture_control  # noqa: E402
import workflow_runner as workflow  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
PLAN_PATH = EXPERIMENT_ROOT / "native-context-series-003-plan.json"
SOURCE_PLAN_PATH = EXPERIMENT_ROOT / "critic-transport-series-002-plan.json"
ARMS = ("portable_direct", "native_isolated", "native_inherited")
_CONTEXT_BY_ARM = {
    "portable_direct": workflow.COMPACT_CRITIC_CONTEXT,
    "native_isolated": workflow.COMPACT_CRITIC_CONTEXT,
    "native_inherited": workflow.FULL_CRITIC_CONTEXT,
}
_FORK_TURNS_BY_ARM = {
    "native_isolated": "none",
    "native_inherited": "all",
}


class NativeContextRequestError(RuntimeError):
    """Raised when a Series 003 request cannot preserve its controls."""


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NativeContextRequestError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise NativeContextRequestError(f"expected a JSON object: {path}")
    return value


def _sha256_text(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _candidate(candidate_id: str) -> dict[str, Any]:
    source_plan = _read_object(SOURCE_PLAN_PATH)
    candidates = source_plan.get("candidates")
    if not isinstance(candidates, list):
        raise NativeContextRequestError("Series 002 has no candidate controls")
    matches = [item for item in candidates if item.get("candidate_id") == candidate_id]
    if len(matches) != 1:
        raise NativeContextRequestError(f"unknown or repeated candidate: {candidate_id}")
    candidate = matches[0]
    fixture_id = candidate.get("fixture_id")
    expected_hash = candidate.get("candidate_workspace_tree_sha256")
    if not isinstance(fixture_id, str) or not isinstance(expected_hash, str):
        raise NativeContextRequestError("candidate controls are incomplete")
    verified = fixture_control.verify_fixture(fixture_id, fixture_control.load_manifest())
    if verified["agent_visible_sha256"] != expected_hash:
        raise NativeContextRequestError("candidate fixture has drifted from Series 002")
    return candidate


def _validate_model(model: str) -> str:
    cleaned = model.strip()
    if not cleaned or cleaned != model or any(character.isspace() for character in model):
        raise NativeContextRequestError("model must be one non-empty identifier")
    return model


def _critic_payload(candidate: dict[str, Any], arm: str, model: str) -> str:
    fixture_id = candidate["fixture_id"]
    candidate_hash = candidate["candidate_workspace_tree_sha256"]
    workspace = fixture_control.FIXTURES_ROOT / fixture_id / "agent-visible"
    manifest = workflow.load_manifest()
    capsule, _ = workflow._compile_handoff(
        fixture_id,
        f"critic-transport-003-{candidate['candidate_id']}",
        f"candidate-{candidate_hash[:16]}",
        f"openai-responses/{model}",
    )
    return workflow._critic_prompt(
        capsule,
        workspace,
        workflow._editable_paths(manifest, fixture_id),
        _CONTEXT_BY_ARM[arm],
    )


def _native_root_input(payload: str, arm: str) -> str:
    fork_turns = _FORK_TURNS_BY_ARM[arm]
    delivery = (
        "Include the complete payload below unchanged in the subagent's initial task message."
        if fork_turns == "none"
        else (
            "The subagent inherits this turn. Give it only a short instruction to review the "
            "inherited payload and return the required JSON."
        )
    )
    return (
        "This is a controlled transport trial. Act only as a relay; do not perform the review "
        "yourself. Spawn exactly one subagent named critic with fork_turns set to "
        f"{fork_turns!r}. {delivery} Tell the subagent not to spawn descendants, use tools, or "
        "add prose outside the required JSON. Wait for that subagent to finish, then return its "
        "JSON result unchanged. Do not call any other collaboration action except the one spawn "
        "and the wait needed for its result.\n\nCritic payload:\n" + payload
    )


def build_request(*, candidate_id: str, arm: str, model: str) -> dict[str, Any]:
    """Return one exact beta Responses request without making a network call."""
    if arm not in ARMS:
        raise NativeContextRequestError(f"unsupported arm: {arm}")
    model = _validate_model(model)
    plan = _read_object(PLAN_PATH)
    if plan.get("status") not in {"planned_requires_api_budget", "pilot_authorized"}:
        raise NativeContextRequestError("Series 003 is not in a request-planning state")
    if candidate_id != plan.get("candidate_policy", {}).get("pilot_candidate_id"):
        raise NativeContextRequestError("candidate is not the preregistered pilot candidate")
    candidate = _candidate(candidate_id)
    payload = _critic_payload(candidate, arm, model)
    request_input = payload if arm == "portable_direct" else _native_root_input(payload, arm)
    request: dict[str, Any] = {
        "model": model,
        "input": request_input,
        "reasoning": {"effort": "low"},
        "store": False,
    }
    if arm != "portable_direct":
        request["multi_agent"] = {"enabled": True, "max_concurrent_subagents": 1}
    return request


def request_plan(*, candidate_id: str, arm: str, model: str) -> dict[str, Any]:
    """Return sanitized deterministic evidence for one unexecuted request."""
    request = build_request(candidate_id=candidate_id, arm=arm, model=model)
    payload = _critic_payload(_candidate(candidate_id), arm, model)
    request_input = request["input"]
    request_bytes = canonical_json(request).encode("utf-8")
    return {
        "schema_version": 1,
        "series_id": "critic-transport-series-003",
        "status": "planned_not_executed",
        "execute": False,
        "api_surface": "beta.responses.create",
        "required_beta": "responses_multi_agent=v1" if arm != "portable_direct" else None,
        "candidate_id": candidate_id,
        "candidate_workspace_tree_sha256": _candidate(candidate_id)[
            "candidate_workspace_tree_sha256"
        ],
        "arm": arm,
        "critic_context": _CONTEXT_BY_ARM[arm],
        "model": model,
        "effort": "low",
        "expected_root_count": 1,
        "expected_subagent_count": 0 if arm == "portable_direct" else 1,
        "expected_api_request_count": 1,
        "fork_turns": _FORK_TURNS_BY_ARM.get(arm),
        "critic_payload_bytes": len(payload.encode("utf-8")),
        "critic_payload_sha256": _sha256_text(payload),
        "request_input_bytes": len(request_input.encode("utf-8")),
        "request_input_sha256": _sha256_text(request_input),
        "request_body_bytes": len(request_bytes),
        "request_body_sha256": hashlib.sha256(request_bytes).hexdigest(),
        "plan_sha256": hashlib.sha256(PLAN_PATH.read_bytes()).hexdigest(),
        "source_candidate_plan_sha256": hashlib.sha256(
            SOURCE_PLAN_PATH.read_bytes()
        ).hexdigest(),
        "request_shape": {
            key: value if key != "input" else "<redacted; see input hash and bytes>"
            for key, value in request.items()
        },
    }


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidate", required=True)
    parser.add_argument("--arm", choices=ARMS, required=True)
    parser.add_argument("--model", required=True)
    parser.add_argument(
        "--include-input",
        action="store_true",
        help="include the full non-secret request body in model-free output",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        result = request_plan(
            candidate_id=args.candidate,
            arm=args.arm,
            model=args.model,
        )
        if args.include_input:
            result["request"] = build_request(
                candidate_id=args.candidate,
                arm=args.arm,
                model=args.model,
            )
        print(canonical_json(result))
        return 0
    except (NativeContextRequestError, fixture_control.FixtureControlError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
