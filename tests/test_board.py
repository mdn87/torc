import hashlib
import json
from pathlib import Path

import pytest

from torc import board
from torc.cli import main
from torc.errors import InvalidInputError


def test_workspace_location_and_offering_do_not_change_authority(tmp_path, monkeypatch, capsys):
    home = tmp_path / "board-home"
    monkeypatch.setenv("TORC_BOARD_HOME", str(home))
    assert main(["board", "workspace", "--project", "p:one", "--json"]) == 0
    where = json.loads(capsys.readouterr().out)
    assert where["lineage_id"] == "board-p:one"
    assert Path(where["state_dir"]) == home / "workspaces" / hashlib.sha256(b"p:one").hexdigest()
    assert not home.exists()
    examples = Path(__file__).resolve().parents[1] / "examples"
    args = ["--state-dir", where["state_dir"], "--lineage", where["lineage_id"]]
    assert (
        main(
            [
                "lineage",
                "create",
                *args,
                "--state-file",
                str(examples / "p2-canonical-state.json"),
                "--substrate-file",
                str(examples / "p2-source-substrate.json"),
                "--json",
            ]
        )
        == 0
    )
    created = json.loads(capsys.readouterr().out)
    assert main(["board", "offer", *args, "--label", "Release review", "--json"]) == 0
    offer = json.loads(capsys.readouterr().out)
    record = json.loads((home / "offers" / (offer["source_id"] + ".json")).read_text())
    assert record["label"] == "Release review"
    assert json.loads(Path(record["holderFile"]).read_text())["holderTag"]
    assert main(["lineage", "status", *args, "--json"]) == 0
    assert created["activation_id"] in capsys.readouterr().out


def test_workspace_resolution_stops_at_a_nested_repository(tmp_path, monkeypatch):
    exchange = tmp_path / ".dias"
    exchange.mkdir()
    (exchange / "status.json").write_text('{"projectId":"atlas"}')
    sub = tmp_path / "code"
    sub.mkdir()
    monkeypatch.chdir(sub)
    assert board._here() == "atlas"
    (exchange / "chips.json").write_text('{"projectId":"other"}')
    with pytest.raises(InvalidInputError, match="disagree"):
        board._here()
    (sub / ".git").mkdir()
    with pytest.raises(InvalidInputError, match="no Board ID"):
        board._here()


def test_named_trail_resolves_only_one_real_board(monkeypatch):
    objective = {"namespace": "team", "id": "release", "label": "Release review"}
    feed = {"source_status": "current", "model": {"objectives": [objective]}}
    links = {"links": [{"objective": "team/release", "projectId": "atlas"}]}
    monkeypatch.setattr(
        board, "_request", lambda port, route: {"trails": feed, "project-trail-links": links}[route]
    )
    boards = [{"projectId": "atlas"}]
    assert board._trail_board(4175, "Release review", boards) == "atlas"
    feed["model"]["objectives"].append({**objective, "namespace": "another"})
    with pytest.raises(InvalidInputError, match="team/release"):
        board._trail_board(4175, "Release review", boards)
    objective["content"] = {
        "links": [
            {"relation": "annotates_chip", "to": {"store_id": key}} for key in ("atlas", "another")
        ]
    }
    with pytest.raises(InvalidInputError, match="single linked Board"):
        board._trail_board(4175, "team/release", boards)
