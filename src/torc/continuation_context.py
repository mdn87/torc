"""Read-only bindings between exact continuation bytes and separate recovery evidence.

Bindings detect substitution, not freshness or permission. Native context bytes
are an opaque owner-supplied handle, never interpreted as portable model state.
Only the capsule helpers verify TORC rendering; generic bindings do not.
"""

from __future__ import annotations

import hashlib
from copy import deepcopy

from . import p5_capsules
from .canonical import canonical_json, payload_sha256
from .store import Store

KINDS = {"torc_capsule", "compiled_prompt", "native_warm", "native_cold"}


def bind_context(report: dict, *, context_kind: str, context_identity: str,
                 context: bytes) -> dict:
    """Pin an independently retained report and exact delivered bytes, without I/O."""
    if context_kind not in KINDS:
        raise ValueError("unsupported context kind")
    if not isinstance(context_identity, str) or not context_identity.strip():
        raise ValueError("context identity required")
    if not isinstance(context, bytes) or not context:
        raise ValueError("nonempty context bytes required")
    if (report.get("schema_version") != "torc.harness_reconciliation.v0"
            or report.get("status") not in {"held", "stale", "observations_complete"}
            or report.get("retry_authorized") is not False
            or report.get("quiescence") != "unknown"
            or not isinstance(report.get("base_bindings"), dict)):
        raise ValueError("unsupported reconciliation report")
    body = {
        "schema_version": "torc.continuation_context.v0",
        "context_kind": context_kind, "context_identity": context_identity,
        "context_sha256": hashlib.sha256(context).hexdigest(),
        "context_byte_length": len(context), "report_sha256": payload_sha256(report),
        "base_bindings": deepcopy(report["base_bindings"]),
        "authority_transferred": False, "retry_authorized": False,
    }
    return {"binding_id": "sha256:" + payload_sha256(body), **body}


def verify_context(binding: dict, report: dict, *, expected_binding_id: str,
                   context_kind: str, context_identity: str, context: bytes,
                   current_bindings: dict) -> dict:
    """Check an external pin and exact pair; preserve stale reports and all holds.

    Current non-TORC observations are caller supplied, not probed here. A result
    says only that these supplied facts match. It never certifies live readiness.
    """
    expected = bind_context(report, context_kind=context_kind,
                            context_identity=context_identity, context=context)
    if (expected["binding_id"] != expected_binding_id
            or canonical_json(binding) != canonical_json(expected)):
        raise ValueError("context binding mismatch")
    stale = not report["base_bindings"] or report["base_bindings"] != current_bindings
    return {
        "binding_id": expected_binding_id,
        "status": "stale" if stale else report["status"],
        "report_sha256": expected["report_sha256"],
        "hold_list": deepcopy(report["hold_list"]),
        "scope_holds": sorted(set(report["scope_holds"])
                              | ({"bindings_stale"} if stale else set())),
        "authority_transferred": False, "retry_authorized": False,
        "quiescence": "unknown",
    }


def _capsule_base(composition: dict, report: dict) -> None:
    base = report["base_bindings"]
    if (base.get("lineage_id") != composition["lineage_id"]
            or base.get("lineage_revision_id") != composition["source_revision_id"]):
        raise ValueError("report and projection base mismatch")


def derive_capsule_context(store: Store, projection_id: str, record_sha256: str,
                          report: dict) -> dict:
    """Reuse the stored carry verbatim; recovery evidence stays outside its budget.

    Delivered capsule bytes are canonical UTF-8 JSON WITHOUT a final newline.
    The identity binds both caller-pinned projection ID and record hash.
    """
    with store.read_transaction():
        capsule, control, composition = p5_capsules.derive(store, projection_id, record_sha256)
        p5_capsules.verify(store, projection_id, record_sha256, capsule, control, composition)
        _capsule_base(composition, report)
        binding = bind_context(
            report, context_kind="torc_capsule",
            context_identity=canonical_json([projection_id, record_sha256]),
            context=canonical_json(capsule).encode("utf-8"),
        )
    return {"capsule": capsule, "control": control, "composition": composition,
            "binding": binding}


def verify_capsule_context(store: Store, projection_id: str, record_sha256: str,
                           bundle: dict, report: dict, *, expected_binding_id: str,
                           delivered_context: bytes, current_bindings: dict) -> dict:
    """Verify faithful rendering and read the actual lineage head in one snapshot."""
    with store.read_transaction():
        p5_capsules.verify(store, projection_id, record_sha256,
                           bundle["capsule"], bundle["control"], bundle["composition"])
        _capsule_base(bundle["composition"], report)
        if delivered_context != canonical_json(bundle["capsule"]).encode("utf-8"):
            raise ValueError("delivered capsule bytes mismatch")
        current = deepcopy(current_bindings)
        lineage_id = bundle["composition"]["lineage_id"]
        lineage = store.get_lineage(lineage_id)
        # The actual store wins even if the caller accidentally reuses an old base.
        current.update(lineage_id=lineage_id, lineage_revision_id=lineage["head_revision_id"])
        return verify_context(
            bundle["binding"], report, expected_binding_id=expected_binding_id,
            context_kind="torc_capsule",
            context_identity=canonical_json([projection_id, record_sha256]),
            context=delivered_context, current_bindings=current,
        )
