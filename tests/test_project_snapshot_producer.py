from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from torc.artifacts.producer import CommandProjectSnapshotProducer, ProducerError
from torc.cli import main

ROOT = Path(__file__).resolve().parents[1]
SCHEMAS = ROOT / "schemas"
FIXTURES = ROOT / "fixtures" / "project-snapshot"


def _load(name: str) -> dict[str, object]:
    value = json.loads((FIXTURES / name).read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _producer_script(tmp_path: Path) -> Path:
    script = tmp_path / "scribe_fixture.py"
    script.write_text(
        """\
import json
import sys

bundle = json.load(sys.stdin)
expected_bundle_id = sys.argv[1]
if bundle["bundle_id"] != expected_bundle_id:
    raise SystemExit(9)
with open(sys.argv[2], encoding="utf-8") as stream:
    json.dump(json.load(stream), sys.stdout, separators=(",", ":"), sort_keys=True)
""",
        encoding="utf-8",
    )
    return script


def test_command_producer_sends_evidence_on_stdin_and_validates_candidate(
    tmp_path: Path,
) -> None:
    bundle = _load("evidence.accepted.json")
    script = _producer_script(tmp_path)
    producer = CommandProjectSnapshotProducer(
        (
            sys.executable,
            str(script),
            str(bundle["bundle_id"]),
            str(FIXTURES / "snapshot.accepted.manual.json"),
        ),
        SCHEMAS,
        timeout_seconds=5,
    )

    snapshot = producer.produce(bundle)

    assert snapshot["artifact_id"] == _load("snapshot.accepted.manual.json")["artifact_id"]
    assert snapshot["evidence_bundle"] == {"bundle_id": bundle["bundle_id"]}


def test_command_producer_rejects_non_object_json(tmp_path: Path) -> None:
    bundle = _load("evidence.accepted.json")
    script = tmp_path / "invalid_scribe.py"
    script.write_text("print('[]')\n", encoding="utf-8")
    producer = CommandProjectSnapshotProducer(
        (sys.executable, str(script)), SCHEMAS, timeout_seconds=5
    )

    with pytest.raises(ProducerError, match="JSON object"):
        producer.produce(bundle)


def test_artifact_produce_cli_writes_validated_candidate(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    bundle = _load("evidence.accepted.json")
    evidence_path = FIXTURES / "evidence.accepted.json"
    snapshot_path = FIXTURES / "snapshot.accepted.manual.json"
    script = _producer_script(tmp_path)
    output = tmp_path / "candidate.json"

    status = main(
        [
            "artifact",
            "produce",
            "--evidence",
            str(evidence_path),
            "--out",
            str(output),
            "--timeout-seconds",
            "5",
            "--json",
            "--",
            sys.executable,
            str(script),
            str(bundle["bundle_id"]),
            str(snapshot_path),
        ]
    )

    payload = json.loads(capsys.readouterr().out)
    assert status == 0
    assert payload["artifact_id"] == _load("snapshot.accepted.manual.json")["artifact_id"]
    assert payload["path"] == str(output)
    assert json.loads(output.read_text(encoding="utf-8")) == _load(
        "snapshot.accepted.manual.json"
    )
