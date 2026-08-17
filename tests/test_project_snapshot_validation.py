from __future__ import annotations

import hashlib
from pathlib import Path

import pytest

from torc.artifacts.identity import seal_content_id
from torc.artifacts.validation import validate_evidence_bundle, validate_project_snapshot

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
NOW = "2026-08-16T12:00:00Z"
COMMIT = "1" * 40


def evidence_bundle() -> dict[str, object]:
    content = "# Status\n\nReady.\n"
    return seal_content_id(
        {
            "schema": "urn:lugos:artifact:evidence-bundle:v1alpha1",
            "bundle_id": "",
            "collected_at": NOW,
            "collector": {"name": "torc", "version": "0.1.0"},
            "scope": {
                "repositories": [{"repository": "local/torc", "commit": COMMIT, "branch": "main"}]
            },
            "sources": [
                {
                    "source_id": "status",
                    "type": "git-file",
                    "repository": "local/torc",
                    "commit": COMMIT,
                    "path": "STATUS.md",
                    "selector": {"type": "whole-file"},
                    "content_sha256": "sha256:" + hashlib.sha256(content.encode()).hexdigest(),
                    "collected_at": NOW,
                    "content": content,
                }
            ],
            "git_state": [
                {
                    "repository": "local/torc",
                    "commit": COMMIT,
                    "branch": "main",
                    "clean": True,
                    "modified_paths": [],
                    "untracked_paths": [],
                    "recent_commits": [
                        {"commit": COMMIT, "subject": "Initial", "authored_at": NOW}
                    ],
                }
            ],
            "warnings": [],
        },
        "bundle_id",
    )


def project_snapshot(
    bundle: dict[str, object],
    *,
    provider: str = "manual",
    claim_status: str = "verified",
    evidence: list[dict[str, str]] | None = None,
) -> dict[str, object]:
    return seal_content_id(
        {
            "schema": "urn:lugos:artifact:project-snapshot:v1alpha1",
            "artifact_id": "",
            "kind": "project-snapshot",
            "generated_at": NOW,
            "scope": {
                "name": "TORC",
                "repositories": [{"repository": "local/torc", "commit": COMMIT}],
            },
            "generator": {
                "implementation": "fixture-writer",
                "version": "1",
                "provider": provider,
            },
            "evidence_bundle": {"bundle_id": bundle["bundle_id"]},
            "projects": [
                {
                    "project_id": "torc",
                    "name": "TORC",
                    "status": "active",
                    "repositories": ["local/torc"],
                    "progress": [{"kind": "milestone", "label": "artifact slice"}],
                }
            ],
            "claims": [
                {
                    "claim_id": "claim-status",
                    "subject": "torc",
                    "predicate": "implementation_state",
                    "value": "ready",
                    "status": claim_status,
                    "evidence": ([{"source_id": "status"}] if evidence is None else evidence),
                    "observed_at": NOW,
                }
            ],
            "blockers": [],
            "pending_decisions": [],
            "recent_activity": [],
            "conflicts": [],
            "unknowns": [],
            "metadata": {},
        },
        "artifact_id",
    )


def test_valid_bundle_and_snapshot_pass_all_checks() -> None:
    bundle = evidence_bundle()
    snapshot = project_snapshot(bundle)

    bundle_result = validate_evidence_bundle(bundle, SCHEMAS)
    snapshot_result = validate_project_snapshot(snapshot, bundle, SCHEMAS)

    assert bundle_result.valid is True
    assert snapshot_result.valid is True
    assert snapshot_result.errors == []
    assert all(check["status"] == "passed" for check in snapshot_result.checks)


@pytest.mark.parametrize("provider", ["openai", "anthropic", "local", "manual"])
def test_provider_is_provenance_only(provider: str) -> None:
    bundle = evidence_bundle()
    result = validate_project_snapshot(project_snapshot(bundle, provider=provider), bundle, SCHEMAS)
    assert result.valid is True


def test_verified_claim_without_evidence_is_rejected() -> None:
    bundle = evidence_bundle()
    snapshot = project_snapshot(bundle, evidence=[])

    result = validate_project_snapshot(snapshot, bundle, SCHEMAS)

    assert result.valid is False
    assert any("verified claim claim-status has no evidence" in item for item in result.errors)


def test_claim_with_nonexistent_source_is_rejected() -> None:
    bundle = evidence_bundle()
    snapshot = project_snapshot(bundle, evidence=[{"source_id": "missing"}])

    result = validate_project_snapshot(snapshot, bundle, SCHEMAS)

    assert result.valid is False
    assert any("unknown evidence source missing" in item for item in result.errors)


def test_malformed_timestamp_is_rejected_even_with_a_correct_digest() -> None:
    bundle = evidence_bundle()
    snapshot = project_snapshot(bundle)
    snapshot["generated_at"] = "yesterday"
    snapshot = seal_content_id(snapshot, "artifact_id")

    result = validate_project_snapshot(snapshot, bundle, SCHEMAS)

    assert result.valid is False
    assert any("generated_at" in item for item in result.errors)


def test_modified_artifact_fails_digest_verification() -> None:
    bundle = evidence_bundle()
    snapshot = project_snapshot(bundle)
    snapshot["metadata"] = {"tampered": True}

    result = validate_project_snapshot(snapshot, bundle, SCHEMAS)

    assert result.valid is False
    assert any("artifact digest does not match content" in item for item in result.errors)


def test_bundle_reference_must_match_supplied_evidence() -> None:
    bundle = evidence_bundle()
    snapshot = project_snapshot(bundle)
    snapshot["evidence_bundle"] = {"bundle_id": "sha256:" + "f" * 64}
    snapshot = seal_content_id(snapshot, "artifact_id")

    result = validate_project_snapshot(snapshot, bundle, SCHEMAS)

    assert result.valid is False
    assert any("supplied Evidence Bundle" in item for item in result.errors)


def test_missing_evidence_bundle_fails_existence_and_integrity_checks() -> None:
    bundle = evidence_bundle()
    snapshot = project_snapshot(bundle)

    result = validate_project_snapshot(snapshot, None, SCHEMAS)

    failed = {
        check["name"] for check in result.checks if check["status"] == "failed"
    }
    assert result.valid is False
    assert {"evidence_bundle_existence", "evidence_bundle_integrity"} <= failed


def test_conflicted_and_unknown_claims_remain_non_verified() -> None:
    bundle = evidence_bundle()
    conflicted = project_snapshot(bundle, claim_status="conflicted", evidence=[])
    unknown = project_snapshot(bundle, claim_status="unknown", evidence=[])

    assert validate_project_snapshot(conflicted, bundle, SCHEMAS).valid is True
    assert validate_project_snapshot(unknown, bundle, SCHEMAS).valid is True
