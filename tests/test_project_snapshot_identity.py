from __future__ import annotations

from torc.artifacts.identity import content_id_is_valid, seal_content_id


def test_canonical_content_identity_is_stable_and_detects_mutation() -> None:
    payload = {
        "schema": "urn:lugos:artifact:project-snapshot:v1alpha1",
        "artifact_id": "",
        "kind": "project-snapshot",
        "generated_at": "2026-08-16T12:00:00Z",
        "metadata": {"z": 2, "a": 1},
    }

    first = seal_content_id(payload, "artifact_id")
    second = seal_content_id(payload, "artifact_id")

    assert first == second
    assert first["artifact_id"] == (
        "sha256:22a063c4255348344ff427f0216c4c66bb0f681473f4006f5eec87b26f6918ba"
    )
    assert content_id_is_valid(first, "artifact_id") is True

    first["metadata"]["a"] = 3
    assert content_id_is_valid(first, "artifact_id") is False
