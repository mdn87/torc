"""Deterministic scoring for frozen P1a artifacts."""

from __future__ import annotations

import json
import unicodedata
from collections.abc import Callable
from pathlib import Path
from typing import Any

from .canonical import payload_sha256, utc_now

SCORER_VERSION = "p1a-1"


def normalize_string(value: Any) -> str:
    return " ".join(unicodedata.normalize("NFKC", str(value)).casefold().split())


def normalize_string_set(values: list[Any]) -> tuple[str, ...]:
    return tuple(sorted({normalize_string(value) for value in values}))


def _recall(expected: list[Any], actual: list[Any]) -> dict[str, Any]:
    required = set(normalize_string_set(expected))
    asserted = set(normalize_string_set(actual))
    matched = len(required & asserted)
    return {
        "matched": matched,
        "required": len(required),
        "asserted": len(asserted),
        "recall": round(matched / len(required), 6) if required else 1.0,
        "precision": round(matched / len(asserted), 6) if asserted else 1.0,
    }


def score_reconstruction(
    oracle: dict[str, Any],
    reconstruction: dict[str, Any],
    rules: dict[str, Any],
) -> dict[str, Any]:
    required = oracle["required"]
    field_scores = {
        field: _recall(required[field], reconstruction.get(field, []))
        for field in (
            "active_commitments",
            "hard_constraints",
            "settled_decisions",
            "unresolved_work",
        )
    }
    inherited_values = {
        normalized
        for value in required.values()
        for normalized in (
            normalize_string_set(value) if isinstance(value, list) else ()
        )
    }
    assertions = reconstruction.get("assertions", [])
    correctly_labeled = sum(
        1
        for assertion in assertions
        if (
            assertion.get("label") == "inherited"
            and normalize_string(assertion.get("text")) in inherited_values
        )
        or (
            assertion.get("label") == "new"
            and normalize_string(assertion.get("text")) not in inherited_values
        )
    )
    provenance_required = [
        assertion for assertion in assertions if assertion.get("label") == "inherited"
    ]
    roots = tuple(oracle["provenance_roots"])
    recoverable = sum(
        1
        for assertion in provenance_required
        if any(str(assertion.get("source_ref", "")).startswith(root) for root in roots)
    )
    asserted_text = {normalize_string(item.get("text")) for item in assertions}
    contradictions = [
        rule
        for rule in oracle.get("contradictions", [])
        if normalize_string(rule["assertion"]) in asserted_text
    ]
    areas = set(reconstruction.get("review_areas", []))
    required_areas = set(rules["required_review_areas"])
    required_fields = set(rules["required_output_fields"])
    present_fields = {field for field in required_fields if field in reconstruction}
    completion_valid = (
        reconstruction.get("completion_status") in rules["allowed_completion_statuses"]
    )
    structural_total = len(required_areas) + len(required_fields) + 1
    structural_passed = (
        len(required_areas & areas) + len(present_fields) + int(completion_valid)
    )
    return {
        "field_scores": field_scores,
        "inherited_new_label_accuracy": round(
            correctly_labeled / len(assertions), 6
        )
        if assertions
        else 1.0,
        "contradiction_count": len(contradictions),
        "contradictions": contradictions,
        "provenance_recoverability": round(
            recoverable / len(provenance_required), 6
        )
        if provenance_required
        else 1.0,
        "task_quality": {
            "passed": structural_passed,
            "required": structural_total,
            "ratio": round(structural_passed / structural_total, 6),
        },
    }


def build_score_core(
    field_scores: dict[str, Any],
    structural_checks: dict[str, Any],
) -> dict[str, Any]:
    return {
        "field_scores": field_scores,
        "inherited_new_label_accuracy": structural_checks[
            "inherited_new_label_accuracy"
        ],
        "contradiction_count": structural_checks["contradiction_count"],
        "contradictions": structural_checks["contradictions"],
        "provenance_recoverability": structural_checks[
            "provenance_recoverability"
        ],
        "context_delivered": structural_checks["context_delivered"],
        "task_quality": structural_checks["task_quality"],
    }


def _repo_root(start: Path) -> Path:
    for candidate in (start.resolve(), *start.resolve().parents):
        if (candidate / "pyproject.toml").is_file():
            return candidate
    raise ValueError("could not locate TORC repository root")


def score_run(
    run_dir: Path | str, *, clock: Callable[[], str] = utc_now
) -> dict[str, Any]:
    root = Path(run_dir).resolve()
    manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
    repo = _repo_root(Path(__file__))
    oracle = json.loads(
        (repo / manifest["fixture"]["oracle"]["path"]).read_text(encoding="utf-8")
    )
    rules = json.loads(
        (repo / manifest["fixture"]["scoring"]["path"]).read_text(encoding="utf-8")
    )
    reference = json.loads(
        (root / "artifacts" / "reconstruction.json").read_text(encoding="utf-8")
    )
    reconstruction = json.loads((root / reference["path"]).read_text(encoding="utf-8"))
    payload = json.loads(
        (root / "artifacts" / "continuity-payload.json").read_text(encoding="utf-8")
    )
    checks = score_reconstruction(oracle, reconstruction, rules)
    checks["context_delivered"] = payload["context"]
    core = build_score_core(checks.pop("field_scores"), checks)
    return {
        "schema_version": 1,
        "run_id": manifest["run_id"],
        "scorer_version": manifest["scoring"]["scorer_version"],
        "score_core": core,
        "score_core_sha256": payload_sha256(core),
        "operational_measurements": {
            "scored_at": clock(),
            "duration_ms": 0,
            "operator_steps": len(list((root / "receipts").glob("*.json"))) + 1,
        },
    }
