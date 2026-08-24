"""Schema, integrity, timestamp, and evidence validation for snapshot records."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from .identity import content_id_is_valid


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    checks: list[dict[str, str]]
    warnings: list[str]
    errors: list[str]

    def as_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "checks": self.checks,
            "warnings": self.warnings,
            "errors": self.errors,
        }


def _schema_errors(record: dict[str, Any], schema_path: Path) -> list[str]:
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    validator = Draft202012Validator(schema, format_checker=FormatChecker())
    errors = []
    for error in sorted(validator.iter_errors(record), key=lambda item: list(item.path)):
        location = ".".join(str(part) for part in error.absolute_path) or "record"
        errors.append(f"schema {location}: {error.message}")
    return errors


def _check(
    checks: list[dict[str, str]],
    errors: list[str],
    name: str,
    failures: list[str],
    success: str,
) -> None:
    if failures:
        errors.extend(failures)
        checks.append({"name": name, "status": "failed", "detail": failures[0]})
    else:
        checks.append({"name": name, "status": "passed", "detail": success})


def _timestamp_failures(value: Any, path: str = "") -> list[str]:
    failures: list[str] = []
    if isinstance(value, dict):
        for key, item in value.items():
            location = f"{path}.{key}" if path else key
            if key.endswith("_at"):
                try:
                    parsed = datetime.fromisoformat(str(item).replace("Z", "+00:00"))
                    if parsed.tzinfo is None:
                        raise ValueError("timezone is required")
                except (TypeError, ValueError):
                    failures.append(f"invalid timestamp at {location}: {item!r}")
            else:
                failures.extend(_timestamp_failures(item, location))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            failures.extend(_timestamp_failures(item, f"{path}.{index}"))
    return failures


def validate_evidence_bundle(bundle: dict[str, Any], schema_dir: Path | str) -> ValidationResult:
    schemas = Path(schema_dir)
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings = list(bundle.get("warnings", [])) if isinstance(bundle, dict) else []

    schema_failures = _schema_errors(bundle, schemas / "evidence-bundle.v1alpha1.schema.json")
    _check(
        checks,
        errors,
        "schema_validity",
        schema_failures,
        "Evidence Bundle matches v1alpha1 schema and timestamp formats",
    )
    _check(
        checks,
        errors,
        "timestamps",
        _timestamp_failures(bundle),
        "All Evidence Bundle timestamps are timezone-aware ISO-8601 values",
    )

    digest_failures = (
        []
        if content_id_is_valid(bundle, "bundle_id")
        else ["Evidence Bundle digest does not match content"]
    )
    _check(
        checks,
        errors,
        "canonical_digest",
        digest_failures,
        "Evidence Bundle canonical digest matches content",
    )

    content_failures = []
    for source in bundle.get("sources", []):
        if not isinstance(source, dict) or not isinstance(source.get("content"), str):
            continue
        actual = "sha256:" + hashlib.sha256(source["content"].encode("utf-8")).hexdigest()
        if source.get("content_sha256") != actual:
            source_id = source.get("source_id", "<unknown>")
            content_failures.append(
                f"evidence source {source_id} content digest does not match"
            )
    _check(
        checks,
        errors,
        "source_content_digests",
        content_failures,
        "All collected source content digests match",
    )
    return ValidationResult(not errors, checks, warnings, errors)


def validate_acceptance_receipt(
    receipt: dict[str, Any], schema_dir: Path | str
) -> ValidationResult:
    schemas = Path(schema_dir)
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings = list(receipt.get("warnings", []))
    _check(
        checks,
        errors,
        "schema_validity",
        _schema_errors(
            receipt, schemas / "acceptance-receipt.v1alpha1.schema.json"
        ),
        "Acceptance Receipt matches v1alpha1 schema",
    )
    _check(
        checks,
        errors,
        "timestamps",
        _timestamp_failures(receipt),
        "All Acceptance Receipt timestamps are timezone-aware ISO-8601 values",
    )
    digest_failures = (
        []
        if content_id_is_valid(receipt, "receipt_id")
        else ["Acceptance Receipt digest does not match content"]
    )
    _check(
        checks,
        errors,
        "canonical_digest",
        digest_failures,
        "Acceptance Receipt canonical digest matches content",
    )
    return ValidationResult(not errors, checks, warnings, errors)


def _evidence_references(snapshot: dict[str, Any]) -> list[str]:
    references: list[str] = []
    for collection in (
        "claims",
        "blockers",
        "pending_decisions",
        "recent_activity",
        "conflicts",
        "unknowns",
    ):
        for record in snapshot.get(collection, []):
            if not isinstance(record, dict):
                continue
            for reference in record.get("evidence", []):
                if isinstance(reference, dict) and isinstance(reference.get("source_id"), str):
                    references.append(reference["source_id"])
    for project in snapshot.get("projects", []):
        if not isinstance(project, dict):
            continue
        if isinstance(project.get("status_source_id"), str):
            references.append(project["status_source_id"])
        for progress in project.get("progress", []):
            if isinstance(progress, dict) and isinstance(progress.get("source_id"), str):
                references.append(progress["source_id"])
    return references


def validate_project_snapshot(
    snapshot: dict[str, Any],
    evidence_bundle: dict[str, Any] | None,
    schema_dir: Path | str,
) -> ValidationResult:
    schemas = Path(schema_dir)
    checks: list[dict[str, str]] = []
    errors: list[str] = []
    warnings: list[str] = []

    schema_failures = _schema_errors(snapshot, schemas / "project-snapshot.v1alpha1.schema.json")
    _check(
        checks,
        errors,
        "schema_validity",
        schema_failures,
        "Project Snapshot matches v1alpha1 schema and timestamp formats",
    )
    _check(
        checks,
        errors,
        "timestamps",
        _timestamp_failures(snapshot),
        "All Project Snapshot timestamps are timezone-aware ISO-8601 values",
    )

    digest_failures = (
        []
        if content_id_is_valid(snapshot, "artifact_id")
        else ["artifact digest does not match content"]
    )
    _check(
        checks,
        errors,
        "canonical_digest",
        digest_failures,
        "Project Snapshot canonical digest matches content",
    )

    existence_failures = [] if evidence_bundle is not None else ["Evidence Bundle does not exist"]
    _check(
        checks,
        errors,
        "evidence_bundle_existence",
        existence_failures,
        "Supplied Evidence Bundle exists",
    )

    if evidence_bundle is None:
        bundle_result = None
        bundle_id = None
        source_ids: set[str] = set()
    else:
        bundle_result = validate_evidence_bundle(evidence_bundle, schemas)
        bundle_id = evidence_bundle.get("bundle_id")
        source_ids = {
            source["source_id"]
            for source in evidence_bundle.get("sources", [])
            if isinstance(source, dict) and isinstance(source.get("source_id"), str)
        }
        warnings.extend(bundle_result.warnings)

    if bundle_result is None:
        bundle_failures = ["Evidence Bundle cannot be validated because it does not exist"]
    elif bundle_result.valid:
        bundle_failures = []
    else:
        bundle_failures = [
            f"Evidence Bundle validation failed: {message}"
            for message in bundle_result.errors
        ]
    _check(
        checks,
        errors,
        "evidence_bundle_integrity",
        bundle_failures,
        "Evidence Bundle schema, timestamps, and digests are valid",
    )

    referenced_bundle = (
        snapshot.get("evidence_bundle", {}).get("bundle_id")
        if isinstance(snapshot.get("evidence_bundle"), dict)
        else None
    )
    reference_failures = (
        []
        if bundle_id is not None and referenced_bundle == bundle_id
        else ["artifact does not reference the supplied Evidence Bundle"]
    )
    _check(
        checks,
        errors,
        "evidence_bundle_reference",
        reference_failures,
        "Artifact references the supplied Evidence Bundle digest",
    )

    verified_failures = []
    for claim in snapshot.get("claims", []):
        if not isinstance(claim, dict) or claim.get("status") != "verified":
            continue
        if not claim.get("evidence"):
            verified_failures.append(
                f"verified claim {claim.get('claim_id', '<unknown>')} has no evidence"
            )
    _check(
        checks,
        errors,
        "verified_claim_evidence",
        verified_failures,
        "Every verified claim references evidence",
    )

    claim_statuses: dict[str, str] = {}
    conflict_failures: list[str] = []
    for claim in snapshot.get("claims", []):
        if not isinstance(claim, dict) or not isinstance(claim.get("claim_id"), str):
            continue
        claim_id = claim["claim_id"]
        if claim_id in claim_statuses:
            conflict_failures.append(f"duplicate claim identity {claim_id}")
        elif isinstance(claim.get("status"), str):
            claim_statuses[claim_id] = claim["status"]
    for conflict in snapshot.get("conflicts", []):
        if not isinstance(conflict, dict):
            continue
        conflict_id = conflict.get("conflict_id", "<unknown>")
        for claim_id in conflict.get("claim_ids", []):
            if claim_id not in claim_statuses:
                conflict_failures.append(
                    f"conflict {conflict_id} references unknown claim {claim_id}"
                )
            elif claim_statuses[claim_id] != "conflicted":
                conflict_failures.append(
                    f"conflict {conflict_id} references claim {claim_id} "
                    f"with status {claim_statuses[claim_id]}"
                )
    _check(
        checks,
        errors,
        "claim_conflict_consistency",
        conflict_failures,
        "Claim identities are unique and every conflict references conflicted claims",
    )

    resolution_failures = [
        f"unknown evidence source {source_id}"
        for source_id in sorted(set(_evidence_references(snapshot)) - source_ids)
    ]
    _check(
        checks,
        errors,
        "evidence_source_resolution",
        resolution_failures,
        "Every referenced evidence source resolves in the bundle",
    )

    return ValidationResult(not errors, checks, warnings, errors)
