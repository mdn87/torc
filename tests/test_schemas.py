from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from torc.canonical import payload_sha256

ROOT = Path(__file__).resolve().parents[1]

CASES = (
    ("lineage-revision.schema.json", "lineage-revision.example.json"),
    ("execution-projection.schema.json", "execution-projection.example.json"),
    ("fit-decision.schema.json", "fit-decision.example.json"),
    ("handoff-snapshot.schema.json", "handoff-snapshot.example.json"),
    ("handoff-result.schema.json", "handoff-result.example.json"),
    ("experiment-manifest.schema.json", "experiment-manifest.example.json"),
    ("experiment-run.schema.json", "experiment-run.example.json"),
    ("continuity-payload.schema.json", "continuity-payload.example.json"),
    ("score-report.schema.json", "score-report.example.json"),
    ("artifact-manifest.schema.json", "artifact-manifest.example.json"),
)


@pytest.mark.parametrize(("schema_name", "example_name"), CASES)
def test_example_matches_schema(schema_name: str, example_name: str) -> None:
    schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
    example = json.loads((ROOT / "examples" / example_name).read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(example)


def test_experiment_manifest_pins_fixture_bytes() -> None:
    manifest = json.loads(
        (ROOT / "examples" / "experiment-manifest.example.json").read_text(
            encoding="utf-8"
        )
    )
    fixture = manifest["fixture"]
    for entry in [*fixture["agent_visible"], fixture["oracle"], fixture["scoring"]]:
        assert hashlib.sha256((ROOT / entry["path"]).read_bytes()).hexdigest() == (
            entry["sha256"]
        )


def test_score_report_example_pins_canonical_score_core() -> None:
    report = json.loads(
        (ROOT / "examples" / "score-report.example.json").read_text(encoding="utf-8")
    )
    assert report["score_core_sha256"] == payload_sha256(report["score_core"])
