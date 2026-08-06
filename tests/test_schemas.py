from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

ROOT = Path(__file__).resolve().parents[1]

CASES = (
    ("lineage-revision.schema.json", "lineage-revision.example.json"),
    ("execution-projection.schema.json", "execution-projection.example.json"),
    ("fit-decision.schema.json", "fit-decision.example.json"),
    ("handoff-snapshot.schema.json", "handoff-snapshot.example.json"),
    ("handoff-result.schema.json", "handoff-result.example.json"),
)


@pytest.mark.parametrize(("schema_name", "example_name"), CASES)
def test_example_matches_schema(schema_name: str, example_name: str) -> None:
    schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
    example = json.loads((ROOT / "examples" / example_name).read_text(encoding="utf-8"))

    Draft202012Validator.check_schema(schema)
    Draft202012Validator(schema).validate(example)
