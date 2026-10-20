"""Build an exact-prefix manifest from explicit, caller-owned observations."""

from __future__ import annotations

import hashlib
from copy import deepcopy
from datetime import datetime

from torc.canonical import payload_sha256

from .classify import classify, valid_id
from .parser import parse_prefix


def build_capture(
    data: bytes, *, prefix_length: int, session_ref: str, session_incarnation: str,
    observed_at: str, bindings: dict, boundary: str = "interrupted",
    transcript_status: str = "unchanged", writer_state: str = "unconfirmed",
    workspace_available: bool = False, lifecycle_complete: bool = False,
    operation_coverage: str = "unknown", usage_ref: str | None = None,
) -> dict:
    """Caller supplies facts; this pure builder neither stats files nor probes writers.

    ``fixture_complete`` is a synthetic coverage attestation only. Live
    transcripts cannot inherit it. Complete observations never authorize retry.
    Bindings and opaque references are caller-allowlisted metadata, not redacted
    automatically; untrusted transcript content is never copied into them.
    """
    if not valid_id(session_ref) or not valid_id(session_incarnation):
        raise ValueError("invalid session identity")
    if not isinstance(observed_at, str) or not observed_at.endswith("Z"):
        raise ValueError("observed_at must be UTC RFC 3339")
    datetime.fromisoformat(observed_at)
    if not isinstance(bindings, dict):
        raise ValueError("bindings must be an object")
    for value, allowed in [
        (boundary, {"stop", "interrupted", "unknown"}),
        (transcript_status, {"unchanged", "appended", "truncated", "rotated", "unknown"}),
        (writer_state, {"stopped", "unconfirmed"}),
        (operation_coverage, {"unknown", "fixture_complete"}),
    ]:
        if value not in allowed:
            raise ValueError("unsupported capture observation")
    if type(workspace_available) is not bool or type(lifecycle_complete) is not bool:
        raise ValueError("coverage observations must be booleans")
    parsed = parse_prefix(data, prefix_length)
    operations, errors = classify(parsed.records, session_incarnation)
    errors = sorted(set(errors).union(parsed.errors))
    reasons = []
    if transcript_status != "unchanged":
        reasons.append("transcript_" + transcript_status)
    if parsed.quarantined_tail_bytes:
        reasons.append("quarantined_tail")
    if errors:
        reasons.append("collector_errors")
    if writer_state != "stopped":
        reasons.append("writer_unconfirmed")
    if not lifecycle_complete:
        reasons.append("lifecycle_unconfirmed")
    if not workspace_available:
        reasons.append("workspace_unavailable")
    if not bindings:
        reasons.append("bindings_unavailable")
    if operation_coverage != "fixture_complete":
        reasons.append("operation_coverage_unknown")
    sanitized = {"tool_operations": operations, "collector_errors": errors}
    body = {
        "schema_version": "torc.harness_capture.v0",
        "harness": "synthetic-claude-shaped-v0",
        "session_ref": session_ref, "session_incarnation": session_incarnation,
        "observed_at": observed_at, "boundary": boundary,
        "captured_prefix": {
            "byte_length": prefix_length,
            "raw_sha256": hashlib.sha256(data[:prefix_length]).hexdigest(),
            "parsed_byte_length": parsed.parsed_byte_length,
            "quarantined_tail_bytes": parsed.quarantined_tail_bytes,
        },
        "transcript_after_capture": {"status": transcript_status},
        "coverage": {"status": "incomplete" if reasons else "complete",
                     "reasons": reasons, "writer_state": writer_state,
                     "operation_coverage": operation_coverage},
        "redacted_view": {"policy_version": "metadata-only-v0",
                          "sha256": payload_sha256(sanitized)},
        "bindings": deepcopy(bindings), "quiescence": "unknown", "usage_ref": usage_ref,
        **sanitized,
    }
    return {"capture_id": "sha256:" + payload_sha256(body), **body}
