"""Link execution-owned batch evidence through existing TORC checkpoint APIs.

This experiment helper performs no inference or dispatch. Receipt validation is
structural evidence validation, not approval of the candidate or its findings.
Artifact IDs use TORC's UUID scheme; the stored byte hashes and sealed records
retain the full receipt and response without promoting either to canonical state.
"""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from critic_batch_adapter import BatchDecision, CriticJob, validate_response

from torc.canonical import canonical_json, seal_record, utc_now
from torc.errors import IntegrityError, InvalidInputError, LeaseConflictError
from torc.ids import new_id
from torc.store import Store
from torc.verify import artifact_metadata, verify_store


def link_batch_evidence(
    store: Store,
    *,
    lineage_id: str,
    activation_id: str,
    decision: BatchDecision,
    jobs: tuple[CriticJob, ...],
    receipt: dict[str, Any],
    response: dict[str, Any],
    evidence_context: dict[str, Any] | None = None,
    revision_id: str | None = None,
    created_at: str | None = None,
) -> dict[str, Any]:
    """Preserve a validated batch as two artifact refs in an ordinary checkpoint.

The current authority is checked before exporting and by ``append_revision``
before advancing the head. Exported artifacts precede the checkpoint and may
remain unlinked if a subsequent append fails; no lease or handoff is created.
"""
    authority = store.current_authority(lineage_id)
    if authority["activation_id"] != activation_id:
        raise LeaseConflictError("activation does not hold the authoritative lease")
    verification = verify_store(store, lineage_id)
    if not verification["valid"]:
        first = verification["errors"][0]
        raise IntegrityError(
            f"lineage integrity failed: {first['code']} ({first['record_id']})"
        )
    if not isinstance(receipt, dict):
        raise InvalidInputError("batch receipt must be an object")
    expected = validate_response(
        decision, jobs, response, aggregate_usage=receipt.get("aggregate_usage")
    )
    if receipt != expected:
        raise InvalidInputError("batch receipt does not match its validated response")
    if evidence_context is not None and not isinstance(evidence_context, dict):
        raise InvalidInputError("batch evidence context must be an object")

    created_at = created_at or utc_now()
    source = store.get_revision(authority["lineage_head_revision_id"])
    exports = []
    for kind, evidence in (("critic-batch-receipt", receipt), ("critic-batch-response", response)):
        artifact_id = new_id("artifact")
        relative_path = f"artifacts/{artifact_id}.json"
        record = {
            "schema_version": 1,
            "record_kind": kind,
            "artifact_id": artifact_id,
            "lineage_id": lineage_id,
            "activation_id": activation_id,
            "source_revision_id": source["revision_id"],
            "batch_id": decision.batch_id,
            "created_at": created_at,
            "evidence": evidence,
        }
        if evidence_context is not None:
            record["evidence_context"] = deepcopy(evidence_context)
        record = seal_record(record)
        path = store.state_dir / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("x", encoding="utf-8", newline="\n") as handle:
            handle.write(canonical_json(record) + "\n")
        exports.append(
            artifact_metadata(
                store,
                artifact_id=artifact_id,
                record_kind=kind,
                record_id=decision.batch_id,
                relative_path=relative_path,
                created_at=created_at,
            )
        )

    artifact_ids = [item["artifact_id"] for item in exports]
    canonical_state = deepcopy(source["canonical_state"])
    canonical_state["artifact_refs"] = canonical_state.get("artifact_refs", []) + artifact_ids
    with store.transaction(immediate=True):
        if store.current_authority(lineage_id) != authority:
            raise LeaseConflictError("lineage head or authority changed before evidence checkpoint")
        checkpoint = store.append_revision(
            lineage_id,
            canonical_state,
            event_type="checkpoint",
            activation_id=activation_id,
            evidence_refs=artifact_ids,
            revision_id=revision_id,
            created_at=created_at,
        )
    return {"checkpoint": checkpoint, "artifacts": exports}
