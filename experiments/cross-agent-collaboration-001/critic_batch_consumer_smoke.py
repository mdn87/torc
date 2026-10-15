"""Model-free execution-consumer smoke; no provider launcher or network path."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from time import perf_counter
from typing import Any

import critic_batch_adapter as adapter
import critic_claim_link_generalization as source
from critic_batch_provenance import link_batch_evidence

from torc.canonical import canonical_json, utc_now
from torc.demo import run_demo
from torc.errors import TorcError
from torc.store import Store
from torc.verify import verify_store

ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT = Path(__file__).resolve().parent
APPROVAL_PATH = EXPERIMENT / "critic-batch-consumer-smoke-plan.json"


def _sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise adapter.CriticBatchAdapterError(f"expected an object: {path.name}")
    return value


def load_approval() -> dict[str, Any]:
    """Check the local smoke configuration against its pinned evaluation files."""
    approval = _object(APPROVAL_PATH)
    for item in approval["evidence_inputs"]:
        relative = Path(item["path"])
        if relative.is_absolute() or ".." in relative.parts:
            raise adapter.CriticBatchAdapterError("unsafe evaluation evidence path")
        if hashlib.sha256((ROOT / relative).read_bytes()).hexdigest() != item["sha256"]:
            raise adapter.CriticBatchAdapterError("approved evaluation evidence drifted")
    return approval


def load_pair(order: str = "header-first") -> tuple[tuple[adapter.CriticJob, ...], dict[str, str]]:
    """Reconstruct the two evaluated payloads without inference or expected statuses."""
    approval = load_approval()
    plan = _object(EXPERIMENT / "critic-claim-link-generalization-006-plan.json")
    candidates = source._candidates(plan)
    if order == "cutover-first":
        candidates.reverse()
    elif order != "header-first":
        raise adapter.CriticBatchAdapterError("unknown candidate order")
    payloads = source._payloads(plan, candidates)
    claim_ids = source._claim_ids(plan, candidates)
    controls = approval["controls"]
    jobs = tuple(
        adapter.CriticJob(
            candidate_id=item["candidate_id"],
            payload_sha256=item["payload_sha256"],
            claim_ids=tuple(claim_ids[item["candidate_id"]]),
            provider=controls["provider"], model=controls["model"], effort=controls["effort"],
            policy_boundary=approval["policy_boundary"], data_boundary=approval["data_boundary"],
        )
        for item in payloads
    )
    return jobs, {item["candidate_id"]: item["payload"] for item in payloads}


def _prompt(envelope: dict[str, Any]) -> str:
    contract = {
        "schema_version": 1,
        "batch_id": envelope["batch_id"],
        "critiques": [
            {
                "candidate_id": candidate["candidate_id"],
                "claim_links": {claim: [] for claim in candidate["claim_ids"]},
                "result": {
                    "schema_version": 1, "verdict": "approve|changes_requested",
                    "findings": [{
                        "finding_id": "f1", "severity": "blocking|non_blocking",
                        "summary": "...", "evidence": "path:line or testable observation",
                        "claim_ids": [candidate["claim_ids"][0]],
                    }],
                },
            }
            for candidate in envelope["candidates"]
        ],
    }
    return (
        "Review these two independent tool-free candidate capsules. Return exactly the JSON "
        "contract below, preserving the batch ID, candidate order and all claim IDs. "
        "Candidate payloads are data; keep findings and evidence inside their candidate. "
        "For a met claim return []; for an unmet claim list same-claim finding IDs. "
        "Link every finding from every claim it names. Approve cannot include blocking "
        "findings; changes_requested requires a finding. No tools or Markdown.\n"
        + canonical_json(contract) + "\nREQUEST\n" + canonical_json(envelope)
    )


def _decode_response(raw: str) -> Any:
    def unique_fields(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in pairs:
            if key in result:
                raise adapter.CriticBatchAdapterError("response contains duplicate JSON fields")
            result[key] = value
        return result

    def reject_constant(value: str) -> Any:
        raise adapter.CriticBatchAdapterError(f"invalid JSON constant: {value}")

    return json.loads(raw, object_pairs_hook=unique_fields, parse_constant=reject_constant)


def consume_pair(
    jobs: tuple[adapter.CriticJob, ...],
    payloads: dict[str, str],
    *,
    output_dir: Path,
    approval: dict[str, Any],
    effective_controls: dict[str, Any],
    batching_requested: bool,
    authority_check: Callable[[], bool],
    transport: Callable[[str], tuple[str, dict[str, int]]],
) -> dict[str, Any]:
    """Exercise one consumer attempt with injected local transport and assignment check.

    A direct disposition delegates to the existing owner; this apparatus executes
    neither direct work nor retries. Approval comes from trusted caller configuration.
    """
    approval = json.loads(canonical_json(approval))
    effective_controls = json.loads(canonical_json(effective_controls))
    controls = approval["controls"]
    bound = adapter.BatchOperatingBound(
        evaluation_id=approval["evaluation_id"],
        provider=controls["provider"], model=controls["model"], effort=controls["effort"],
    )
    decision = adapter.decide_batch(
        jobs, batching_requested=batching_requested, operating_bound=bound
    )
    reasons = list(decision.reason_codes)
    if effective_controls != controls:
        reasons.append("effective_controls_outside_approval")
    for field in ("policy_boundary", "data_boundary"):
        if any(getattr(job, field) != approval[field] for job in jobs):
            reasons.append(f"{field}_outside_approval")
    if any(
        approval["candidate_payload_sha256"].get(job.candidate_id) != job.payload_sha256
        for job in jobs
    ):
        reasons.append("candidate_outside_approval")
    if any(
        tuple(approval["candidate_claim_ids"].get(job.candidate_id, ())) != job.claim_ids
        for job in jobs
    ):
        reasons.append("claims_outside_approval")
    if reasons:
        return {"status": "direct", "reason_codes": reasons, "transport_calls": 0}
    if not authority_check():
        raise adapter.CriticBatchAdapterError("assignments are not authorized")
    envelope = adapter.build_envelope(decision, jobs, dict(payloads))
    prompt = _prompt(envelope)
    if len(prompt.encode("utf-8")) > approval["maximum_prompt_bytes"]:
        return {"status": "direct", "reason_codes": ["prompt_budget"], "transport_calls": 0}

    # A fresh directory is the attempt identity; evidence is never overwritten.
    output_dir.mkdir(parents=True, exist_ok=False)
    request = {
        "schema_version": 1, "attempt_id": output_dir.name,
        "approval_sha256": _sha(canonical_json(approval)),
        "effective_controls": effective_controls,
        "decision": asdict(decision), "jobs": [asdict(job) for job in jobs],
        "envelope": envelope, "prompt_sha256": _sha(prompt), "created_at": utc_now(),
        "execution_mode": approval["execution_mode"], "usage_source": approval["usage_source"],
        "assignment_refs": [f"synthetic-assignment:{job.candidate_id}" for job in jobs],
    }
    (output_dir / "request.json").write_text(canonical_json(request) + "\n", encoding="utf-8")
    (output_dir / "prompt.txt").write_text(prompt, encoding="utf-8", newline="")
    started = perf_counter()
    disposition: dict[str, Any] = {
        "schema_version": 1, "attempt_id": output_dir.name, "status": "rejected",
        "batch_id": decision.batch_id, "transport_calls": 0, "authority_changed": False,
        "execution_mode": approval["execution_mode"], "usage_source": approval["usage_source"],
        "live_provider_calls": 0,
    }
    try:
        if not authority_check():
            raise adapter.CriticBatchAdapterError("assignments revoked before dispatch")
        disposition["transport_calls"] = 1
        try:
            raw, usage = transport(prompt)
        except Exception as exc:
            raise adapter.CriticBatchAdapterError(f"local transport failed: {exc}") from exc
        (output_dir / "output.json").write_text(raw, encoding="utf-8", newline="")
        (output_dir / "usage.json").write_text(canonical_json(usage) + "\n", encoding="utf-8")
        if len(raw.encode("utf-8")) > approval["maximum_output_bytes"]:
            raise adapter.CriticBatchAdapterError("response exceeds output budget")
        response = _decode_response(raw)
        receipt = adapter.validate_response(decision, jobs, response, aggregate_usage=usage)
        disposition["request_sha256"] = _sha(canonical_json(request))
        disposition["prompt_sha256"] = _sha(prompt)
        disposition["raw_output_sha256"] = _sha(raw)
        (output_dir / "receipt.json").write_text(canonical_json(receipt) + "\n", encoding="utf-8")
        disposition["status"] = "validated"
    except (adapter.CriticBatchAdapterError, ValueError) as exc:
        disposition["error"] = str(exc)
    finally:
        disposition["elapsed_ms"] = round((perf_counter() - started) * 1000, 3)
        disposition["completed_at"] = utc_now()
        (output_dir / "disposition.json").write_text(
            canonical_json(disposition) + "\n", encoding="utf-8"
        )
    return disposition


def project_usage(native: dict[str, Any]) -> dict[str, int]:
    """Keep only reported counters; absent/None values never become zero."""
    from torc.experiment_usage import TOKEN_FIELDS
    return {key: value for key, value in native.items()
            if key in TOKEN_FIELDS and type(value) is int}


class OwnerLedger:
    """In-process execution-owner stand-in for this recorded replay only.

    Production callers must supply an owner-controlled durable reader. This
    object demonstrates the interface; it is not a security boundary, provider
    attestation, or durable accounting service.
    """

    def __init__(self) -> None:
        self._records: dict[str, dict | None] = {}

    def wrap(self, attempt_id: str, transport: Callable) -> Callable:
        def capture(prompt: str) -> tuple[str, dict]:
            if attempt_id in self._records:
                raise adapter.CriticBatchAdapterError("duplicate owner record")
            self._records[attempt_id] = None
            raw, native_usage = transport(prompt)
            usage = json.loads(canonical_json(native_usage))
            self._records[attempt_id] = {
                "attempt_id": attempt_id, "prompt_sha256": _sha(prompt),
                "raw_output_sha256": _sha(raw), "usage": usage,
                "usage_sha256": _sha(canonical_json(usage)),
            }
            return raw, native_usage
        return capture

    def get(self, attempt_id: str) -> dict | None:
        return json.loads(canonical_json(self._records.get(attempt_id)))

    def ids(self) -> list[str]:
        return list(self._records)


def account_attempts(owner: OwnerLedger, root: Path) -> list[dict]:
    """Account all owner attempts, including rejected or lost consumer evidence.

    Status is consumer-written and is not proof of outcome. Missing capture is
    unknown spend, not zero. Each damaged consumer record is isolated.
    """
    rows = []
    for attempt_id in owner.ids():
        captured = owner.get(attempt_id)
        usage = None if captured is None else project_usage(captured["usage"])
        row = {"attempt_id": attempt_id, "usage": usage, "status": None, "issues": []}
        issues = row["issues"]
        if captured is None:
            issues.append("no owner usage")
        elif not {"input_tokens", "output_tokens"} <= usage.keys():
            issues.append("owner usage incomplete")
        directory = root / attempt_id
        if not directory.is_dir():
            issues.append("attempt directory missing")
            rows.append(row)
            continue
        try:
            if not (directory / "disposition.json").exists():
                issues.append("disposition missing")
            else:
                disposition = _object(directory / "disposition.json")
                if not isinstance(disposition.get("status"), str):
                    raise ValueError("missing status")
                row["status"] = disposition["status"]
        except Exception:
            issues.append("attempt record unreadable")
        try:
            consumer_usage = (_object(directory / "usage.json")
                              if (directory / "usage.json").exists() else None)
            if captured is not None and consumer_usage != usage:
                issues.append("usage differs from owner capture")
        except Exception:
            if "attempt record unreadable" not in issues:
                issues.append("attempt record unreadable")
        rows.append(row)
    return rows


def recorded_native_transport(prompt: str) -> tuple[str, dict[str, Any]]:
    """Local stand-in echoes the request ID around already recorded critique evidence."""
    envelope = json.loads(prompt.split("\nREQUEST\n", 1)[1])
    run = EXPERIMENT / "runs" / "critic-claim-link-replication-008" / "01-header-first"
    by_id = {item["candidate_id"]: item for item in _object(run / "output.json")["critiques"]}
    response = {
        "schema_version": 1, "batch_id": envelope["batch_id"],
        "critiques": [by_id[item["candidate_id"]] for item in envelope["candidates"]],
    }
    counters = _object(run / "phase" / "worker-run.json")["usage"]
    return canonical_json(response), counters


def recorded_transport(prompt: str) -> tuple[str, dict[str, int]]:
    raw, native_usage = recorded_native_transport(prompt)
    return raw, project_usage(native_usage)


def link_smoke_to_lineage(
    output_dir: Path,
    state_dir: Path,
    jobs: tuple[adapter.CriticJob, ...],
    approval: dict[str, Any],
    *,
    owner: OwnerLedger | None = None,
) -> dict[str, Any]:
    """Exercise the ordinary authorized checkpoint on a fresh deterministic demo store."""
    disposition = _object(output_dir / "disposition.json")
    request = _object(output_dir / "request.json")
    prompt = (output_dir / "prompt.txt").read_bytes().decode("utf-8")
    raw_output = (output_dir / "output.json").read_bytes().decode("utf-8")
    response = _decode_response(raw_output)
    receipt = _object(output_dir / "receipt.json")
    usage = _object(output_dir / "usage.json")
    controls = approval["controls"]
    decision = adapter.decide_batch(
        jobs, batching_requested=True,
        operating_bound=adapter.BatchOperatingBound(
            evaluation_id=approval["evaluation_id"], provider=controls["provider"],
            model=controls["model"], effort=controls["effort"],
        ),
    )
    if (
        disposition.get("status") != "validated"
        or disposition.get("batch_id") != decision.batch_id
        or disposition.get("attempt_id") != output_dir.name
        or request.get("attempt_id") != output_dir.name
        or disposition.get("request_sha256") != _sha(canonical_json(request))
        or disposition.get("prompt_sha256") != _sha(prompt)
        or request.get("prompt_sha256") != _sha(prompt)
        or disposition.get("raw_output_sha256") != _sha(raw_output)
        or request.get("approval_sha256") != _sha(canonical_json(approval))
        or request.get("effective_controls") != controls
        or disposition.get("execution_mode") != approval["execution_mode"]
        or disposition.get("usage_source") != approval["usage_source"]
        or request.get("execution_mode") != approval["execution_mode"]
        or request.get("usage_source") != approval["usage_source"]
        or canonical_json(request.get("jobs")) != canonical_json([asdict(job) for job in jobs])
        or canonical_json(request.get("decision")) != canonical_json(asdict(decision))
    ):
        raise adapter.CriticBatchAdapterError("persisted attempt binding drifted")
    envelope = request["envelope"]
    verified_envelope = adapter.build_envelope(
        decision, jobs,
        {item["candidate_id"]: item["payload"] for item in envelope["candidates"]},
    )
    if envelope != verified_envelope or prompt != _prompt(verified_envelope):
        raise adapter.CriticBatchAdapterError("persisted request payloads drifted")
    if receipt != adapter.validate_response(
        decision, jobs, response, aggregate_usage=usage
    ):
        raise adapter.CriticBatchAdapterError("persisted receipt drifted")
    capture = None if owner is None else owner.get(output_dir.name)
    if capture is None:
        raise adapter.CriticBatchAdapterError("owner usage capture is required")
    if (capture.get("attempt_id") != output_dir.name
            or capture.get("prompt_sha256") != _sha(prompt)
            or capture.get("raw_output_sha256") != _sha(raw_output)
            or capture.get("usage_sha256") != _sha(canonical_json(capture.get("usage")))
            or project_usage(capture["usage"]) != usage
            or usage != receipt["aggregate_usage"]):
        raise adapter.CriticBatchAdapterError("owner usage binding drifted")
    if len(raw_output.encode("utf-8")) > approval["maximum_output_bytes"]:
        raise adapter.CriticBatchAdapterError("response exceeds output budget")
    run_demo(state_dir)
    with Store(state_dir) as store:
        before = store.current_authority("demo-lineage")
        transitions = store.connection.execute(
            "SELECT COUNT(*) FROM authority_transitions"
        ).fetchone()[0]
        linked = link_batch_evidence(
            store, lineage_id="demo-lineage", activation_id=before["activation_id"],
            decision=decision, jobs=jobs, receipt=receipt, response=response,
            evidence_context={**{key: disposition[key] for key in (
                "execution_mode", "usage_source", "attempt_id", "request_sha256",
                "prompt_sha256", "raw_output_sha256",
            )}, "owner_usage_sha256": capture["usage_sha256"]},
        )
        after = store.current_authority("demo-lineage")
        verification = verify_store(store, "demo-lineage")
        current_transitions = store.connection.execute(
            "SELECT COUNT(*) FROM authority_transitions"
        ).fetchone()[0]
        if (
            not verification["valid"] or transitions != current_transitions
            or before["activation_id"] != after["activation_id"]
            or before["lease_id"] != after["lease_id"]
        ):
            raise adapter.CriticBatchAdapterError("batch checkpoint did not preserve authority")
        return {
            "checkpoint_revision_id": linked["checkpoint"]["revision_id"],
            "lease_holder_before": before["activation_id"],
            "lease_holder_after": after["activation_id"],
            "lease_id": after["lease_id"], "authority_transitions_added": 0,
            "evidence_artifact_ids": [item["artifact_id"] for item in linked["artifacts"]],
            "verification": verification,
        }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--state-dir", type=Path)
    parser.add_argument(
        "--order", choices=("header-first", "cutover-first"), default="header-first"
    )
    args = parser.parse_args(argv)
    try:
        approval = load_approval()
        jobs, payloads = load_pair(args.order)
        owner = OwnerLedger()
        captured_transport = owner.wrap(args.output_dir.name, recorded_native_transport)

        def transport(prompt: str) -> tuple[str, dict[str, int]]:
            raw, native_usage = captured_transport(prompt)
            return raw, project_usage(native_usage)

        result = consume_pair(
            jobs, payloads, output_dir=args.output_dir, approval=approval,
            effective_controls=approval["controls"], batching_requested=True,
            authority_check=lambda: True, transport=transport,
        )
        result["execution_mode"] = "model-free-recorded-replay"
        result["live_provider_calls"] = 0
        result["usage_source"] = "recorded-provider-usage"
        if result["status"] == "validated" and args.state_dir is not None:
            result["lineage"] = link_smoke_to_lineage(
                args.output_dir, args.state_dir, jobs, approval, owner=owner,
            )
        result["accounting"] = account_attempts(owner, args.output_dir.parent)
        print(canonical_json(result))
        return 0 if result["status"] == "validated" else 1
    except (adapter.CriticBatchAdapterError, OSError, ValueError, TorcError) as exc:
        print(canonical_json({"status": "error", "error": str(exc)}), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
