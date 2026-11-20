"""Held-out preparation binds the same evidence to both prompts before results exist."""

import hashlib
import importlib
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
STUDY = ROOT / "experiments/continuation-review"


@pytest.fixture
def cohort(monkeypatch):
    monkeypatch.syspath_prepend(str(STUDY))
    return importlib.import_module("prepare_cohort")


def digest(data):
    return hashlib.sha256(data).hexdigest()


def source(tmp_path, spec):
    case = "sample"
    directory = tmp_path / "intake" / case
    tree = directory / "tree"
    tree.mkdir(parents=True)
    (tree / "source.txt").write_bytes(b"interrupted\n")
    manifest = json.dumps({"source.txt": digest(b"interrupted\n")}).encode()
    (directory / "tree-manifest.json").write_bytes(manifest)
    history = json.dumps({"events": [{"source_line": n, "content": "PRIVATE_RAW_HISTORY"}
                                     for n in spec["source_lines"]]}).encode()
    (directory / "history.json").write_bytes(history)
    return {"candidate_id": case, "editable_files": ["source.txt"],
            "boundary_timestamp": "2026-10-01T00:00:00Z", "source_prefix_sha256": "a" * 64,
            "history_sha256": digest(history), "tree_manifest_sha256": digest(manifest)}


def test_preparation_repeats_exact_bytes_and_keeps_private_material_off_both_arms(
    tmp_path, cohort,
):
    spec = next(iter(cohort.read_specs().values()))
    row = source(tmp_path, spec)
    first, second = (tmp_path / name for name in ("first", "second"))
    a = cohort.prepare_case(row, spec, tmp_path / "intake", first)
    b = cohort.prepare_case(row, spec, tmp_path / "intake", second)
    assert a == b
    assert a["source_tree_sha256"] == row["tree_manifest_sha256"]
    assert set(a["prompt_sha256"]) == {"compiled", "torc"}
    for arm, pin in a["prompt_sha256"].items():
        data = (first / "prompts" / f"{arm}.txt").read_bytes()
        assert data == (second / "prompts" / f"{arm}.txt").read_bytes()
        assert digest(data) == pin
        assert b"PRIVATE_RAW_HISTORY" not in data
        assert spec["review"][0]["question"].encode() not in data
    assert a["prompt_sha256"]["compiled"] != a["prompt_sha256"]["torc"]
    assert (first / "shared/source.txt").read_bytes() == b"interrupted\n"
    assert sorted(p.name for p in (first / "shared").iterdir()) == [
        "CONTINUATION_BRIEF.md", "source.txt",
    ]
    (tmp_path / "intake/sample/tree/source.txt").write_bytes(b"later revision")
    with pytest.raises(ValueError, match="source.txt"):
        cohort.prepare_case(row, spec, tmp_path / "intake", tmp_path / "changed")


def test_eight_review_cards_bind_specific_rows_without_candidate_answers(cohort):
    inventory = json.loads((ROOT / "docs/evidence/2026-11-20-continuation-fixtures.json")
                           .read_bytes())
    specs = cohort.read_specs()
    assert set(specs) == {row["candidate_id"] for row in inventory["candidates"]}
    for spec in specs.values():
        assert len(spec["review"]) >= 2
        assert all(spec[key].endswith("?") for key in ("usable", "preference", "reason"))
        for row in spec["review"]:
            assert set(row) == {"label", "expected", "question"}
            assert row["question"].endswith("?") and row["expected"] and row["label"]
    assert "wow_helper/character.py" in specs["wow-context-channel"]["additional_editable_files"]
