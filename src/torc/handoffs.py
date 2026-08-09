"""Two-stage immutable handoff preparation and resolution."""

from __future__ import annotations

from copy import deepcopy
from datetime import UTC, datetime
from typing import Any

from .canonical import canonical_json, seal_record, utc_now
from .errors import HandoffError, LeaseConflictError
from .ids import new_id, valid_id
from .store import Store
from .vocabulary import HANDOFF_REASON_CODES

CONTINUITY_FIELDS = (
    "lineage_identity",
    "current_responsibility",
    "settled_decisions",
    "active_commitments",
    "hard_constraints",
    "unresolved_work",
    "uncertainties",
    "handoff_reason",
    "source_revision_id",
)


def prepare_handoff(
    store: Store,
    *,
    lineage_id: str,
    source_activation_id: str,
    fit_decision_id: str,
    projection_id: str,
    reason_code: str,
    rationale: str,
    target_activation_id: str | None = None,
    recovery_context: dict[str, Any] | None = None,
    continuity_requirements: list[str] | None = None,
    handoff_id: str | None = None,
    prepared_at: str | None = None,
) -> dict[str, Any]:
    if reason_code not in HANDOFF_REASON_CODES:
        raise HandoffError(f"unsupported handoff reason: {reason_code}")
    if reason_code == "failure_recovery":
        validate_recovery_context(recovery_context)
    elif recovery_context is not None:
        raise HandoffError("recovery context requires the failure_recovery reason")
    authority = store.current_authority(lineage_id)
    if authority["activation_id"] != source_activation_id:
        raise LeaseConflictError("source activation does not hold lineage authority")
    fit = store.get_hashed_record("fit_decisions", "fit_decision_id", fit_decision_id)
    projection = store.get_hashed_record("projections", "projection_id", projection_id)
    source_revision_id = authority["lineage_head_revision_id"]
    target_substrate_id = fit["selected_substrate_id"]
    if target_substrate_id is None:
        raise HandoffError("fit decision selected no target substrate")
    if (
        fit["lineage_id"] != lineage_id
        or fit["source_revision_id"] != source_revision_id
        or projection["lineage_id"] != lineage_id
        or projection["source_revision_id"] != source_revision_id
        or projection["target_substrate_id"] != target_substrate_id
    ):
        raise HandoffError("fit decision or projection does not match current authority")
    if target_activation_id is not None:
        target = store.get_activation(target_activation_id)
        if (
            target["lineage_id"] != lineage_id
            or target["substrate_id"] != target_substrate_id
            or target["revision_id"] != source_revision_id
        ):
            raise HandoffError("target activation does not match the handoff preparation")

    record = seal_record(
        {
            "schema_version": 1,
            "handoff_id": handoff_id or new_id("handoff"),
            "lineage_id": lineage_id,
            "source_revision_id": source_revision_id,
            "source_activation_id": source_activation_id,
            "source_lease_id": authority["lease_id"],
            "target_substrate_id": target_substrate_id,
            "target_activation_id": target_activation_id,
            "recovery_context": recovery_context,
            "fit_decision_id": fit_decision_id,
            "projection_id": projection_id,
            "reason_code": reason_code,
            "rationale": rationale,
            "continuity_requirements": continuity_requirements
            or list(CONTINUITY_FIELDS),
            "source_authority": {
                "lineage_head_revision_id": source_revision_id,
                "activation_id": source_activation_id,
                "lease_id": authority["lease_id"],
            },
            "prepared_at": prepared_at or utc_now(),
        }
    )
    with store.connection:
        store.connection.execute(
            """INSERT INTO handoffs
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                record["handoff_id"],
                lineage_id,
                source_revision_id,
                source_activation_id,
                authority["lease_id"],
                target_substrate_id,
                fit_decision_id,
                projection_id,
                canonical_json(record),
            ),
        )
    return record


def expected_reconstruction(store: Store, snapshot: dict[str, Any]) -> dict[str, Any]:
    revision = store.get_revision(snapshot["source_revision_id"])
    projection = store.get_hashed_record(
        "projections", "projection_id", snapshot["projection_id"]
    )
    purpose = next(
        item["content"]
        for item in projection["included_sections"]
        if item["section_id"] == "handoff-purpose"
    )
    state = revision["canonical_state"]
    return {
        "lineage_identity": state["identity"]["label"],
        "current_responsibility": purpose["target_responsibility"],
        "settled_decisions": state["self_model"].get("settled_decisions", []),
        "active_commitments": state["commitments"],
        "hard_constraints": state["constraints"],
        "unresolved_work": state["open_work"],
        "uncertainties": state["uncertainties"],
        "handoff_reason": snapshot["reason_code"],
        "source_revision_id": snapshot["source_revision_id"],
        "new_inferences": [],
    }


def resolve_handoff(
    store: Store,
    *,
    handoff_id: str,
    target_activation_id: str,
    reconstruction: dict[str, Any],
    handoff_result_id: str | None = None,
    target_lease_id: str | None = None,
    resulting_revision_id: str | None = None,
    resolved_at: str | None = None,
) -> dict[str, Any]:
    snapshot = store.get_hashed_record("handoffs", "handoff_id", handoff_id)
    if snapshot["reason_code"] == "failure_recovery":
        validate_recovery_context(snapshot.get("recovery_context"))
    existing = store.connection.execute(
        "SELECT 1 FROM handoff_results WHERE handoff_id = ?", (handoff_id,)
    ).fetchone()
    if existing:
        raise HandoffError(f"handoff already resolved: {handoff_id}")
    target = store.get_activation(target_activation_id)
    if (
        target["lineage_id"] != snapshot["lineage_id"]
        or target["substrate_id"] != snapshot["target_substrate_id"]
        or target["revision_id"] != snapshot["source_revision_id"]
        or target["state"] != "pending"
    ):
        raise HandoffError("target activation does not match the handoff snapshot")
    if (
        snapshot.get("target_activation_id") is not None
        and target_activation_id != snapshot["target_activation_id"]
    ):
        raise HandoffError("target activation is not the intended handoff recipient")

    expected = expected_reconstruction(store, snapshot)
    checks = []
    for requirement in snapshot["continuity_requirements"]:
        passed = (
            requirement in expected
            and reconstruction.get(requirement) == expected[requirement]
        )
        checks.append(
            {
                "requirement": requirement,
                "passed": passed,
                "evidence": (
                    "target reconstruction matches frozen canonical continuity"
                    if passed
                    else "target reconstruction differs from frozen canonical continuity"
                ),
            }
        )
    disposition = "accepted" if all(item["passed"] for item in checks) else "rejected"
    result_id = handoff_result_id or new_id("handoff-result")
    resolved_at = resolved_at or utc_now()

    if disposition == "rejected":
        result = seal_record(
            {
                "schema_version": 1,
                "handoff_result_id": result_id,
                "handoff_id": handoff_id,
                "lineage_id": snapshot["lineage_id"],
                "target_activation_id": target_activation_id,
                "reconstruction": reconstruction,
                "checks": checks,
                "disposition": "rejected",
                "rejection_reason": "one or more continuity requirements failed",
                "resulting_authority": None,
                "resolved_at": resolved_at,
            }
        )
        with store.connection:
            store.connection.execute(
                "INSERT INTO handoff_results VALUES (?, ?, ?, ?, 'rejected', ?)",
                (
                    result_id,
                    handoff_id,
                    snapshot["lineage_id"],
                    target_activation_id,
                    canonical_json(result),
                ),
            )
        return result

    revision_id = resulting_revision_id or new_id("revision")
    lease_id = target_lease_id or new_id("lease")
    source_revision = store.get_revision(snapshot["source_revision_id"])
    new_state = deepcopy(source_revision["canonical_state"])
    new_state["self_model"] = deepcopy(new_state["self_model"])
    new_state["self_model"]["role"] = reconstruction["current_responsibility"]
    revision = seal_record(
        {
            "schema_version": 1,
            "lineage_id": snapshot["lineage_id"],
            "revision_id": revision_id,
            "parent_revision_ids": [snapshot["source_revision_id"]],
            "created_at": resolved_at,
            "event_type": "handoff_accepted",
            "actor": {
                "kind": "activation",
                "activation_id": target_activation_id,
                "substrate_id": target["substrate_id"],
            },
            "canonical_state": new_state,
            "evidence_refs": [handoff_id, result_id],
        },
        previous_revision_sha256=source_revision["integrity"][
            "canonical_payload_sha256"
        ],
    )
    result = seal_record(
        {
            "schema_version": 1,
            "handoff_result_id": result_id,
            "handoff_id": handoff_id,
            "lineage_id": snapshot["lineage_id"],
            "target_activation_id": target_activation_id,
            "reconstruction": reconstruction,
            "checks": checks,
            "disposition": "accepted",
            "rejection_reason": None,
            "resulting_authority": {
                "lineage_head_revision_id": revision_id,
                "activation_id": target_activation_id,
                "lease_id": lease_id,
            },
            "resolved_at": resolved_at,
        }
    )

    with store.connection:
        authority = store.current_authority(snapshot["lineage_id"])
        if (
            authority["activation_id"] != snapshot["source_activation_id"]
            or authority["lease_id"] != snapshot["source_lease_id"]
            or authority["lineage_head_revision_id"] != snapshot["source_revision_id"]
        ):
            raise LeaseConflictError("source authority changed after handoff preparation")
        store._insert_revision(revision)
        store.connection.execute(
            "UPDATE lineages SET head_revision_id = ? WHERE lineage_id = ?",
            (revision_id, snapshot["lineage_id"]),
        )
        store.connection.execute(
            "UPDATE leases SET status = 'closed', closed_at = ? WHERE lease_id = ?",
            (resolved_at, snapshot["source_lease_id"]),
        )
        source_state = (
            "failed" if snapshot["reason_code"] == "failure_recovery" else "suspended"
        )
        store.connection.execute(
            "UPDATE activations SET state = ?, ended_at = ? WHERE activation_id = ?",
            (source_state, resolved_at, snapshot["source_activation_id"]),
        )
        store.connection.execute(
            "UPDATE activations SET state = 'active', revision_id = ? WHERE activation_id = ?",
            (revision_id, target_activation_id),
        )
        store.connection.execute(
            "INSERT INTO leases VALUES (?, ?, ?, ?, 'active', ?, NULL)",
            (
                lease_id,
                snapshot["lineage_id"],
                revision_id,
                target_activation_id,
                resolved_at,
            ),
        )
        store.connection.execute(
            "INSERT INTO handoff_results VALUES (?, ?, ?, ?, 'accepted', ?)",
            (
                result_id,
                handoff_id,
                snapshot["lineage_id"],
                target_activation_id,
                canonical_json(result),
            ),
        )
        store.connection.execute(
            """INSERT INTO authority_transitions
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                new_id("transition"),
                snapshot["lineage_id"],
                snapshot["source_activation_id"],
                target_activation_id,
                snapshot["source_lease_id"],
                lease_id,
                handoff_id,
                result_id,
                revision_id,
                resolved_at,
            ),
        )
    return result


def validate_recovery_context(context: dict[str, Any] | None) -> None:
    if not isinstance(context, dict):
        raise HandoffError("failure recovery requires structured recovery context")
    if set(context) != {
        "initiator",
        "failure_kind",
        "observed_at",
        "evidence_refs",
        "target_assignment_ref",
    }:
        raise HandoffError("recovery context fields are invalid")
    initiator = context["initiator"]
    if (
        not isinstance(initiator, dict)
        or set(initiator) != {"kind", "ref"}
        or initiator["kind"] != "operator"
        or not valid_id(initiator["ref"])
    ):
        raise HandoffError("failure recovery must be initiated by the operator")
    if context["failure_kind"] != "activation_unavailable":
        raise HandoffError("unsupported recovery failure kind")
    observed_at = context["observed_at"]
    if not isinstance(observed_at, str) or not observed_at.endswith("Z"):
        raise HandoffError("recovery observation time is required")
    try:
        parsed_observed_at = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
    except ValueError as exc:
        raise HandoffError("recovery observation time must be UTC RFC 3339") from exc
    if parsed_observed_at.tzinfo != UTC:
        raise HandoffError("recovery observation time must be UTC RFC 3339")
    evidence_refs = context["evidence_refs"]
    if (
        not isinstance(evidence_refs, list)
        or not evidence_refs
        or any(not valid_id(item) for item in evidence_refs)
        or len(evidence_refs) != len(set(evidence_refs))
    ):
        raise HandoffError("failure recovery requires unique evidence references")
    if not valid_id(context["target_assignment_ref"]):
        raise HandoffError("failure recovery requires a target assignment reference")
