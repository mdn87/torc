"""Native context and results cross a strict boundary without running a model."""

import json
from copy import deepcopy

import pytest
from test_mirror import BINDING, LATER, NOW, signal

from torc.cli import main
from torc.errors import InvalidInputError
from torc.mirror import resolve_settings, validate_delivery


def sidecar():
    facts = [
        {"id": "outcome", "kind": "outcome", "text": "The requested work is unfinished."},
        {"id": "verification", "kind": "verification", "text": "No checks have run."},
        {"id": "limit", "kind": "limitation", "text": "The required source is unavailable."},
        {"id": "next", "kind": "next_action", "text": "Provide the source to continue."},
    ]
    return {
        "written": "\n".join(fact["text"] for fact in facts),
        "result": {"status": "blocked", "verification": "not_run", "facts": facts},
    }


def project_request(**changes):
    native = sidecar()
    return {
        "settings": resolve_settings(BINDING, [], now=NOW), "binding": BINDING,
        "signals": [], "sidecar": native, "written": native["written"],
        "response_id": "native-message-1", "now": LATER, **changes,
    }


def invoke(tmp_path, capsys, action, data, expected=0):
    request = tmp_path / "request.json"
    request.write_text(json.dumps(data), encoding="utf-8")
    assert main(["mirror", action, "--input-file", str(request), "--json"]) == expected
    return json.loads(capsys.readouterr().out)


def test_cli_prepares_context_without_writing_sidecar(tmp_path, capsys):
    destination = tmp_path / "native result.json"
    prepared = invoke(tmp_path, capsys, "prepare", {
        "binding": BINDING, "signals": [signal("turn_length", "brief")],
        "now": NOW, "sidecar_path": str(destination),
    })
    assert set(prepared) == {"settings", "context"}
    assert prepared["settings"]["values"]["turn_length"] == "brief"
    context = prepared["context"]
    assert prepared["settings"]["settings_id"] in context
    assert json.dumps(str(destination)) in context
    assert "No setting grants approval" in context
    assert "exactly the written string" in context
    assert "not_run" in context and "instruction" in context
    assert not destination.exists()


def test_cli_renews_expired_settings_without_relabeling_original(tmp_path, capsys):
    data = project_request()
    original = deepcopy(data)
    response = invoke(tmp_path, capsys, "native-project", data)
    assert set(response) == {"delivery", "settings", "prior_settings_id"}
    assert response["prior_settings_id"] == original["settings"]["settings_id"]
    assert response["settings"]["settings_id"] != response["prior_settings_id"]
    assert response["settings"]["issued_at"] == LATER
    assert response["delivery"]["settings_id"] == response["settings"]["settings_id"]
    assert response["delivery"]["result"] == original["sidecar"]["result"]
    assert response["delivery"]["written"] == original["written"]
    assert data == original
    validate_delivery(response["delivery"], binding=BINDING,
                      response_id=data["response_id"], written=data["written"], now=LATER)


def test_renewal_recomputes_expired_signal_provenance():
    from torc.mirror_native import project_native

    signals = [signal("turn_length", "brief")]
    settings = resolve_settings(BINDING, signals, now=NOW)
    response = project_native(**project_request(settings=settings, signals=signals))
    assert settings["values"]["turn_length"] == "brief"
    assert response["settings"]["values"]["turn_length"] == "normal"
    assert response["settings"]["provenance"]["turn_length"]["kind"] == "default"


@pytest.mark.parametrize("changes", [
    {"binding": {**BINDING, "task_id": "different"}},
    {"binding": {**BINDING, "turn_id": "superseding-turn"}},
    {"binding": {**BINDING, "response_revision": 2}},
    {"written": sidecar()["written"] + "\n"},
    {"written": "A different native response."},
    {"sidecar": {**sidecar(), "binding": BINDING}},
    {"signals": [{"setting": "turn_length", "value": "brief"}]},
    {"settings": []},
    {"now": "2026-11-06T11:00:00Z"},
    {"ttl_seconds": 0},
])
def test_cli_rejects_invalid_native_boundaries(tmp_path, capsys, changes):
    error = invoke(tmp_path, capsys, "native-project", project_request(**changes), expected=1)
    assert error["ok"] is False


def test_rejects_tampered_old_settings_even_after_expiry():
    from torc.mirror_native import project_native

    data = project_request()
    data["settings"]["values"]["turn_length"] = "brief"
    with pytest.raises(InvalidInputError, match="digest"):
        project_native(**data)


@pytest.mark.parametrize("path", [None, "", "unsafe\npath", "unsafe\x00path"])
def test_rejects_invalid_sidecar_paths(path):
    from torc.mirror_native import prepare_native

    with pytest.raises(InvalidInputError, match="sidecar path"):
        prepare_native(BINDING, [], now=NOW, sidecar_path=path)
