"""Conservative observations for a documented synthetic Claude-shaped subset."""

from __future__ import annotations

import re

from torc.canonical import payload_sha256

_ID = re.compile(r"[A-Za-z0-9_-]{1,128}\Z")
_KINDS = {"Read": "idempotent", "Write": "non_idempotent",
          "Edit": "non_idempotent", "Bash": "unknown"}


def valid_id(value):
    return isinstance(value, str) and _ID.fullmatch(value) is not None


def classify(records, session_incarnation: str):
    """Return sanitized operations and diagnostics, never effect verification.

    Fingerprints describe exact payloads, not semantic equivalence or permission
    to retry. Raw paths, arguments, prose and tool outputs are not exported.
    """
    if not valid_id(session_incarnation):
        raise ValueError("invalid session incarnation")
    operations = {}
    results = set()
    errors = []
    for record in records:
        event = record.get("type")
        if event == "stop":
            continue
        if not isinstance(event, str) or event not in {"assistant", "user"}:
            errors.append("unsupported_event")
            continue
        message = record.get("message")
        content = message.get("content") if isinstance(message, dict) else None
        if isinstance(content, str):  # Prose supplies no operation evidence.
            continue
        if not isinstance(content, list):
            errors.append("malformed_message")
            continue
        for item in content:
            if not isinstance(item, dict):
                errors.append("malformed_content")
                continue
            kind = item.get("type")
            if kind == "text":
                continue
            if kind == "tool_use" and event == "assistant":
                tool_id = item.get("id")
                args = item.get("input")
                name = item.get("name")
                if not valid_id(tool_id) or not isinstance(args, dict) or not isinstance(name, str):
                    errors.append("malformed_tool_use")
                    continue
                if tool_id in operations:
                    errors.append("duplicate_tool_id")
                    operations[tool_id]["observation"] = "not_observable"
                    continue
                path = args.get("file_path")
                target = {"type": "unknown", "identity": None}
                if name in {"Read", "Write", "Edit"} and isinstance(path, str) and path:
                    target = {"type": "path_digest", "identity": "sha256:" + payload_sha256(path)}
                operations[tool_id] = {
                    "operation_id": f"{session_incarnation}/{tool_id}",
                    "kind": name if name in _KINDS else "unknown",
                    "idempotency": _KINDS.get(name, "unknown"),
                    "target": target,
                    "fingerprint": "sha256:" + payload_sha256(
                        {"kind": name, "target": target, "arguments": args}),
                    "observation": "started_without_confirmed_result",
                    "evidence_ref": None,
                }
            elif kind == "tool_result" and event == "user":
                tool_id = item.get("tool_use_id")
                if not valid_id(tool_id) or tool_id not in operations:
                    errors.append("orphan_tool_result")
                    continue
                operation = operations[tool_id]
                if tool_id in results or operation["observation"] == "not_observable":
                    errors.append("ambiguous_tool_result")
                    operation["observation"] = "not_observable"
                elif type(item.get("is_error", False)) is not bool:
                    errors.append("malformed_tool_result")
                    operation["observation"] = "not_observable"
                else:
                    operation["observation"] = (
                        "reported_failure" if item.get("is_error", False) else "reported_success")
                results.add(tool_id)
            else:
                errors.append("unsupported_content")
    return list(operations.values()), sorted(set(errors))
