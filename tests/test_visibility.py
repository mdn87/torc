from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from jsonschema import Draft202012Validator, FormatChecker

from torc.branches import create_lineage_branch
from torc.canonical import utc_now
from torc.cli import main
from torc.handoffs import resolve_handoff
from torc.operator import (
    checkpoint_operator_lineage,
    create_operator_lineage,
    prepare_operator_handoff,
    prepare_operator_recovery,
    resolve_operator_handoff,
    resolve_operator_recovery,
    rollback_operator_lineage,
)
from torc.store import Store
from torc.visibility import build_lineage_explanation

ROOT = Path(__file__).resolve().parents[1]


def _validate_report(report: dict[str, Any]) -> None:
    schema = json.loads(
        (ROOT / "schemas" / "operator-view.schema.json").read_text(encoding="utf-8")
    )
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(report)


def _state(label: str) -> dict[str, Any]:
    return {
        "identity": {"label": f"Visibility lineage {label}"},
        "self_model": {
            "role": label,
            "settled_decisions": [f"decision-{label}"],
            "methods": ["derive explanations from verified provenance"],
        },
        "goals": [f"goal-{label}"],
        "commitments": ["preserve authority provenance"],
        "constraints": ["do not grant external execution authority"],
        "open_work": [f"work-{label}"],
        "uncertainties": [f"uncertainty-{label}"],
        "artifact_refs": [],
        "memory_refs": [],
    }


def _substrate(
    substrate_id: str,
    *,
    affinities: list[str] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": 1,
        "substrate_id": substrate_id,
        "label": f"Substrate {substrate_id}",
        "adapter": "manual",
        "capabilities": [
            "repository_read",
            "repository_write",
            "verification_execute",
        ],
        "policy_labels": ["local-workspace"],
        "context_budget": {"unit": "words", "limit": 10000},
        "task_affinities": affinities or ["implementation"],
    }


def _handoff_plan(
    *,
    target_substrate_id: str = "visibility-target",
    target_activation_id: str = "activation-visibility-target",
    reason_code: str = "task_phase_transition",
) -> dict[str, Any]:
    affinity = "recovery" if reason_code == "failure_recovery" else "review"
    plan = {
        "target_substrate": _substrate(
            target_substrate_id,
            affinities=[affinity],
        ),
        "target_activation_id": target_activation_id,
        "task_phase": (
            "failure-recovery"
            if reason_code == "failure_recovery"
            else "independent-review"
        ),
        "requirements": {
            "capabilities": ["repository_read", "verification_execute"],
            "policy_labels": ["local-workspace"],
            "minimum_context_units": 500,
        },
        "budget_limit": 1000,
        "target_responsibility": (
            "Recover the last verified lineage head"
            if reason_code == "failure_recovery"
            else "Review the current lineage state"
        ),
        "reason_code": reason_code,
        "rationale": f"Exercise visibility for {reason_code}.",
    }
    if reason_code == "failure_recovery":
        plan.update(
            {
                "operator_ref": "operator-visibility-recovery",
                "target_assignment_ref": "assignment-visibility-recovery",
            }
        )
    return plan


def _bootstrap(
    store: Store,
    *,
    lineage_id: str = "visibility-lineage",
    activation_id: str = "activation-visibility-source",
    substrate_id: str = "visibility-source",
) -> dict[str, Any]:
    return create_operator_lineage(
        store,
        lineage_id=lineage_id,
        canonical_state=_state(lineage_id),
        substrate=_substrate(substrate_id),
        activation_id=activation_id,
    )


def _reconstruction(store: Store, prepared: dict[str, Any]) -> dict[str, Any]:
    return json.loads(
        (store.state_dir / prepared["reconstruction_template_path"]).read_text(
            encoding="utf-8"
        )
    )


def _accepted_handoff(store: Store) -> tuple[dict[str, Any], dict[str, Any]]:
    source = _bootstrap(store)
    prepared = prepare_operator_handoff(
        store,
        lineage_id="visibility-lineage",
        source_activation_id=source["activation_id"],
        plan=_handoff_plan(),
    )
    resolve_operator_handoff(
        store,
        handoff_id=prepared["handoff_id"],
        target_activation_id=prepared["target_activation_id"],
        reconstruction=_reconstruction(store, prepared),
    )
    return source, prepared


def test_initial_authority_is_explained_from_verified_records(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        created = _bootstrap(store)

        report = build_lineage_explanation(store, "visibility-lineage")

    assert report["schema_version"] == 1
    assert report["report_kind"] == "lineage_explanation"
    assert report["derived"] is True
    assert report["canonical"] is False
    assert report["trusted"] is True
    assert report["explanation_complete"] is True
    assert report["warnings"] == []
    assert report["lineage"]["lineage_id"] == "visibility-lineage"
    assert report["lineage"]["head"]["revision_id"] == created["revision_id"]
    assert report["current_authority"]["activation_id"] == created["activation_id"]
    assert report["current_authority"]["lease_id"] == created["lease_id"]
    assert report["current_authority"]["head_revision_id"] == created["revision_id"]
    assert len(report["authority_changes"]) == 1
    initial = report["authority_changes"][0]
    assert initial["kind"] == "lineage_created"
    assert initial["from_authority"] is None
    assert initial["to_authority"]["activation_id"] == created["activation_id"]
    assert created["activation_id"] in initial["summary"]

    _validate_report(report)


def test_accepted_handoff_explains_fit_acceptance_and_transfer(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        source, prepared = _accepted_handoff(store)

        report = build_lineage_explanation(store, "visibility-lineage")

    assert report["trusted"] is True
    assert report["current_authority"]["activation_id"] == prepared[
        "target_activation_id"
    ]
    assert len(report["authority_changes"]) == 2
    transfer = report["authority_changes"][-1]
    assert transfer["kind"] == "handoff"
    assert transfer["from_authority"]["activation_id"] == source["activation_id"]
    assert transfer["to_authority"]["activation_id"] == prepared[
        "target_activation_id"
    ]
    assert transfer["detail"]["reason_code"] == "task_phase_transition"
    assert transfer["detail"]["acceptance"]["disposition"] == "accepted"
    assert transfer["detail"]["acceptance"]["passed_requirements"] == 9
    assert transfer["detail"]["acceptance"]["total_requirements"] == 9
    assert transfer["detail"]["fit"]["selected_substrate_id"] == (
        "visibility-target"
    )
    assert transfer["detail"]["fit_selection_grants_authority"] is False
    handoff = report["handoffs"][0]
    assert handoff["handoff_id"] == prepared["handoff_id"]
    assert handoff["state"] == "accepted"
    assert handoff["authority_effect"] == "transferred"
    assert handoff["external_assignment_grants_authority"] is False
    _validate_report(report)


def test_rejected_handoff_explains_failed_checks_and_unchanged_authority(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        prepared = prepare_operator_handoff(
            store,
            lineage_id="visibility-lineage",
            source_activation_id=source["activation_id"],
            plan=_handoff_plan(),
        )
        reconstruction = _reconstruction(store, prepared)
        reconstruction["hard_constraints"] = []
        resolve_operator_handoff(
            store,
            handoff_id=prepared["handoff_id"],
            target_activation_id=prepared["target_activation_id"],
            reconstruction=reconstruction,
        )

        report = build_lineage_explanation(store, "visibility-lineage")

    assert report["trusted"] is True
    assert report["current_authority"]["activation_id"] == source["activation_id"]
    assert len(report["authority_changes"]) == 1
    handoff = report["handoffs"][0]
    assert handoff["state"] == "rejected"
    assert handoff["can_resolve"] is False
    assert handoff["authority_effect"] == "unchanged"
    assert handoff["acceptance"]["failed_requirements"] == ["hard_constraints"]
    _validate_report(report)


def test_pending_and_stale_handoffs_are_distinguished(tmp_path: Path) -> None:
    pending_dir = tmp_path / "pending"
    stale_dir = tmp_path / "stale"
    with Store(pending_dir) as store:
        source = _bootstrap(store)
        prepare_operator_handoff(
            store,
            lineage_id="visibility-lineage",
            source_activation_id=source["activation_id"],
            plan=_handoff_plan(),
        )
        pending_report = build_lineage_explanation(store, "visibility-lineage")

    with Store(stale_dir) as store:
        source = _bootstrap(store)
        prepare_operator_handoff(
            store,
            lineage_id="visibility-lineage",
            source_activation_id=source["activation_id"],
            plan=_handoff_plan(),
        )
        checkpoint_operator_lineage(
            store,
            lineage_id="visibility-lineage",
            activation_id=source["activation_id"],
            canonical_state=_state("advanced-after-prepare"),
        )
        stale_report = build_lineage_explanation(store, "visibility-lineage")

    pending = pending_report["handoffs"][0]
    assert pending_report["trusted"] is True
    assert pending["state"] == "pending"
    assert pending["can_resolve"] is True
    assert pending["stale_reasons"] == []
    assert pending["authority_effect"] == "not transferred"

    stale = stale_report["handoffs"][0]
    assert stale_report["trusted"] is True
    assert stale["state"] == "stale"
    assert stale["can_resolve"] is False
    assert stale["stale_reasons"] == ["source head changed"]
    assert stale["authority_effect"] == "unchanged; cannot resolve"
    _validate_report(pending_report)
    _validate_report(stale_report)


def test_pending_handoff_requires_a_matching_pending_target(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        prepared = prepare_operator_handoff(
            store,
            lineage_id="visibility-lineage",
            source_activation_id=source["activation_id"],
            plan=_handoff_plan(),
        )
        store.connection.execute(
            "UPDATE activations SET state = 'completed' WHERE activation_id = ?",
            (prepared["target_activation_id"],),
        )
        store.connection.commit()

        report = build_lineage_explanation(store, "visibility-lineage")

    handoff = report["handoffs"][0]
    assert report["trusted"] is True
    assert handoff["state"] == "stale"
    assert handoff["can_resolve"] is False
    assert handoff["stale_reasons"] == [
        "matching pending target activation unavailable"
    ]
    _validate_report(report)


def test_accepted_recovery_is_explained_as_failure_recovery(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        prepared = prepare_operator_recovery(
            store,
            lineage_id="visibility-lineage",
            failed_activation_id=source["activation_id"],
            plan=_handoff_plan(
                target_substrate_id="visibility-recovery-target",
                target_activation_id="activation-visibility-recovery",
                reason_code="failure_recovery",
            ),
            evidence_refs=["process-probe-visibility"],
        )
        resolve_operator_recovery(
            store,
            handoff_id=prepared["handoff_id"],
            target_activation_id=prepared["target_activation_id"],
            reconstruction=_reconstruction(store, prepared),
        )

        report = build_lineage_explanation(store, "visibility-lineage")

    recovery = report["authority_changes"][-1]
    assert report["trusted"] is True
    assert report["current_authority"]["activation_id"] == (
        "activation-visibility-recovery"
    )
    assert recovery["kind"] == "failure_recovery"
    assert recovery["detail"]["reason_code"] == "failure_recovery"
    assert recovery["detail"]["recovery_context"]["evidence_refs"] == [
        "process-probe-visibility"
    ]
    assert recovery["detail"]["acceptance"]["disposition"] == "accepted"
    _validate_report(report)


def test_rollback_is_continuity_only_and_does_not_invent_authority_change(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        checkpoint = checkpoint_operator_lineage(
            store,
            lineage_id="visibility-lineage",
            activation_id=source["activation_id"],
            canonical_state=_state("state-to-undo"),
        )
        rollback = rollback_operator_lineage(
            store,
            lineage_id="visibility-lineage",
            activation_id=source["activation_id"],
            expected_head_revision_id=checkpoint["revision_id"],
            target_revision_id=source["revision_id"],
            operator_ref="operator-visibility-rollback",
            rationale="Restore the initial visible state.",
            evidence_refs=["review-finding-visibility"],
        )

        report = build_lineage_explanation(store, "visibility-lineage")

    rollback_event = next(
        item
        for item in report["continuity_events"]
        if item["revision_id"] == rollback["revision_id"]
    )
    assert report["trusted"] is True
    assert len(report["authority_changes"]) == 1
    assert report["current_authority"]["activation_id"] == source["activation_id"]
    assert report["current_authority"]["lease_id"] == source["lease_id"]
    assert rollback_event["event_type"] == "rollback_applied"
    assert rollback_event["authority_changed"] is False
    assert rollback_event["related_revision_id"] == source["revision_id"]
    assert "bearer unchanged" in rollback_event["summary"]
    _validate_report(report)


def test_branch_origin_and_child_relationship_are_visible_from_both_lineages(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        child = create_lineage_branch(
            store,
            source_lineage_id="visibility-lineage",
            source_activation_id=source["activation_id"],
            expected_source_revision_id=source["revision_id"],
            child_lineage_id="visibility-child",
            child_activation_id="activation-visibility-child",
            child_substrate=_substrate("visibility-child-substrate"),
            operator_ref="operator-visibility-branch",
            target_assignment_ref="assignment-visibility-child",
            rationale="Create an independently visible child lineage.",
            evidence_refs=["design-finding-visibility-branch"],
        )

        source_report = build_lineage_explanation(store, "visibility-lineage")
        child_report = build_lineage_explanation(store, "visibility-child")

    assert source_report["trusted"] is True
    assert source_report["relationships"]["branch_origin"] is None
    assert source_report["relationships"]["child_lineages"] == [
        {
            "lineage_id": "visibility-child",
            "root_revision_id": child["revision_id"],
            "source_revision_id": source["revision_id"],
        }
    ]
    origin = child_report["relationships"]["branch_origin"]
    assert child_report["trusted"] is True
    assert origin["source_lineage_id"] == "visibility-lineage"
    assert origin["source_revision_id"] == source["revision_id"]
    assert origin["target_assignment_ref"] == "assignment-visibility-child"
    assert child_report["authority_changes"][0]["kind"] == "branch_created"
    assert child_report["authority_changes"][0]["detail"][
        "external_assignment_grants_authority"
    ] is False
    _validate_report(source_report)
    _validate_report(child_report)


def test_invalid_child_branch_makes_source_relationship_untrusted(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        child = create_lineage_branch(
            store,
            source_lineage_id="visibility-lineage",
            source_activation_id=source["activation_id"],
            expected_source_revision_id=source["revision_id"],
            child_lineage_id="visibility-child",
            child_activation_id="activation-visibility-child",
            child_substrate=_substrate("visibility-child-substrate"),
            operator_ref="operator-visibility-branch",
            target_assignment_ref="assignment-visibility-child",
            rationale="Create a relationship that will be tampered.",
            evidence_refs=["design-finding-visibility-branch"],
        )
        row = store.connection.execute(
            "SELECT payload_json FROM revisions WHERE revision_id = ?",
            (child["revision_id"],),
        ).fetchone()
        payload = json.loads(row["payload_json"])
        payload["branch_origin"]["rationale"] = "tampered"
        store.connection.execute("DROP TRIGGER revisions_no_update")
        store.connection.execute(
            "UPDATE revisions SET payload_json = ? WHERE revision_id = ?",
            (json.dumps(payload), child["revision_id"]),
        )
        store.connection.commit()

        report = build_lineage_explanation(store, "visibility-lineage")

    assert report["trusted"] is False
    assert report["relationships"]["child_lineages"] == []
    assert "revision_hash_mismatch" in {
        item["code"] for item in report["verification"]["errors"]
    }
    _validate_report(report)


def test_time_inverted_transfer_is_untrusted(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        prepared = prepare_operator_handoff(
            store,
            lineage_id="visibility-lineage",
            source_activation_id=source["activation_id"],
            plan=_handoff_plan(),
        )
        resolve_handoff(
            store,
            handoff_id=prepared["handoff_id"],
            target_activation_id=prepared["target_activation_id"],
            reconstruction=_reconstruction(store, prepared),
            resolved_at="2000-01-01T00:00:00Z",
        )

        report = build_lineage_explanation(store, "visibility-lineage")

    assert report["trusted"] is False
    assert "authority_transition_chronology_invalid" in {
        item["code"] for item in report["verification"]["errors"]
    }
    _validate_report(report)


def test_invalid_transition_makes_report_untrusted_and_cli_nonzero(
    tmp_path: Path, capsys
) -> None:
    with Store(tmp_path) as store:
        source = _bootstrap(store)
        store.connection.execute(
            """INSERT INTO authority_transitions
               VALUES (?, ?, ?, ?, ?, ?, NULL, NULL, ?, ?)""",
            (
                "transition-unexplained-visibility",
                "visibility-lineage",
                source["activation_id"],
                source["activation_id"],
                source["lease_id"],
                source["lease_id"],
                source["revision_id"],
                utc_now(),
            ),
        )
        store.connection.commit()
        report = build_lineage_explanation(store, "visibility-lineage")

    assert report["trusted"] is False
    assert report["explanation_complete"] is False
    assert report["current_authority"] is None
    assert report["authority_changes"] == []
    assert report["warnings"]
    assert "authority_transition_unexplained" in {
        item["code"] for item in report["verification"]["errors"]
    }
    _validate_report(report)

    exit_code = main(
        [
            "lineage",
            "explain",
            "--state-dir",
            str(tmp_path),
            "--lineage",
            "visibility-lineage",
            "--json",
        ]
    )
    cli_report = json.loads(capsys.readouterr().out)
    assert exit_code == 1
    assert cli_report["trusted"] is False
    assert cli_report["explanation_complete"] is False


def test_missing_head_returns_schema_conforming_untrusted_report(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        _bootstrap(store)
        store.connection.execute("PRAGMA foreign_keys = OFF")
        store.connection.execute(
            "UPDATE lineages SET head_revision_id = ? WHERE lineage_id = ?",
            ("revision-missing-visibility", "visibility-lineage"),
        )
        store.connection.commit()

        report = build_lineage_explanation(store, "visibility-lineage")

    assert report["trusted"] is False
    assert report["lineage"]["head"] == {
        "revision_id": "revision-missing-visibility",
        "event_type": "unverified",
        "created_at": report["lineage"]["head"]["created_at"],
    }
    assert report["authority_changes"] == []
    _validate_report(report)


def test_explanation_order_and_payload_are_deterministic(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        _accepted_handoff(store)

        first = build_lineage_explanation(store, "visibility-lineage")
        second = build_lineage_explanation(store, "visibility-lineage")

    assert first == second
    assert [item["sequence"] for item in first["authority_changes"]] == sorted(
        item["sequence"] for item in first["authority_changes"]
    )
    assert [item["occurred_at"] for item in first["authority_changes"]] == sorted(
        item["occurred_at"] for item in first["authority_changes"]
    )
    assert [item["prepared_at"] for item in first["handoffs"]] == sorted(
        item["prepared_at"] for item in first["handoffs"]
    )
    assert [item["decided_at"] for item in first["fit_decisions"]] == sorted(
        item["decided_at"] for item in first["fit_decisions"]
    )
    assert [item["created_at"] for item in first["continuity_events"]] == sorted(
        item["created_at"] for item in first["continuity_events"]
    )


def test_cli_json_and_text_reports_are_genuinely_read_only(
    tmp_path: Path, capsys
) -> None:
    state_dir = tmp_path / "state"
    with Store(state_dir) as store:
        _accepted_handoff(store)

    before = {
        path.relative_to(state_dir): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in state_dir.rglob("*")
        if path.is_file()
    }

    json_exit = main(
        [
            "lineage",
            "explain",
            "--state-dir",
            str(state_dir),
            "--lineage",
            "visibility-lineage",
            "--json",
        ]
    )
    json_report = json.loads(capsys.readouterr().out)
    text_exit = main(
        [
            "lineage",
            "explain",
            "--state-dir",
            str(state_dir),
            "--lineage",
            "visibility-lineage",
        ]
    )
    text_report = capsys.readouterr().out

    after = {
        path.relative_to(state_dir): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in state_dir.rglob("*")
        if path.is_file()
    }
    assert json_exit == 0
    assert text_exit == 0
    assert json_report["trusted"] is True
    assert text_report.startswith("TORC lineage visibility-lineage — VALID")
    assert "Authority history" in text_report
    assert "Handoffs" in text_report
    assert "Continuity events" in text_report
    assert not text_report.lstrip().startswith("{")
    assert after == before


def test_explain_missing_store_fails_without_creating_state(
    tmp_path: Path, capsys
) -> None:
    missing = tmp_path / "missing"

    exit_code = main(
        [
            "lineage",
            "explain",
            "--state-dir",
            str(missing),
            "--lineage",
            "visibility-lineage",
            "--json",
        ]
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 1
    assert payload["ok"] is False
    assert payload["error"] == "NotFoundError"
    assert not missing.exists()
