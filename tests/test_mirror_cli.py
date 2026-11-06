import json

from test_mirror import BINDING, NOW, result, signal

from torc.cli import main


def test_cli_resolves_projects_and_renders_one_bound_response(tmp_path, capsys):
    request = tmp_path / "request.json"
    request.write_text(json.dumps({
        "binding": BINDING, "signals": [signal("turn_length", "brief")], "now": NOW,
    }), encoding="utf-8")
    assert main(["mirror", "resolve", "--input-file", str(request), "--json"]) == 0
    settings = json.loads(capsys.readouterr().out)
    request.write_text(json.dumps({
        "settings": settings, "binding": BINDING, "now": NOW,
    }), encoding="utf-8")
    assert main(["mirror", "context", "--input-file", str(request), "--json"]) == 0
    assert "turn_length: brief" in json.loads(capsys.readouterr().out)["text"]
    facts = result()
    written = "\n\n".join(fact["text"] for fact in facts["facts"])
    request.write_text(json.dumps({
        "settings": settings, "result": facts, "written": written,
        "response_id": "reply-2", "now": NOW,
    }), encoding="utf-8")
    assert main(["mirror", "project", "--input-file", str(request), "--json"]) == 0
    delivery = json.loads(capsys.readouterr().out)
    request.write_text(json.dumps({
        "delivery": delivery, "binding": BINDING, "response_id": "reply-2", "now": NOW,
    }), encoding="utf-8")
    assert main(["mirror", "text", "--input-file", str(request), "--json"]) == 0
    assert json.loads(capsys.readouterr().out)["text"] == written


def test_cli_malformed_input_returns_structured_error(tmp_path, capsys):
    request = tmp_path / "bad.json"
    request.write_text('{"binding": []}', encoding="utf-8")
    assert main(["mirror", "resolve", "--input-file", str(request), "--json"]) == 1
    assert json.loads(capsys.readouterr().out)["ok"] is False
