"""Deterministically score a continuity run with corrected label accounting."""

from __future__ import annotations

import argparse
import hashlib
import json
import unicodedata
from pathlib import Path
from typing import Any

import jsonschema

ROOT = Path(__file__).resolve().parent
SCORER_VERSION = "sol-continuity-2"
FIELDS = (
    "settled_decisions",
    "active_commitments",
    "hard_constraints",
    "unresolved_work",
    "uncertainties",
)


def normalize(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def normalized_set(values: list[Any]) -> set[str]:
    return {normalize(value) for value in values}


def set_score(expected: list[Any], actual: list[Any]) -> dict[str, Any]:
    wanted = normalized_set(expected)
    observed = normalized_set(actual)
    matched = len(wanted & observed)
    return {
        "matched": matched,
        "required": len(wanted),
        "asserted": len(observed),
        "recall": round(matched / len(wanted), 6) if wanted else 1.0,
        "precision": round(matched / len(observed), 6) if observed else 1.0,
    }


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _oracles() -> tuple[dict[str, Any], dict[str, Any]]:
    label_oracle = json.loads(
        (ROOT / "fixture" / "oracle-v2.json").read_text(encoding="utf-8")
    )
    base_path = ROOT / "fixture" / label_oracle["base_oracle_path"]
    if sha256(base_path) != label_oracle["base_oracle_sha256"]:
        raise ValueError("base oracle hash does not match scorer v2 input")
    return json.loads(base_path.read_text(encoding="utf-8")), label_oracle


def score(run_dir: Path) -> dict[str, Any]:
    oracle, label_oracle = _oracles()
    schema = json.loads(
        (ROOT / "schemas" / "target-output.schema.json").read_text(encoding="utf-8")
    )
    output_path = run_dir / "target-output.json"
    output = json.loads(output_path.read_text(encoding="utf-8"))
    jsonschema.validate(output, schema)

    required = oracle["required"]
    field_scores = {
        field: set_score(required[field], output[field]) for field in FIELDS
    }
    continuity_recall = round(
        sum(item["matched"] for item in field_scores.values())
        / sum(item["required"] for item in field_scores.values()),
        6,
    )

    expected_inherited = normalized_set(label_oracle["inherited_assertions"])
    assertions = output["assertions"]
    correct_labels = sum(
        1
        for item in assertions
        if (
            item["label"] == "inherited"
            and normalize(item["text"]) in expected_inherited
        )
        or (
            item["label"] == "new"
            and normalize(item["text"]) not in expected_inherited
        )
    )
    inherited = [item for item in assertions if item["label"] == "inherited"]
    inherited_values = [item["text"] for item in inherited]
    inherited_score = set_score(label_oracle["inherited_assertions"], inherited_values)
    recoverable = sum(1 for item in inherited if item["source_ref"].strip())

    expected_areas = oracle["required_blocking_areas"]
    observed_areas = [item["area"] for item in output["blocking_findings"]]
    review_score = set_score(expected_areas, observed_areas)

    rendered = normalize(json.dumps(output, sort_keys=True))
    contradictions = [
        claim
        for claim in oracle["forbidden_assertions"]
        if normalize(claim) in rendered
    ]
    core = {
        "identity_correct": output["lineage_identity"] == required["lineage_identity"],
        "responsibility_correct": (
            output["current_responsibility"] == required["current_responsibility"]
        ),
        "handoff_reason_correct": output["handoff_reason"] == required["handoff_reason"],
        "source_revision_correct": (
            output["source_revision_id"] == required["source_revision_id"]
        ),
        "field_scores": field_scores,
        "continuity_recall": continuity_recall,
        "inherited_new_label_accuracy": (
            round(correct_labels / len(assertions), 6) if assertions else 0.0
        ),
        "inherited_assertion_score": inherited_score,
        "provenance_recoverability": (
            round(recoverable / len(inherited), 6) if inherited else 0.0
        ),
        "contradiction_count": len(contradictions),
        "contradictions": contradictions,
        "blocking_area_score": review_score,
        "release_decision_correct": (
            output["release_decision"] == oracle["required_release_decision"]
        ),
        "completion_status": output["completion_status"],
    }
    encoded = json.dumps(core, ensure_ascii=False, separators=(",", ":"), sort_keys=True)
    return {
        "schema_version": 1,
        "run_id": run_dir.name,
        "scorer_version": SCORER_VERSION,
        "target_output_sha256": sha256(output_path),
        "score_core": core,
        "score_core_sha256": hashlib.sha256(encoded.encode("utf-8")).hexdigest(),
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    print(json.dumps(score(args.run_dir), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
