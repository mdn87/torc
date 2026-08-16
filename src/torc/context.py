"""Same-activation runtime binding, checkpoint, and read-only hydration."""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Any, Protocol

from .canonical import canonical_json, record_hash_is_valid, utc_now
from .errors import IntegrityError, LeaseConflictError, NotFoundError, TorcError
from .ids import new_id
from .ogmi_adapter import OgmiAdapter, OgmiAdapterError
from .operator import checkpoint_operator_lineage
from .projections import compile_projection
from .store import Store
from .verify import verify_store

HYDRATION_OUTPUT_LIMIT = 65_536
_MODES = {"ogmi_workgraph", "torc_standalone"}


class ContextError(TorcError):
    """A runtime continuity binding or refresh is invalid."""


class StaleContextError(ContextError):
    """A once-valid binding no longer matches current activation authority."""


class _OgmiResolver(Protocol):
    def resolve(self, **kwargs: object) -> dict[str, Any]: ...


def attach_context(
    store: Store,
    *,
    harness: str,
    repository_identity: str,
    runtime_session_ref: str,
    lineage_id: str,
    activation_id: str,
    continuity_mode: str,
    ogmi_project_path: Path | str | None = None,
    ogmi_run_id: str | None = None,
    ogmi_assignment_id: str | None = None,
    ogmi_orientation_spine_id: str | None = None,
    ogmi_checkpoint_path: Path | str | None = None,
    ogmi: _OgmiResolver | None = None,
) -> dict[str, Any]:
    """Bind one exact external runtime to an existing authoritative activation."""

    _require_external_identity("harness", harness)
    _require_external_identity("repository identity", repository_identity)
    _require_external_identity("runtime session reference", runtime_session_ref)
    if continuity_mode not in _MODES:
        raise ContextError(f"unsupported continuity mode: {continuity_mode}")
    authority = store.current_authority(lineage_id)
    activation = store.get_activation(activation_id)
    if authority["activation_id"] != activation_id or activation["state"] != "active":
        raise LeaseConflictError("binding activation does not hold lineage authority")
    if activation["lineage_id"] != lineage_id:
        raise ContextError("binding activation belongs to another lineage")

    ogmi_fields = (
        ogmi_project_path,
        ogmi_run_id,
        ogmi_assignment_id,
        ogmi_orientation_spine_id,
        ogmi_checkpoint_path,
    )
    resolved: dict[str, Any] | None = None
    if continuity_mode == "ogmi_workgraph":
        if any(value is None for value in ogmi_fields):
            raise ContextError(
                "ogmi_workgraph requires project, run, assignment, spine, and checkpoint"
            )
        assert ogmi_project_path is not None
        assert ogmi_run_id is not None
        assert ogmi_assignment_id is not None
        assert ogmi_orientation_spine_id is not None
        assert ogmi_checkpoint_path is not None
        resolved = (ogmi or OgmiAdapter()).resolve(
            checkpoint_path=ogmi_checkpoint_path,
            project_path=ogmi_project_path,
            orientation_spine_id=ogmi_orientation_spine_id,
            expected_run_id=ogmi_run_id,
            expected_assignment_id=ogmi_assignment_id,
        )
    elif any(value is not None for value in ogmi_fields):
        raise ContextError("torc_standalone cannot attach synthetic OGMI fields")

    binding = {
        "binding_id": new_id("binding"),
        "harness": harness,
        "repository_identity": repository_identity,
        "runtime_session_ref": runtime_session_ref,
        "lineage_id": lineage_id,
        "activation_id": activation_id,
        "continuity_mode": continuity_mode,
        "ogmi_project_path": (
            str(Path(ogmi_project_path).resolve()) if ogmi_project_path is not None else None
        ),
        "ogmi_run_id": ogmi_run_id,
        "ogmi_assignment_id": ogmi_assignment_id,
        "ogmi_orientation_spine_id": ogmi_orientation_spine_id,
        "ogmi_checkpoint_id": resolved["checkpoint_id"] if resolved else None,
        "ogmi_checkpoint_path": resolved["checkpoint_path"] if resolved else None,
        "ogmi_checkpoint_sha256": resolved["checkpoint_sha256"] if resolved else None,
        "source_revision_id": None,
        "projection_id": None,
        "created_at": utc_now(),
    }
    try:
        return store.create_context_binding(binding)
    except sqlite3.IntegrityError as exc:
        if "UNIQUE constraint failed" in str(exc):
            raise ContextError("runtime session is already bound") from exc
        raise ContextError("context binding violates the durable contract") from exc


def checkpoint_context(
    store: Store,
    *,
    harness: str,
    repository_identity: str,
    runtime_session_ref: str,
    canonical_state: dict[str, Any],
    budget_limit: int,
    evidence_refs: list[str] | None = None,
    ogmi: _OgmiResolver | None = None,
) -> dict[str, Any]:
    """Append exactly one canonical revision and compile its same-substrate view."""

    binding = _exact_binding(
        store,
        harness=harness,
        repository_identity=repository_identity,
        runtime_session_ref=runtime_session_ref,
    )
    authority = _require_current_binding(store, binding)
    resolved = _resolve_bound_ogmi(binding, ogmi) if _is_ogmi(binding) else None
    refs = list(evidence_refs or [])
    if resolved is not None:
        refs.append("ogmi-checkpoint:sha256:" + resolved["checkpoint_sha256"])
    refs = list(dict.fromkeys(refs))

    with store.transaction(immediate=True):
        current = _require_current_binding(store, binding)
        if current != authority:
            raise LeaseConflictError("authority changed before context checkpoint")
        result = checkpoint_operator_lineage(
            store,
            lineage_id=binding["lineage_id"],
            activation_id=binding["activation_id"],
            canonical_state=canonical_state,
            event_type="checkpoint",
            evidence_refs=refs,
        )
        projection = compile_projection(
            store,
            lineage_id=binding["lineage_id"],
            source_revision_id=result["revision_id"],
            target_substrate_id=current["substrate_id"],
            budget_limit=budget_limit,
            handoff_reason="context_degradation",
            target_responsibility="Continue the bound runtime session from structured state",
        )
        store.update_context_checkpoint(
            binding["binding_id"],
            source_revision_id=result["revision_id"],
            projection_id=projection["projection_id"],
        )
    return {
        **result,
        "projection_id": projection["projection_id"],
        "continuity_mode": binding["continuity_mode"],
    }


def detach_context(
    store: Store,
    *,
    harness: str,
    repository_identity: str,
    runtime_session_ref: str,
) -> dict[str, Any]:
    """Retire one exact adapter binding without touching lineage authority."""

    try:
        binding = store.delete_context_binding(
            harness, runtime_session_ref, repository_identity
        )
    except NotFoundError as exc:
        raise ContextError("exact runtime context binding not found") from exc
    return {
        "schema_version": 1,
        "status": "detached",
        "binding_id": binding["binding_id"],
        "harness": binding["harness"],
        "repository_identity": binding["repository_identity"],
        "runtime_session_ref": binding["runtime_session_ref"],
        "lineage_id": binding["lineage_id"],
        "activation_id": binding["activation_id"],
        "continuity_mode": binding["continuity_mode"],
    }


def hydrate_context(
    store: Store,
    *,
    harness: str,
    repository_identity: str,
    runtime_session_ref: str,
    ogmi: _OgmiResolver | None = None,
) -> dict[str, Any]:
    """Return a bounded derived view without mutating TORC or OGMI."""

    try:
        binding = store.get_context_binding(
            harness, runtime_session_ref, repository_identity
        )
    except NotFoundError:
        status = (
            "stale"
            if store.context_bindings_for_session(harness, runtime_session_ref)
            else "unbound"
        )
        detail = (
            "Runtime session is bound to a different repository identity."
            if status == "stale"
            else "No exact runtime context binding exists."
        )
        return _not_ready(status, detail)

    try:
        authority = _require_current_binding(store, binding)
        if not binding["source_revision_id"] or not binding["projection_id"]:
            return _not_ready("stale", "The binding has no completed context checkpoint.")
        if authority["lineage_head_revision_id"] != binding["source_revision_id"]:
            return _not_ready("stale", "The binding does not reference the lineage head.")
        verification = verify_store(store, binding["lineage_id"])
        if not verification["valid"]:
            raise IntegrityError("TORC provenance verification failed")
        projection = store.get_hashed_record(
            "projections", "projection_id", binding["projection_id"]
        )
        if not record_hash_is_valid(projection):
            raise IntegrityError("stored context projection failed its hash check")
        if (
            projection["lineage_id"] != binding["lineage_id"]
            or projection["source_revision_id"] != binding["source_revision_id"]
            or projection["target_substrate_id"] != authority["substrate_id"]
        ):
            raise IntegrityError("stored context projection provenance does not match binding")

        if _is_ogmi(binding):
            resolved = _resolve_bound_ogmi(binding, ogmi)
            continuity = {
                "mode": "ogmi_workgraph",
                "checkpoint_id": binding["ogmi_checkpoint_id"],
                "checkpoint_sha256": binding["ogmi_checkpoint_sha256"],
                "orientation_spine_id": binding["ogmi_orientation_spine_id"],
                "run_id": binding["ogmi_run_id"],
                "assignment_id": binding["ogmi_assignment_id"],
            }
            view = {
                "label": "prior structured continuity state",
                "precedence": "Current instructions and repository evidence take precedence.",
                "torc_projection": projection,
                "ogmi_checkpoint": resolved["checkpoint"],
                "ogmi_orientation": resolved["orientation"],
            }
        else:
            continuity = {
                "mode": "torc_standalone",
                "limitation": "No shared OGMI workgraph checkpoint is attached.",
            }
            view = {
                "label": "prior standalone Torc structured state",
                "precedence": "Current instructions and repository evidence take precedence.",
                "torc_projection": projection,
            }
        additional_context = canonical_json(view)
        if len(additional_context.encode("utf-8")) > HYDRATION_OUTPUT_LIMIT:
            raise ContextError("hydration output exceeds the fixed size limit")
    except StaleContextError as exc:
        return _not_ready("stale", str(exc))
    except (
        ContextError,
        IntegrityError,
        LeaseConflictError,
        NotFoundError,
        OgmiAdapterError,
    ) as exc:
        return _not_ready("invalid", str(exc))

    return {
        "schema_version": 1,
        "status": "ready",
        "lineage_id": binding["lineage_id"],
        "activation_id": binding["activation_id"],
        "source_revision_id": binding["source_revision_id"],
        "projection_id": binding["projection_id"],
        "continuity": continuity,
        "additional_context": additional_context,
    }


def _exact_binding(
    store: Store,
    *,
    harness: str,
    repository_identity: str,
    runtime_session_ref: str,
) -> dict[str, Any]:
    try:
        return store.get_context_binding(
            harness, runtime_session_ref, repository_identity
        )
    except NotFoundError as exc:
        raise ContextError("exact runtime context binding not found") from exc


def _require_current_binding(
    store: Store, binding: dict[str, Any]
) -> dict[str, Any]:
    activation = store.get_activation(binding["activation_id"])
    if activation["lineage_id"] != binding["lineage_id"]:
        raise ContextError("binding activation belongs to another lineage")
    if activation["state"] != "active":
        raise StaleContextError("binding activation is no longer active")
    try:
        authority = store.current_authority(binding["lineage_id"])
    except LeaseConflictError as exc:
        raise StaleContextError("binding lineage no longer has an active lease") from exc
    if authority["activation_id"] != binding["activation_id"]:
        raise StaleContextError("binding activation no longer holds the lease")
    return authority


def _resolve_bound_ogmi(
    binding: dict[str, Any], ogmi: _OgmiResolver | None
) -> dict[str, Any]:
    resolved = (ogmi or OgmiAdapter()).resolve(
        checkpoint_path=binding["ogmi_checkpoint_path"],
        project_path=binding["ogmi_project_path"],
        orientation_spine_id=binding["ogmi_orientation_spine_id"],
        expected_run_id=binding["ogmi_run_id"],
        expected_assignment_id=binding["ogmi_assignment_id"],
    )
    if (
        resolved["checkpoint_id"] != binding["ogmi_checkpoint_id"]
        or resolved["checkpoint_sha256"] != binding["ogmi_checkpoint_sha256"]
    ):
        raise ContextError("OGMI checkpoint reference changed after binding")
    return resolved


def _is_ogmi(binding: dict[str, Any]) -> bool:
    return binding["continuity_mode"] == "ogmi_workgraph"


def _require_external_identity(label: str, value: str) -> None:
    if not isinstance(value, str) or not value.strip() or len(value) > 2048:
        raise ContextError(f"{label} must be a bounded non-empty string")


def _not_ready(status: str, detail: str) -> dict[str, Any]:
    return {"schema_version": 1, "status": status, "detail": detail[:500]}
