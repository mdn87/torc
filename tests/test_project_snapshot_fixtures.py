from __future__ import annotations

import json
from pathlib import Path

from jsonschema import Draft202012Validator, FormatChecker

from torc.artifacts.identity import content_id_is_valid
from torc.artifacts.render import render_snapshot_html
from torc.artifacts.validation import validate_evidence_bundle, validate_project_snapshot

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
FIXTURES = ROOT / "fixtures" / "project-snapshot"


def _load(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_committed_project_snapshot_fixtures_cover_acceptance_conflict_and_unknowns() -> None:
    bundle = _load(FIXTURES / "evidence.accepted.json")
    assert validate_evidence_bundle(bundle, SCHEMAS).valid is True

    for name in (
        "snapshot.accepted.manual.json",
        "snapshot.conflicted.json",
        "snapshot.unknowns.json",
    ):
        snapshot = _load(FIXTURES / name)
        assert validate_project_snapshot(snapshot, bundle, SCHEMAS).valid is True

    accepted = _load(FIXTURES / "snapshot.accepted.manual.json")
    conflicted = _load(FIXTURES / "snapshot.conflicted.json")
    unknowns = _load(FIXTURES / "snapshot.unknowns.json")
    assert accepted["generator"]["provider"] == "manual"
    assert accepted["metadata"]["producer_kind"] == "non-ai"
    assert conflicted["claims"][0]["status"] == "conflicted"
    assert conflicted["conflicts"]
    assert unknowns["claims"][0]["status"] == "unknown"
    assert unknowns["unknowns"]


def test_committed_rejected_fixture_fails_for_verified_claim_without_evidence() -> None:
    bundle = _load(FIXTURES / "evidence.accepted.json")
    rejected = _load(FIXTURES / "snapshot.rejected.json")

    result = validate_project_snapshot(rejected, bundle, SCHEMAS)

    assert result.valid is False
    assert any("verified claim unsupported has no evidence" in item for item in result.errors)


def test_committed_receipt_matches_schema_identity_and_accepted_fixture() -> None:
    receipt = _load(FIXTURES / "receipt.accepted.json")
    snapshot = _load(FIXTURES / "snapshot.accepted.manual.json")
    schema = _load(SCHEMAS / "acceptance-receipt.v1alpha1.schema.json")

    Draft202012Validator(schema, format_checker=FormatChecker()).validate(receipt)
    assert content_id_is_valid(receipt, "receipt_id") is True
    assert receipt["artifact_id"] == snapshot["artifact_id"]


def test_reference_renderer_loads_the_accepted_fixture() -> None:
    snapshot = _load(FIXTURES / "snapshot.accepted.manual.json")
    receipt = _load(FIXTURES / "receipt.accepted.json")

    html = render_snapshot_html(snapshot, receipt)

    assert "reference-consumer-ready" in html
    assert "Created a provider-neutral fixture" in html
    assert "Acceptance: accepted" in html
