from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments" / "cross-agent-collaboration-001"
sys.path.insert(0, str(EXPERIMENT))
import workflow_runner as workflow  # noqa: E402


def _record(
    provider: str,
    role: str,
    session_mode: str,
    session_id: str | None,
) -> dict[str, Any]:
    return {
        "provider": provider,
        "role": role,
        "tool_mode": "none",
        "session": {
            "mode": session_mode,
            "requested_id": session_id,
            "observed_id": session_id or "session-observed",
        },
        "usage": {
            "schema_version": 1,
            "source": provider,
            "supplied": False,
            "input_tokens": None,
            "cached_input_tokens": None,
            "cache_write_input_tokens": None,
            "reasoning_output_tokens": None,
            "output_tokens": None,
            "reported_fields": [],
            "unreported_fields": [
                "input_tokens",
                "cached_input_tokens",
                "cache_write_input_tokens",
                "reasoning_output_tokens",
                "output_tokens",
            ],
            "provider_usage": {},
        },
        "timing": {
            "startup_ms": 1.0,
            "time_to_first_output_ms": 2.0,
            "completion_ms": 3.0,
        },
    }


def _solution_artifact() -> dict[str, Any]:
    return {
        "schema_version": 1,
        "changes": [
            {
                "path": "header_merge.py",
                "content": """from collections.abc import Mapping


def merge_headers(defaults: Mapping[str, str], overrides: Mapping[str, str]) -> dict[str, str]:
    order: list[str] = []
    values: dict[str, tuple[str, str]] = {}
    for source in (defaults, overrides):
        for name, value in source.items():
            identity = name.lower()
            if identity not in values:
                order.append(identity)
            values[identity] = (name, value)
    return {values[identity][0]: values[identity][1] for identity in order}
""",
            }
        ],
        "summary": "Merge headers case-insensitively while preserving first position.",
        "test_plan": ["python -m pytest -q"],
    }


def _write_worker_output(
    provider: str, output_dir: Path, value: dict[str, Any]
) -> None:
    output_dir.mkdir(parents=True)
    if provider == "codex":
        event = {
            "type": "item.completed",
            "item": {"type": "agent_message", "text": json.dumps(value)},
        }
    else:
        event = {
            "type": "result",
            "result": json.dumps(value),
            "session_id": "critic-session",
        }
    (output_dir / "stdout.jsonl").write_text(
        json.dumps(event) + "\n", encoding="utf-8"
    )


def test_workflow_plans_make_call_cost_explicit() -> None:
    manifest = workflow.load_manifest()

    solo = workflow.workflow_plan(manifest, "bug-hidden-regression", "codex-solo")
    native_review = workflow.workflow_plan(
        manifest, "bug-hidden-regression", "codex-review"
    )
    cross = workflow.workflow_plan(manifest, "bug-hidden-regression", "codex-claude")

    assert solo["model_call_count"] == 1
    assert solo["phases"] == ["codex"]
    assert solo["worker_interface"] == "patch-artifact-v1"
    assert native_review["model_call_count"] == 3
    assert native_review["model_call_count_range"] == [2, 3]
    assert native_review["revision_policy"] == "changes_requested_only"
    assert native_review["phases"] == ["codex", "codex", "codex"]
    assert cross["model_call_count"] == 3
    assert cross["phases"] == ["codex", "claude-code", "codex"]


def test_claim_capsule_accepts_known_citations_and_rejects_unknown() -> None:
    capsule, control = workflow._compile_handoff(
        "refactor-superseded-path",
        "run-1",
        "revision-1",
        "codex/gpt-6-sol",
    )
    critique = {
        "schema_version": 1,
        "verdict": "changes_requested",
        "findings": [
            {
                "finding_id": "f1",
                "severity": "blocking",
                "summary": "Dispatch still uses the superseded path.",
                "evidence": "routing.py:20",
                "claim_ids": ["s1", "c1"],
            }
        ],
    }

    resolved = workflow._validate_critique(critique, control)

    assert set(resolved) == {"s1", "c1"}
    assert workflow._claim_text(capsule, "s1").startswith("legacy_route")
    critique["findings"][0]["claim_ids"] = ["missing1"]
    with pytest.raises(workflow.WorkflowRunnerError, match="invalid claim"):
        workflow._validate_critique(critique, control)


def test_solo_workflow_scores_without_model_synthesis(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = workflow.load_manifest()
    monkeypatch.setattr(workflow, "_apparatus_revision", lambda: "a" * 40)

    def fake_worker(**kwargs: Any) -> dict[str, Any]:
        _write_worker_output(
            kwargs["settings"]["provider"],
            kwargs["output_dir"],
            _solution_artifact(),
        )
        return _record(
            kwargs["settings"]["provider"],
            kwargs["role"],
            kwargs["session_mode"],
            kwargs["session_id"],
        )

    monkeypatch.setattr(workflow, "_run_worker", fake_worker)
    result = workflow.run_workflow(
        manifest=manifest,
        fixture_id="bug-hidden-regression",
        workflow_id="codex-solo",
        run_dir=tmp_path / "solo-run",
    )

    assert result["accepted_final"] is True
    assert result["operator_interventions"] == 0
    assert len(result["phases"]) == 1
    assert (tmp_path / "solo-run" / "final.diff").is_file()


def test_cross_workflow_uses_capsule_critic_and_same_session_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = workflow.load_manifest()
    monkeypatch.setattr(workflow, "_apparatus_revision", lambda: "b" * 40)
    calls: list[dict[str, Any]] = []

    def fake_worker(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        output_dir = kwargs["output_dir"]
        provider = kwargs["settings"]["provider"]
        if kwargs["role"] == "implementer" and kwargs["session_mode"].startswith(
            "fresh"
        ):
            output = _solution_artifact()
        elif kwargs["role"] == "critic":
            output = {
                "schema_version": 1,
                "verdict": "changes_requested",
                "findings": [
                    {
                        "finding_id": "f1",
                        "severity": "blocking",
                        "summary": "Recheck case-insensitive identity.",
                        "evidence": "header_merge.py",
                        "claim_ids": ["x1"],
                    }
                ],
            }
        else:
            output = {
                "schema_version": 1,
                "changes": [],
                "summary": "The approved candidate needs no further changes.",
                "test_plan": ["python -m pytest -q"],
            }
        _write_worker_output(provider, output_dir, output)
        session_id = kwargs["session_id"] or "primary-session"
        return _record(provider, kwargs["role"], kwargs["session_mode"], session_id)

    monkeypatch.setattr(workflow, "_run_worker", fake_worker)
    result = workflow.run_workflow(
        manifest=manifest,
        fixture_id="bug-hidden-regression",
        workflow_id="codex-claude",
        run_dir=tmp_path / "cross-run",
    )

    assert result["accepted_after_primary"] is True
    assert result["accepted_final"] is True
    assert result["critic_verdict"] == "changes_requested"
    assert result["revision_performed"] is True
    assert [call["role"] for call in calls] == ["implementer", "critic", "implementer"]
    assert calls[2]["session_mode"] == "resume"
    assert calls[2]["session_id"] == "primary-session"
    assert (tmp_path / "cross-run" / "claim-control-envelope.json").is_file()
    assert (tmp_path / "cross-run" / "candidate.diff").is_file()
    assert (tmp_path / "cross-run" / "final.diff").is_file()


def test_approved_critique_skips_revision(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    manifest = workflow.load_manifest()
    monkeypatch.setattr(workflow, "_apparatus_revision", lambda: "c" * 40)
    calls: list[dict[str, Any]] = []

    def fake_worker(**kwargs: Any) -> dict[str, Any]:
        calls.append(kwargs)
        provider = kwargs["settings"]["provider"]
        output = (
            {"schema_version": 1, "verdict": "approve", "findings": []}
            if kwargs["role"] == "critic"
            else _solution_artifact()
        )
        _write_worker_output(provider, kwargs["output_dir"], output)
        session_id = kwargs["session_id"] or "primary-session"
        return _record(provider, kwargs["role"], kwargs["session_mode"], session_id)

    monkeypatch.setattr(workflow, "_run_worker", fake_worker)
    result = workflow.run_workflow(
        manifest=manifest,
        fixture_id="bug-hidden-regression",
        workflow_id="codex-review",
        run_dir=tmp_path / "approved-run",
    )

    assert len(calls) == 2
    assert result["revision_performed"] is False
    assert result["revision_skipped_reason"] == "critic_approved"
    assert result["accepted_final"] is True
    assert (tmp_path / "approved-run" / "revision-skipped.json").is_file()
    assert not (tmp_path / "approved-run" / "revision-artifact.json").exists()


def test_patch_artifact_rejects_unfrozen_paths(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "allowed.py").write_text("old\n", encoding="utf-8")
    artifact = {
        "schema_version": 1,
        "changes": [{"path": "tests/test_hidden.py", "content": "pass\n"}],
        "summary": "Attempted test edit.",
        "test_plan": ["pytest"],
    }

    with pytest.raises(workflow.WorkflowRunnerError, match="unauthorized"):
        workflow._apply_patch_artifact(workspace, artifact, ["allowed.py"])
