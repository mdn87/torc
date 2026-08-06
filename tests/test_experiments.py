from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from torc.canonical import canonical_json, payload_sha256
from torc.cli import _inspect_experiment, main
from torc.errors import TorcError
from torc.experiment_adapters import CodexSourceAdapter
from torc.experiment_lanes import record_torc_reconstruction
from torc.experiment_runs import (
    append_target_attempt,
    build_visible_workspace,
    load_run,
    scan_artifacts_for_credentials,
    verify_experiment_run,
    write_canonical_artifact,
    write_stage_receipt,
)
from torc.experiment_scoring import score_run
from torc.store import Store

ROOT = Path(__file__).resolve().parents[1]
MANIFEST = ROOT / "examples" / "experiment-manifest.example.json"
FIXED_TIME = "2026-08-06T12:10:00Z"


def _command(*args: object) -> int:
    return main([str(arg) for arg in args])


def _prepare_source(run_dir: Path, lane: str = "compiled-prompt") -> None:
    assert (
        _command(
            "experiment",
            "prepare",
            "--manifest",
            MANIFEST,
            "--lane",
            lane,
            "--run-dir",
            run_dir,
            "--json",
        )
        == 0
    )
    assert (
        _command(
            "experiment",
            "source",
            "--run-dir",
            run_dir,
            "--adapter",
            "replay",
            "--json",
        )
        == 0
    )


def _complete(run_dir: Path, lane: str = "compiled-prompt") -> None:
    _prepare_source(run_dir, lane)
    assert (
        _command(
            "experiment",
            "target",
            "--run-dir",
            run_dir,
            "--adapter",
            "replay",
            "--json",
        )
        == 0
    )
    assert (
        _command("experiment", "score", "--run-dir", run_dir, "--json") == 0
    )
    assert (
        _command("experiment", "verify", "--run-dir", run_dir, "--json") == 0
    )


def test_replay_compiled_prompt_run_completes_and_verifies(tmp_path: Path) -> None:
    run_dir = tmp_path / "lane-a"
    _complete(run_dir)
    result = verify_experiment_run(run_dir)
    assert result["valid"]
    assert result["disposition"] == "accepted"
    assert (run_dir / "receipts" / "target-completed.json").is_file()


def test_inspect_emits_versioned_experiment_run_contract(tmp_path: Path) -> None:
    run_dir = tmp_path / "lane-a"
    _complete(run_dir)
    schema = json.loads(
        (ROOT / "schemas" / "experiment-run.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema).validate(_inspect_experiment(run_dir))


def test_replay_native_persistence_unavailable_run_completes_and_verifies(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "lane-b"
    _prepare_source(run_dir, "native-persistence")
    result = verify_experiment_run(run_dir)
    assert result["valid"]
    assert result["disposition"] == "unavailable"
    assert not (run_dir / "attempts").exists()
    assert not (run_dir / "artifacts" / "score-report.json").exists()


def test_replay_torc_run_transfers_only_after_reconstruction(tmp_path: Path) -> None:
    run_dir = tmp_path / "lane-c"
    _prepare_source(run_dir, "torc")
    with Store(run_dir / "torc-state") as store:
        assert store.current_authority("p1a-lineage")["activation_id"] == (
            "p1a-source-activation"
        )
    assert (
        _command(
            "experiment",
            "target",
            "--run-dir",
            run_dir,
            "--adapter",
            "replay",
            "--json",
        )
        == 0
    )
    with Store(run_dir / "torc-state") as store:
        assert store.current_authority("p1a-lineage")["activation_id"] == (
            "p1a-target-attempt-0001"
        )
    assert _command("experiment", "score", "--run-dir", run_dir, "--json") == 0
    assert _command("experiment", "verify", "--run-dir", run_dir, "--json") == 0


def test_rejected_torc_reconstruction_preserves_source_authority(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "lane-c-rejected"
    _prepare_source(run_dir, "torc")
    result = record_torc_reconstruction(
        load_run(run_dir),
        {
            "attempt_id": "attempt-rejected",
            "started_at": "2026-08-06T12:07:00Z",
            "ended_at": "2026-08-06T12:08:00Z",
        },
        {"lineage_identity": "wrong"},
    )
    assert result["disposition"] == "rejected"
    with Store(run_dir / "torc-state") as store:
        assert store.current_authority("p1a-lineage")["activation_id"] == (
            "p1a-source-activation"
        )


def test_fixed_clock_replay_produces_identical_payload_and_score_report_bytes(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first"
    second = tmp_path / "second"
    for run_dir in (first, second):
        _prepare_source(run_dir)
        assert (
            _command(
                "experiment",
                "target",
                "--run-dir",
                run_dir,
                "--adapter",
                "replay",
                "--json",
            )
            == 0
        )
    assert (first / "artifacts" / "continuity-payload.json").read_bytes() == (
        second / "artifacts" / "continuity-payload.json"
    ).read_bytes()
    def clock() -> str:
        return FIXED_TIME

    first_report = score_run(first, clock=clock)
    second_report = score_run(second, clock=clock)
    assert canonical_json(first_report) == canonical_json(second_report)
    assert first_report["score_core_sha256"] == payload_sha256(
        first_report["score_core"]
    )


def test_score_core_excludes_operational_measurements(tmp_path: Path) -> None:
    run_dir = tmp_path / "lane-a"
    _prepare_source(run_dir)
    assert (
        _command(
            "experiment",
            "target",
            "--run-dir",
            run_dir,
            "--adapter",
            "replay",
            "--json",
        )
        == 0
    )
    first = score_run(run_dir, clock=lambda: FIXED_TIME)
    second = score_run(run_dir, clock=lambda: "2026-08-06T13:00:00Z")
    second["operational_measurements"]["operator_steps"] = 99
    assert first["score_core"] == second["score_core"]
    assert first["score_core_sha256"] == second["score_core_sha256"]


def test_target_workspace_excludes_oracle_and_scoring_material(
    tmp_path: Path,
) -> None:
    run_dir = tmp_path / "lane-a"
    _prepare_source(run_dir)
    assert (
        _command(
            "experiment",
            "target",
            "--run-dir",
            run_dir,
            "--adapter",
            "replay",
            "--json",
        )
        == 0
    )
    paths = {
        path.relative_to(run_dir / "workspaces" / "target").as_posix()
        for path in (run_dir / "workspaces" / "target").rglob("*")
        if path.is_file()
    }
    assert paths == {
        "continuity-payload.json",
        "task.json",
        "visible-workspace-manifest.json",
    }


def test_identical_stage_retry_is_idempotent(tmp_path: Path) -> None:
    run_dir = tmp_path / "lane-a"
    _prepare_source(run_dir)
    before = (run_dir / "receipts" / "payload-frozen.json").read_bytes()
    _prepare_source(run_dir)
    assert (run_dir / "receipts" / "payload-frozen.json").read_bytes() == before


def test_target_and_score_retries_are_idempotent(tmp_path: Path) -> None:
    run_dir = tmp_path / "lane-a"
    _complete(run_dir)
    attempts_before = list((run_dir / "attempts").iterdir())
    score_before = (run_dir / "artifacts" / "score-report.json").read_bytes()
    assert (
        _command(
            "experiment",
            "target",
            "--run-dir",
            run_dir,
            "--adapter",
            "replay",
            "--json",
        )
        == 0
    )
    assert _command("experiment", "score", "--run-dir", run_dir, "--json") == 0
    assert list((run_dir / "attempts").iterdir()) == attempts_before
    assert (run_dir / "artifacts" / "score-report.json").read_bytes() == score_before


def test_changed_stage_input_requires_new_run(tmp_path: Path) -> None:
    root = tmp_path / "run"
    inputs = [{"path": "a.json", "sha256": "a" * 64}]
    write_stage_receipt(root, "created", inputs, [], clock=lambda: FIXED_TIME)
    with pytest.raises(TorcError, match="create a new run"):
        write_stage_receipt(
            root,
            "created",
            [{"path": "a.json", "sha256": "b" * 64}],
            [],
            clock=lambda: FIXED_TIME,
        )


def test_failed_target_attempt_is_preserved(tmp_path: Path) -> None:
    root = tmp_path / "run"
    first = {
        "attempt_id": "attempt-0001",
        "record": {
            "attempt_id": "attempt-0001",
            "payload_sha256": "a" * 64,
            "disposition": "failed",
        },
        "target_output": {"error": "interrupted"},
        "reconstruction": {},
    }
    second = {
        "attempt_id": "attempt-0002",
        "record": {
            "attempt_id": "attempt-0002",
            "payload_sha256": "a" * 64,
            "disposition": "accepted",
        },
        "target_output": {"completion_status": "complete"},
        "reconstruction": {"completion_status": "complete"},
    }
    append_target_attempt(root, first, clock=lambda: FIXED_TIME)
    append_target_attempt(root, second, clock=lambda: FIXED_TIME)
    assert (root / "attempts" / "attempt-0001" / "attempt.json").is_file()
    assert (root / "attempts" / "attempt-0002" / "attempt.json").is_file()


def test_changed_payload_cannot_reuse_run(tmp_path: Path) -> None:
    run_dir = tmp_path / "lane-a"
    _prepare_source(run_dir)
    assert (
        _command(
            "experiment",
            "target",
            "--run-dir",
            run_dir,
            "--adapter",
            "replay",
            "--json",
        )
        == 0
    )
    payload_path = run_dir / "artifacts" / "continuity-payload.json"
    payload = json.loads(payload_path.read_text(encoding="utf-8"))
    payload["mechanism"] = "changed"
    write_canonical_artifact(payload_path, payload)
    assert (
        _command(
            "experiment",
            "target",
            "--run-dir",
            run_dir,
            "--adapter",
            "replay",
            "--json",
        )
        == 1
    )


def test_path_escape_and_case_collision_are_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n", encoding="utf-8")
    with pytest.raises(TorcError, match="escapes"):
        build_visible_workspace(tmp_path / "run", "target", [(source, "../x.json")])
    with pytest.raises(TorcError, match="case-colliding"):
        build_visible_workspace(
            tmp_path / "run-2",
            "target",
            [(source, "Task.json"), (source, "task.json")],
        )


def test_environment_dump_is_rejected(tmp_path: Path) -> None:
    source = tmp_path / "source.json"
    source.write_text("{}\n", encoding="utf-8")
    with pytest.raises(TorcError, match="runner-only"):
        build_visible_workspace(
            tmp_path / "run", "target", [(source, "environment.json")]
        )


def test_credential_scans_are_redacted_and_clean_runs_pass(tmp_path: Path) -> None:
    planted = tmp_path / "planted"
    planted.mkdir()
    (planted / "artifact.txt").write_text(
        "api_key=not-a-real-fixture-secret\n", encoding="utf-8"
    )
    findings = scan_artifacts_for_credentials(planted)
    assert findings == [
        {"path": "artifact.txt", "finding": "credential-like pattern"}
    ]
    run_dir = tmp_path / "clean"
    _complete(run_dir)
    assert scan_artifacts_for_credentials(run_dir) == []


@pytest.mark.parametrize(
    "relative",
    (
        "manifest.json",
        "artifacts/continuity-payload.json",
        "attempts/attempt-0001/attempt.json",
        "attempts/attempt-0001/reconstruction.json",
        "artifacts/score-report.json",
        "receipts/scored.json",
        "workspaces/target/visible-workspace-manifest.json",
        "artifacts/artifact-manifest.json",
    ),
)
def test_artifact_tampering_is_detected(tmp_path: Path, relative: str) -> None:
    run_dir = tmp_path / "lane-a"
    _complete(run_dir)
    path = run_dir / relative
    path.write_bytes(path.read_bytes() + b" ")
    result = verify_experiment_run(run_dir)
    assert not result["valid"]
    assert any("mismatch" in error for error in result["errors"])


def test_unmanifested_artifact_is_detected(tmp_path: Path) -> None:
    run_dir = tmp_path / "lane-a"
    _complete(run_dir)
    (run_dir / "artifacts" / "extra.json").write_text("{}\n", encoding="utf-8")
    result = verify_experiment_run(run_dir)
    assert not result["valid"]
    assert "unmanifested artifact: artifacts/extra.json" in result["errors"]


def test_adapter_mismatch_fails_before_invocation(tmp_path: Path) -> None:
    manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
    manifest["adapters"]["source"] = ["codex"]
    custom = ROOT / "examples" / "experiment-manifest.example.json"
    run_dir = tmp_path / "mismatch"
    assert (
        _command(
            "experiment",
            "prepare",
            "--manifest",
            custom,
            "--lane",
            "compiled-prompt",
            "--run-dir",
            run_dir,
            "--json",
        )
        == 0
    )
    frozen = json.loads((run_dir / "manifest.json").read_text(encoding="utf-8"))
    frozen["adapters"]["source"] = ["codex"]
    write_canonical_artifact(run_dir / "manifest.json", frozen)
    assert (
        _command(
            "experiment",
            "source",
            "--run-dir",
            run_dir,
            "--adapter",
            "replay",
            "--json",
        )
        == 1
    )


def test_live_probe_uses_argument_list_without_shell(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    calls = []

    class Completed:
        returncode = 0
        stdout = "codex 1.0"
        stderr = ""

    monkeypatch.setattr("torc.experiment_adapters.shutil.which", lambda _name: "codex")

    def fake_run(args: list[str], **kwargs: object) -> Completed:
        calls.append((args, kwargs))
        return Completed()

    monkeypatch.setattr("torc.experiment_adapters.subprocess.run", fake_run)
    context = {
        "source_workspace": tmp_path,
        "source_allowed_paths": ["task.json"],
    }
    evidence = CodexSourceAdapter().probe(context, "source")
    assert evidence["boundary_enforced"] is False
    assert calls[0][0] == ["codex", "--version"]
    assert "shell" not in calls[0][1]
    capture = CodexSourceAdapter().capture_source(context)
    assert capture["disposition"] == "contaminated"
