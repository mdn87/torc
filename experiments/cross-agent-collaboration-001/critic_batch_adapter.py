"""Provider-neutral reference policy for safe two-job critic batching."""

from __future__ import annotations

import hashlib
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from torc.canonical import canonical_json  # noqa: E402


class CriticBatchAdapterError(RuntimeError):
    """Raised when an adapter request or response fails closed."""


@dataclass(frozen=True)
class CriticJob:
    """Execution-layer facts needed to decide whether one critique may batch."""

    candidate_id: str
    payload_sha256: str
    claim_ids: tuple[str, ...]
    provider: str
    model: str
    effort: str
    policy_boundary: str
    data_boundary: str
    output_contract: str = "compact-claim-link-v1"
    access_mode: str = "read_only"
    tool_mode: str = "none"
    dependency_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        scalar_values = {
            "candidate_id": self.candidate_id,
            "provider": self.provider,
            "model": self.model,
            "effort": self.effort,
            "policy_boundary": self.policy_boundary,
            "data_boundary": self.data_boundary,
            "output_contract": self.output_contract,
            "access_mode": self.access_mode,
            "tool_mode": self.tool_mode,
        }
        for name, value in scalar_values.items():
            if not value or value.strip() != value:
                raise CriticBatchAdapterError(f"invalid job field: {name}")
        if len(self.payload_sha256) != 64 or any(
            character not in "0123456789abcdef" for character in self.payload_sha256
        ):
            raise CriticBatchAdapterError("payload hash must be lowercase SHA-256")
        if not self.claim_ids or len(self.claim_ids) != len(set(self.claim_ids)):
            raise CriticBatchAdapterError("claim IDs must be non-empty and unique")
        if any(not value or value.strip() != value for value in self.claim_ids):
            raise CriticBatchAdapterError("claim ID is invalid")
        if len(self.dependency_ids) != len(set(self.dependency_ids)):
            raise CriticBatchAdapterError("dependency IDs must be unique")


@dataclass(frozen=True)
class BatchOperatingBound:
    """One externally configured model combination earned by an evaluation."""

    evaluation_id: str
    provider: str
    model: str
    effort: str
    output_contract: str = "compact-claim-link-v1"
    maximum_batch_size: int = 2

    def __post_init__(self) -> None:
        values = (
            self.evaluation_id,
            self.provider,
            self.model,
            self.effort,
            self.output_contract,
        )
        if any(not value or value.strip() != value for value in values):
            raise CriticBatchAdapterError("operating bound contains an invalid field")
        if self.maximum_batch_size != 2:
            raise CriticBatchAdapterError("only evaluated batch size two is supported")


@dataclass(frozen=True)
class BatchDecision:
    """A derived execution decision; never canonical lineage authority."""

    mode: str
    reason_codes: tuple[str, ...]
    ordered_candidate_ids: tuple[str, ...]
    batch_id: str | None


_MATCHED_FIELDS = (
    "provider",
    "model",
    "effort",
    "policy_boundary",
    "data_boundary",
    "output_contract",
)


def decide_batch(
    jobs: tuple[CriticJob, ...],
    *,
    batching_requested: bool,
    operating_bound: BatchOperatingBound,
) -> BatchDecision:
    """Choose a two-job batch only inside the experimentally supported bound."""
    candidate_ids = tuple(job.candidate_id for job in jobs)
    reasons: list[str] = []
    if not batching_requested:
        reasons.append("batching_not_requested")
    if len(jobs) != 2:
        reasons.append("batch_size_not_two")
    if len(candidate_ids) != len(set(candidate_ids)):
        reasons.append("candidate_identity_not_unique")
    if any(job.access_mode != "read_only" for job in jobs):
        reasons.append("mutable_work")
    if any(job.tool_mode != "none" for job in jobs):
        reasons.append("tools_enabled")
    if any(job.dependency_ids for job in jobs):
        reasons.append("dependencies_present")
    for field in _MATCHED_FIELDS:
        if len({getattr(job, field) for job in jobs}) > 1:
            reasons.append(f"mixed_{field}")
    for field in ("provider", "model", "effort", "output_contract"):
        if any(getattr(job, field) != getattr(operating_bound, field) for job in jobs):
            reasons.append(f"{field}_outside_operating_bound")
    if reasons:
        return BatchDecision(
            mode="direct",
            reason_codes=tuple(reasons),
            ordered_candidate_ids=candidate_ids,
            batch_id=None,
        )
    identity = {
        "schema_version": 1,
        "ordered_candidates": [
            {
                "candidate_id": job.candidate_id,
                "payload_sha256": job.payload_sha256,
                "claim_ids": list(job.claim_ids),
            }
            for job in jobs
        ],
        "controls": {field: getattr(jobs[0], field) for field in _MATCHED_FIELDS},
        "operating_bound": {
            "evaluation_id": operating_bound.evaluation_id,
            "maximum_batch_size": operating_bound.maximum_batch_size,
        },
    }
    digest = hashlib.sha256(canonical_json(identity).encode("utf-8")).hexdigest()
    return BatchDecision(
        mode="batch",
        reason_codes=(),
        ordered_candidate_ids=candidate_ids,
        batch_id=f"critic-batch-{digest}",
    )


def build_envelope(
    decision: BatchDecision,
    jobs: tuple[CriticJob, ...],
    payloads: dict[str, str],
) -> dict[str, Any]:
    """Bind verified payloads and claim identities to an eligible decision."""
    if decision.mode != "batch" or decision.batch_id is None:
        raise CriticBatchAdapterError("direct decisions cannot build a batch envelope")
    if tuple(job.candidate_id for job in jobs) != decision.ordered_candidate_ids:
        raise CriticBatchAdapterError("job order does not match the decision")
    if set(payloads) != set(decision.ordered_candidate_ids):
        raise CriticBatchAdapterError("payload membership does not match the decision")
    candidates = []
    for job in jobs:
        payload = payloads[job.candidate_id]
        observed = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        if observed != job.payload_sha256:
            raise CriticBatchAdapterError(f"payload hash drifted: {job.candidate_id}")
        candidates.append(
            {
                "candidate_id": job.candidate_id,
                "payload_sha256": observed,
                "claim_ids": list(job.claim_ids),
                "payload": payload,
            }
        )
    return {
        "schema_version": 1,
        "batch_id": decision.batch_id,
        "output_contract": jobs[0].output_contract,
        "candidates": candidates,
    }


def _validate_usage(usage: dict[str, Any]) -> dict[str, int]:
    if not isinstance(usage, dict) or "input_tokens" not in usage or "output_tokens" not in usage:
        raise CriticBatchAdapterError("aggregate provider usage is incomplete")
    if any("candidate" in key or key.startswith("per_") for key in usage):
        raise CriticBatchAdapterError("per-candidate usage must not be manufactured")
    validated = {}
    for key, value in usage.items():
        if not isinstance(key, str) or not isinstance(value, int) or value < 0:
            raise CriticBatchAdapterError("provider usage values must be non-negative integers")
        validated[key] = value
    return validated


def validate_response(
    decision: BatchDecision,
    jobs: tuple[CriticJob, ...],
    response: dict[str, Any],
    *,
    aggregate_usage: dict[str, Any],
) -> dict[str, Any]:
    """Fail closed on identity, coverage, or finding-link attribution drift."""
    if decision.mode != "batch" or decision.batch_id is None:
        raise CriticBatchAdapterError("response validation requires a batch decision")
    if set(response) != {"schema_version", "batch_id", "critiques"}:
        raise CriticBatchAdapterError("response envelope is invalid")
    if response["schema_version"] != 1 or response["batch_id"] != decision.batch_id:
        raise CriticBatchAdapterError("response batch identity drifted")
    critiques = response["critiques"]
    if not isinstance(critiques, list) or len(critiques) != len(jobs):
        raise CriticBatchAdapterError("response critique count is invalid")
    if [item.get("candidate_id") for item in critiques if isinstance(item, dict)] != list(
        decision.ordered_candidate_ids
    ):
        raise CriticBatchAdapterError("response candidate order drifted")

    candidate_receipts = []
    for job, item in zip(jobs, critiques, strict=True):
        if not isinstance(item, dict) or set(item) != {
            "candidate_id",
            "claim_links",
            "result",
        }:
            raise CriticBatchAdapterError("critique envelope is invalid")
        links = item["claim_links"]
        result = item["result"]
        if not isinstance(links, dict) or set(links) != set(job.claim_ids):
            raise CriticBatchAdapterError("claim-link coverage drifted")
        if not isinstance(result, dict) or set(result) != {
            "schema_version",
            "verdict",
            "findings",
        }:
            raise CriticBatchAdapterError("nested result is invalid")
        if result["schema_version"] != 1 or result["verdict"] not in {
            "approve",
            "changes_requested",
        }:
            raise CriticBatchAdapterError("nested result header is invalid")
        findings = result["findings"]
        if not isinstance(findings, list):
            raise CriticBatchAdapterError("findings must be a list")
        finding_by_id: dict[str, dict[str, Any]] = {}
        for finding in findings:
            if not isinstance(finding, dict) or set(finding) != {
                "finding_id",
                "severity",
                "summary",
                "evidence",
                "claim_ids",
            }:
                raise CriticBatchAdapterError("finding shape is invalid")
            finding_id = finding["finding_id"]
            claim_ids = finding["claim_ids"]
            if (
                not isinstance(finding_id, str)
                or not finding_id
                or finding_id in finding_by_id
                or finding["severity"] not in {"blocking", "non_blocking"}
                or not isinstance(finding["summary"], str)
                or not finding["summary"]
                or not isinstance(finding["evidence"], str)
                or not finding["evidence"]
                or not isinstance(claim_ids, list)
                or not claim_ids
                or not set(claim_ids) <= set(job.claim_ids)
            ):
                raise CriticBatchAdapterError("finding content is invalid")
            finding_by_id[finding_id] = finding
        linked: set[str] = set()
        statuses = {}
        for claim_id in job.claim_ids:
            finding_ids = links[claim_id]
            if (
                not isinstance(finding_ids, list)
                or len(finding_ids) != len(set(finding_ids))
                or any(not isinstance(value, str) or not value for value in finding_ids)
            ):
                raise CriticBatchAdapterError("claim-link values are invalid")
            for finding_id in finding_ids:
                finding = finding_by_id.get(finding_id)
                if finding is None or claim_id not in finding["claim_ids"]:
                    raise CriticBatchAdapterError("claim link does not match its finding")
                linked.add(finding_id)
            statuses[claim_id] = "unmet" if finding_ids else "met"
        if linked != set(finding_by_id):
            raise CriticBatchAdapterError("response contains an unlinked finding")
        candidate_receipts.append(
            {
                "candidate_id": job.candidate_id,
                "payload_sha256": job.payload_sha256,
                "verdict": result["verdict"],
                "claim_statuses": statuses,
                "finding_count": len(findings),
            }
        )
    usage = _validate_usage(aggregate_usage)
    output_sha256 = hashlib.sha256(canonical_json(response).encode("utf-8")).hexdigest()
    return {
        "schema_version": 1,
        "batch_id": decision.batch_id,
        "status": "validated",
        "output_sha256": output_sha256,
        "ordered_candidate_ids": list(decision.ordered_candidate_ids),
        "candidate_receipts": candidate_receipts,
        "aggregate_usage": usage,
        "authority_changed": False,
    }
