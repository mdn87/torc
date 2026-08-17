"""Content identities for immutable artifact records."""

from __future__ import annotations

from copy import deepcopy
from typing import Any

from torc.canonical import payload_sha256


def content_payload(record: dict[str, Any], identity_field: str) -> dict[str, Any]:
    """Return the canonical hash payload without its self-referential identity."""

    payload = deepcopy(record)
    payload.pop(identity_field, None)
    return payload


def content_id(record: dict[str, Any], identity_field: str) -> str:
    return f"sha256:{payload_sha256(content_payload(record, identity_field))}"


def seal_content_id(record: dict[str, Any], identity_field: str) -> dict[str, Any]:
    sealed = deepcopy(record)
    sealed[identity_field] = content_id(sealed, identity_field)
    return sealed


def content_id_is_valid(record: dict[str, Any], identity_field: str) -> bool:
    value = record.get(identity_field)
    return isinstance(value, str) and value == content_id(record, identity_field)
