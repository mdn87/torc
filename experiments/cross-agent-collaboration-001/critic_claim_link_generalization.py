"""Build, run, and score the new-fixture compact claim-link capability probe."""

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

import codex_usage_snapshot  # noqa: E402
import critic_claim_link_probe as link  # noqa: E402
import fixture_control  # noqa: E402
import native_context_request as request_builder  # noqa: E402
import worker_runner  # noqa: E402
import workflow_runner as workflow  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402

EXPERIMENT_ROOT = Path(__file__).resolve().parent
PLAN_PATH = EXPERIMENT_ROOT / "critic-claim-link-generalization-006-plan.json"


class CriticClaimLinkGeneralizationError(RuntimeError):
    """Raised when the generalization probe violates a preregistered control."""


def _object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise CriticClaimLinkGeneralizationError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise CriticClaimLinkGeneralizationError(f"expected a JSON object: {path}")
    return value


def _sha256_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _write_json(path: Path, value: dict[str, Any]) -> None:
    path.write_text(canonical_json(value) + "\n", encoding="utf-8")


def _candidates(plan: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = plan.get("candidates")
    if not isinstance(candidates, list) or len(candidates) != 2:
        raise CriticClaimLinkGeneralizationError("exactly two candidates are required")
    manifest = fixture_control.load_manifest()
    identifiers: set[str] = set()
    verified_candidates = []
    for candidate in candidates:
        if not isinstance(candidate, dict):
            raise CriticClaimLinkGeneralizationError("candidate controls are invalid")
        candidate_id = candidate.get("candidate_id")
        fixture_id = candidate.get("fixture_id")
        expected_hash = candidate.get("candidate_workspace_tree_sha256")
        if (
            not isinstance(candidate_id, str)
            or not candidate_id
            or candidate_id in identifiers
            or not isinstance(fixture_id, str)
            or not isinstance(expected_hash, str)
        ):
            raise CriticClaimLinkGeneralizationError("candidate identity is invalid")
        identifiers.add(candidate_id)
        verified = fixture_control.verify_fixture(fixture_id, manifest)
        if verified["agent_visible_sha256"] != expected_hash:
            raise CriticClaimLinkGeneralizationError(f"candidate fixture drifted: {candidate_id}")
        verified_candidates.append(candidate)
    return verified_candidates


def _capsule(candidate: dict[str, Any], model: str) -> dict[str, Any]:
    capsule, _ = workflow._compile_handoff(
        candidate["fixture_id"],
        f"critic-claim-link-generalization-006-{candidate['candidate_id']}",
        f"candidate-{candidate['candidate_workspace_tree_sha256'][:16]}",
        f"openai-responses/{model}",
    )
    return capsule


def _claim_ids(plan: dict[str, Any], candidates: list[dict[str, Any]]) -> dict[str, list[str]]:
    model = plan["provider_controls"]["model"]
    categories = plan["reviewable_claim_categories"]
    result = {}
    for candidate in candidates:
        candidate_id = candidate["candidate_id"]
        claims = _capsule(candidate, model)["claims"]
        identifiers = [
            claim_id for category in categories for claim_id in sorted(claims.get(category, {}))
        ]
        if not identifiers or len(identifiers) != len(set(identifiers)):
            raise CriticClaimLinkGeneralizationError(
                f"reviewable claim IDs are invalid for {candidate_id}"
            )
        expected = candidate.get("expected_claim_statuses")
        if not isinstance(expected, dict) or set(expected) != set(identifiers):
            raise CriticClaimLinkGeneralizationError(
                f"expected claim statuses do not match the capsule for {candidate_id}"
            )
        if set(expected.values()) - {"met", "unmet"}:
            raise CriticClaimLinkGeneralizationError(
                f"expected claim status value is invalid for {candidate_id}"
            )
        result[candidate_id] = identifiers
    return result


def _payloads(plan: dict[str, Any], candidates: list[dict[str, Any]]) -> list[dict[str, Any]]:
    model = plan["provider_controls"]["model"]
    payloads = []
    for candidate in candidates:
        payload = request_builder._critic_payload(candidate, "portable_direct", model)
        payloads.append(
            {
                "candidate_id": candidate["candidate_id"],
                "fixture_id": candidate["fixture_id"],
                "candidate_workspace_tree_sha256": candidate["candidate_workspace_tree_sha256"],
                "payload": payload,
                "payload_bytes": len(payload.encode("utf-8")),
                "payload_sha256": hashlib.sha256(payload.encode("utf-8")).hexdigest(),
            }
        )
    return payloads


def _verify_apparatus(plan: dict[str, Any]) -> list[dict[str, str]]:
    verified = []
    for item in plan.get("apparatus_inputs", []):
        path = REPO_ROOT / item["path"]
        observed = _sha256_file(path)
        if observed != item["sha256"]:
            raise CriticClaimLinkGeneralizationError(
                f"apparatus hash drifted for {item['path']}: {observed}"
            )
        verified.append({"path": item["path"], "sha256": observed})
    if not verified:
        raise CriticClaimLinkGeneralizationError("frozen apparatus inputs are missing")
    return verified


def build_probe() -> dict[str, Any]:
    """Return the exact model-free request without launching Codex."""
    plan = _object(PLAN_PATH)
    if plan.get("status") not in {"draft", "ready", "complete", "rejected"}:
        raise CriticClaimLinkGeneralizationError("probe is not plannable")
    candidates = _candidates(plan)
    claim_ids = _claim_ids(plan, candidates)
    payloads = _payloads(plan, candidates)
    prompt = link._prompt(payloads=payloads, claim_ids=claim_ids)
    return {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "plan_status": plan["status"],
        "execute": False,
        "candidate_order": [item["candidate_id"] for item in candidates],
        "reviewable_claim_ids": claim_ids,
        "candidates": [
            {key: value for key, value in payload.items() if key != "payload"}
            for payload in payloads
        ],
        "prompt_bytes": len(prompt.encode("utf-8")),
        "prompt_sha256": hashlib.sha256(prompt.encode("utf-8")).hexdigest(),
        "plan_sha256": _sha256_file(PLAN_PATH),
        "prompt": prompt,
    }


def _candidate_control(candidate: dict[str, Any], model: str) -> dict[str, Any]:
    _, control = workflow._compile_handoff(
        candidate["fixture_id"],
        f"critic-claim-link-generalization-006-{candidate['candidate_id']}",
        f"candidate-{candidate['candidate_workspace_tree_sha256'][:16]}",
        f"openai-responses/{model}",
    )
    return control


def validate_output(value: dict[str, Any], *, plan: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = _candidates(plan)
    candidate_ids = [item["candidate_id"] for item in candidates]
    if set(value) != {"schema_version", "critiques"} or value.get("schema_version") != 1:
        raise CriticClaimLinkGeneralizationError("output header is invalid")
    critiques = value.get("critiques")
    if not isinstance(critiques, list) or len(critiques) != len(candidates):
        raise CriticClaimLinkGeneralizationError("critique count is invalid")
    if [item.get("candidate_id") for item in critiques if isinstance(item, dict)] != candidate_ids:
        raise CriticClaimLinkGeneralizationError("candidate identity or order drifted")
    claim_ids = _claim_ids(plan, candidates)
    model = plan["provider_controls"]["model"]
    validated = []
    for item, candidate in zip(critiques, candidates, strict=True):
        if not isinstance(item, dict) or set(item) != {
            "candidate_id",
            "claim_links",
            "result",
        }:
            raise CriticClaimLinkGeneralizationError("candidate envelope is invalid")
        critique = item.get("result")
        if not isinstance(critique, dict):
            raise CriticClaimLinkGeneralizationError("nested critique is invalid")
        try:
            workflow._validate_critique(
                critique,
                _candidate_control(candidate, model),
            )
            links = link._validate_claim_links(
                item=item,
                expected_claim_ids=claim_ids[candidate["candidate_id"]],
            )
        except (workflow.WorkflowRunnerError, link.CriticClaimLinkProbeError) as exc:
            raise CriticClaimLinkGeneralizationError(
                f"invalid critique for {candidate['candidate_id']}: {exc}"
            ) from exc
        expected = candidate["expected_claim_statuses"]
        validated.append(
            {
                "candidate_id": candidate["candidate_id"],
                "critique": critique,
                **links,
                "expected_claim_statuses": expected,
                "claim_map_correct": links["observed_claim_statuses"] == expected,
                "verdict_correct": critique["verdict"] == candidate["expected_verdict"],
            }
        )
    return validated


def execute_probe(
    *,
    run_dir: Path,
    expected_plan_sha256: str,
    expected_prompt_sha256: str,
) -> dict[str, Any]:
    plan = _object(PLAN_PATH)
    if plan.get("status") != "ready":
        raise CriticClaimLinkGeneralizationError("probe is not ready")
    _verify_apparatus(plan)
    probe = build_probe()
    if probe["plan_sha256"] != expected_plan_sha256:
        raise CriticClaimLinkGeneralizationError("plan hash does not match")
    if probe["prompt_sha256"] != expected_prompt_sha256:
        raise CriticClaimLinkGeneralizationError("prompt hash does not match")
    configured = Path(plan["call_budget"]["run_directory"])
    expected_run = (EXPERIMENT_ROOT / configured).resolve()
    resolved_run = run_dir.resolve()
    if configured.is_absolute() or ".." in configured.parts or resolved_run != expected_run:
        raise CriticClaimLinkGeneralizationError("run directory does not match the plan")
    if resolved_run.exists():
        raise CriticClaimLinkGeneralizationError(f"run directory already exists: {resolved_run}")
    checkpoint = codex_usage_snapshot.read_snapshot(
        stop_threshold_percent=plan["call_budget"]["stop_threshold_percent"]
    )
    if checkpoint["decision"] != "proceed":
        raise CriticClaimLinkGeneralizationError("current usage reached the stop threshold")

    resolved_run.mkdir(parents=True)
    _write_json(
        resolved_run / "probe-plan.json",
        {key: value for key, value in probe.items() if key != "prompt"},
    )
    _write_json(resolved_run / "usage-checkpoint.json", checkpoint)
    attempt_path = resolved_run / "attempt.json"
    _write_json(
        attempt_path,
        {
            "schema_version": 1,
            "status": "reserved",
            "retry_requires_plan_change": True,
        },
    )
    phase_dir = resolved_run / "phase"
    candidates = _candidates(plan)
    settings = workflow._provider_settings(workflow.load_manifest(), "codex")
    error: Exception | None = None
    record: dict[str, Any] | None = None
    try:
        workspace = EXPERIMENT_ROOT / "fixtures" / candidates[0]["fixture_id"] / "agent-visible"
        record = workflow._run_worker(
            settings=settings,
            workspace=workspace,
            prompt=probe["prompt"],
            effort=plan["provider_controls"]["effort"],
            role="critic",
            tool_mode="none",
            session_mode="fresh-ephemeral",
            session_id=None,
            timeout_seconds=workflow.load_manifest()["timeout_seconds"],
            output_dir=phase_dir,
        )
        output = workflow._phase_output_object("codex", phase_dir)
        scored = validate_output(output, plan=plan)
    except (
        CriticClaimLinkGeneralizationError,
        fixture_control.FixtureControlError,
        link.CriticClaimLinkProbeError,
        request_builder.NativeContextRequestError,
        workflow.WorkflowRunnerError,
        worker_runner.WorkerRunnerError,
    ) as exc:
        error = exc
    if error is not None:
        _write_json(
            resolved_run / "disposition.json",
            {
                "schema_version": 1,
                "status": "excluded",
                "reason": str(error),
                "model_call_may_have_started": (phase_dir / "worker-run.json").exists(),
                "retry_allowed": False,
            },
        )
        raise CriticClaimLinkGeneralizationError(
            f"probe excluded; evidence preserved: {error}"
        ) from error
    assert record is not None
    thresholds = plan["capability_thresholds"]
    quality_passed = all(
        item["claim_map_correct"]
        and item["verdict_correct"]
        and item["structured_finding_linkage_complete"]
        for item in scored
    )
    budget_passed = (
        record["usage"]["input_tokens"] <= thresholds["maximum_input_tokens"]
        and record["timing"]["completion_ms"] <= thresholds["maximum_completion_ms"]
    )
    capability_confirmed = quality_passed and budget_passed
    result = {
        "schema_version": 1,
        "series_id": plan["series_id"],
        "status": "capability_confirmed" if capability_confirmed else "capability_rejected",
        "prompt_bytes": probe["prompt_bytes"],
        "prompt_sha256": probe["prompt_sha256"],
        "candidate_results": scored,
        "quality_passed": quality_passed,
        "usage": record["usage"],
        "timing": record["timing"],
        "budget_thresholds_passed": budget_passed,
        "capability_thresholds_passed": capability_confirmed,
        "matched_direct_comparison_available": False,
    }
    _write_json(resolved_run / "batch-output.json", output)
    _write_json(resolved_run / "result.json", result)
    _write_json(
        attempt_path,
        {
            "schema_version": 1,
            "status": "completed",
            "retry_requires_plan_change": True,
        },
    )
    return result


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--expected-plan-sha256")
    parser.add_argument("--expected-prompt-sha256")
    parser.add_argument("--include-prompt", action="store_true")
    parser.add_argument("--execute", action="store_true")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        if not args.execute:
            value = build_probe()
            if not args.include_prompt:
                value = {key: item for key, item in value.items() if key != "prompt"}
            print(canonical_json(value))
            return 0
        required = {
            "--run-dir": args.run_dir,
            "--expected-plan-sha256": args.expected_plan_sha256,
            "--expected-prompt-sha256": args.expected_prompt_sha256,
        }
        missing = [name for name, value in required.items() if value is None]
        if missing:
            raise CriticClaimLinkGeneralizationError("live probe requires " + ", ".join(missing))
        value = execute_probe(
            run_dir=args.run_dir,
            expected_plan_sha256=args.expected_plan_sha256,
            expected_prompt_sha256=args.expected_prompt_sha256,
        )
        print(canonical_json(value))
        return 0
    except (
        CriticClaimLinkGeneralizationError,
        codex_usage_snapshot.CodexUsageSnapshotError,
        fixture_control.FixtureControlError,
        link.CriticClaimLinkProbeError,
        request_builder.NativeContextRequestError,
    ) as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
