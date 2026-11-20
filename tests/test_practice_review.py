"""Human practice judgments remain blind, durable, and tied to what was reviewed."""

import copy
import importlib
import json
import sqlite3
from contextlib import closing
from pathlib import Path

import pytest

from torc.canonical import payload_sha256

APP = Path(__file__).resolve().parents[1] / "experiments/continuation-review"


@pytest.fixture
def app(monkeypatch):
    monkeypatch.syspath_prepend(str(APP))
    return importlib.import_module("practice_review")


def test_review_resumes_exact_display_and_attributed_answers(app, tmp_path):
    path = tmp_path / "practice.sqlite3"
    source = json.loads((APP / "practice.json").read_text(encoding="utf-8"))
    store = app.ReviewStore(path, "UI test", source)
    batch = store.view()
    assert batch["mode"] == "practice"
    assert len(batch["cards"]) == 2
    card = batch["cards"][0]
    answers = {**card["answers"], "A": {"request": "Partly"}}
    saved = store.save(card["id"], card["binding"], 0, answers, submit=False)
    assert saved["revision"] == 1
    reopened = app.ReviewStore(path, "UI test", source)
    assert reopened.view()["cards"][0] == {**card, **saved}
    with pytest.raises(app.Conflict):
        reopened.save(card["id"], card["binding"], 0, card["answers"], submit=False)
    with pytest.raises(app.Conflict):
        reopened.save(card["id"], "changed", 1, answers, submit=False)
    export = reopened.view(history=True)
    assert export["cards"][0]["history"][0]["reviewer"] == "UI test"
    assert export["cards"][0]["history"][0]["binding"] == card["binding"]
    assert card["artifact_sha256"] == {
        side: payload_sha256(result) for side, result in card["results"].items()
    }
    assert export["rubric_sha256"] == payload_sha256(batch["rubric"])
    with pytest.raises(app.Conflict):
        app.ReviewStore(path, "Another reviewer", source)
    for field in ("rubric", "cards"):
        changed = copy.deepcopy(source)
        if field == "rubric":
            changed["rubric"]["criteria"][0]["question"] += " Changed."
        else:
            changed["cards"][0]["variants"][0]["output"] += " Changed."
        with pytest.raises(app.Conflict):
            app.ReviewStore(path, "UI test", changed)
    with closing(sqlite3.connect(path)) as db, db:
        snapshot = json.loads(db.execute("SELECT snapshot FROM batch").fetchone()[0])
        snapshot["cards"][0]["results"]["A"]["output"] += " Altered display."
        db.execute("UPDATE batch SET snapshot = ?", (json.dumps(snapshot),))
    with pytest.raises(app.Conflict, match="evidence has changed"):
        app.ReviewStore(path, "UI test", source)


@pytest.mark.parametrize("flip", [0, 1])
def test_random_sides_only_expose_review_evidence(app, tmp_path, monkeypatch, flip):
    source = json.loads((APP / "practice.json").read_text(encoding="utf-8"))
    monkeypatch.setattr(app.secrets, "randbelow", lambda _: flip)
    item = source["cards"][0]
    item["private_mapping"] = "private-marker"
    for result in item["variants"]:
        result.update(arm="private-marker", automated_correctness="private-marker",
                      tokens="private-marker", cost="private-marker")
    store = app.ReviewStore(tmp_path / "blind.db", "UI test", source)
    for history in (False, True):
        view = store.view(history=history)
        assert "private-marker" not in json.dumps(view)
        card = view["cards"][0]
        assert card["results"]["A"]["output"] == item["variants"][flip]["output"]
        assert card["results"]["B"]["output"] == item["variants"][1 - flip]["output"]


def test_submissions_revisions_and_lock(app, tmp_path):
    source = json.loads((APP / "practice.json").read_text(encoding="utf-8"))
    store = app.ReviewStore(tmp_path / "reviews.db", "UI test", source)
    batch = store.view()
    ratings = {row["id"]: "Cannot judge" for row in batch["rubric"]["criteria"]}
    complete = {"A": ratings, "B": ratings, "preference": "Insufficient evidence",
                "reason": "Automated form check."}
    revisions = {}
    for card in batch["cards"]:
        args = card["id"], card["binding"]
        for incomplete in ({"A": {}}, {"preference": ""}, {"reason": " "}, {"B": {"extra": "Yes"}}):
            with pytest.raises(ValueError):
                store.save(*args, 0, {**complete, **incomplete}, submit=True)
        with pytest.raises(ValueError, match="Submit both"):
            store.lock(batch["batch_id"], revisions)
        first = store.save(*args, 0, complete, submit=True)
        assert store.save(*args, 0, complete, submit=True) == first
        revised = {**complete, "reason": "Automated form revision."}
        store.save(*args, 1, revised, submit=False)
        revisions[card["id"]] = store.save(*args, 2, revised, submit=True)["revision"]
    with pytest.raises(app.Conflict):
        store.lock(batch["batch_id"], dict.fromkeys(revisions, 1))
    assert store.lock(batch["batch_id"], revisions)["locked_at"]
    with pytest.raises(app.Conflict, match="locked"):
        store.save(*args, 3, complete, submit=False)
    for card in store.view(history=True)["cards"]:
        assert [row["status"] for row in card["history"]] == ["submitted", "draft", "submitted"]
        assert [row["revision"] for row in card["history"]] == [1, 2, 3]
        assert all(row["binding"] == card["binding"] for row in card["history"])
