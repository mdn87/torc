"""Deterministic serialization and SHA-256 tamper evidence.

SHA-256 here detects accidental or post-hoc content changes. It does not
authenticate writers, encrypt state, or protect against a malicious local
process with filesystem access.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import UTC, datetime
from typing import Any


def canonical_json(value: Any) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def payload_sha256(value: Any) -> str:
    return hashlib.sha256(canonical_json(value).encode("utf-8")).hexdigest()


def hashable_record(record: dict[str, Any]) -> dict[str, Any]:
    payload = deepcopy(record)
    payload.pop("integrity", None)
    return payload


def seal_record(
    record: dict[str, Any],
    *,
    previous_revision_sha256: str | None | object = ...,
) -> dict[str, Any]:
    sealed = deepcopy(record)
    integrity: dict[str, Any] = {
        "algorithm": "sha256",
        "canonical_payload_sha256": payload_sha256(hashable_record(sealed)),
    }
    if previous_revision_sha256 is not ...:
        integrity["previous_revision_sha256"] = previous_revision_sha256
    sealed["integrity"] = integrity
    return sealed


def record_hash_is_valid(record: dict[str, Any]) -> bool:
    integrity = record.get("integrity", {})
    return (
        integrity.get("algorithm") == "sha256"
        and integrity.get("canonical_payload_sha256")
        == payload_sha256(hashable_record(record))
    )


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="microseconds").replace("+00:00", "Z")
