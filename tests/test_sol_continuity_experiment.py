from __future__ import annotations

import hashlib
import json
import runpy
from pathlib import Path

import jsonschema

ROOT = Path(__file__).resolve().parents[1] / "experiments" / "sol-continuity-001"


def _read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_frozen_manifest_inputs_match_hashes() -> None:
    for name, field in (
        ("manifest.json", "inputs"),
        ("series-002-manifest.json", "fixed_inputs"),
    ):
        manifest = _read(ROOT / name)
        for item in manifest[field]:
            assert _sha256(ROOT / item["path"]) == item["sha256"]


def test_preserved_target_outputs_match_schema_and_recorded_hashes() -> None:
    schema = _read(ROOT / "schemas" / "target-output.schema.json")
    for series in ("series-001", "series-002"):
        for path in sorted((ROOT / "runs" / series).glob("*/target-output.json")):
            jsonschema.validate(_read(path), schema)

    disposition = _read(ROOT / "runs" / "series-001" / "disposition.json")
    for item in disposition["preserved_outputs"]:
        path = ROOT / "runs" / "series-001" / item["run_id"] / "target-output.json"
        assert _sha256(path) == item["sha256"]

    results = _read(ROOT / "runs" / "series-002" / "results.json")
    for item in results["runs"]:
        path = ROOT / "runs" / "series-002" / item["run_id"] / "target-output.json"
        assert _sha256(path) == item["target_output_sha256"]


def test_recorded_series_002_scores_replay() -> None:
    scorer = runpy.run_path(str(ROOT / "score.py"))["score"]
    results = _read(ROOT / "runs" / "series-002" / "results.json")
    for recorded in results["runs"]:
        run_dir = ROOT / "runs" / "series-002" / recorded["run_id"]
        actual = scorer(run_dir)
        core = actual["score_core"]
        assert actual["score_core_sha256"] == recorded["score_core_sha256"]
        assert core["continuity_recall"] == recorded["continuity_recall"]
        assert (
            core["blocking_area_score"]["recall"]
            == recorded["blocking_area_recall"]
        )
        assert core["release_decision_correct"] is recorded["release_decision_correct"]
        assert core["contradiction_count"] == recorded["contradiction_count"]


def test_scorer_v2_corrects_inherited_label_accounting() -> None:
    scorer = runpy.run_path(str(ROOT / "score_v2.py"))["score"]
    results = _read(ROOT / "runs" / "series-002" / "results.json")

    for recorded in results["runs"]:
        run_dir = ROOT / "runs" / "series-002" / recorded["run_id"]
        report = scorer(run_dir)
        core = report["score_core"]
        assert report["scorer_version"] == "sol-continuity-2"
        assert core["inherited_new_label_accuracy"] == 1.0
        assert core["inherited_assertion_score"]["precision"] == 1.0
