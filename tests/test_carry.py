from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest
from jsonschema import Draft202012Validator, FormatChecker

import torc.operator as operator_module
from torc.canonical import seal_record, utc_now
from torc.cli import main
from torc.errors import IntegrityError, InvalidInputError, ProjectionBudgetError
from torc.history import changes_since_substrate, unaccounted_drops
from torc.ids import new_id
from torc.operator import (
    carry_operator_lineage,
    checkpoint_operator_lineage,
    create_operator_lineage,
    operator_lineage_status,
    prepare_operator_handoff,
    resolve_operator_handoff,
    rollback_operator_lineage,
)
from torc.projections import compile_projection, receiver_budget
from torc.store import Store
from torc.verify import verify_store

ROOT = Path(__file__).resolve().parents[1]
FIXTURE = ROOT / "examples" / "p5-dropped-work"
LINEAGE = "p5-dropped-work"
ACTIVATION = "activation-implementer"
DROPPED_WORK = "Handle exports larger than memory"
DROPPED_CONSTRAINT = "Never write outside the state directory"
COMPLETED_WORK = "Define the export schema"


def _load(name: str) -> Any:
    return json.loads((FIXTURE / name).read_text(encoding="utf-8"))


def _checkpoint(store: Store, state: dict[str, Any], **kwargs: Any) -> dict[str, Any]:
    return checkpoint_operator_lineage(
        store,
        lineage_id=LINEAGE,
        activation_id=kwargs.pop("activation_id", ACTIVATION),
        canonical_state=state,
        **kwargs,
    )


def _build(store: Store, *, through: int = 4) -> list[str]:
    """Replay the fixture and return its revision identifiers, oldest first."""

    created = create_operator_lineage(
        store,
        lineage_id=LINEAGE,
        canonical_state=_load("state-1-created.json"),
        substrate=_load("source-substrate.json"),
        activation_id=ACTIVATION,
    )
    revisions = [created["revision_id"]]
    steps = (
        ("state-2-work-added.json", None),
        ("state-3-item-completed.json", _load("resolutions-3.json")),
        ("state-4-last-summary.json", None),
    )
    for name, resolutions in steps[: through - 1]:
        revisions.append(
            _checkpoint(store, _load(name), resolutions=resolutions)["revision_id"]
        )
    return revisions


def _carry(store: Store, receiver: str, **kwargs: Any) -> dict[str, Any]:
    return carry_operator_lineage(
        store, lineage_id=LINEAGE, substrate=_load(receiver), **kwargs
    )["projection"]


def _sections(projection: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["section_id"]: item for item in projection["included_sections"]}


def _omitted(projection: dict[str, Any]) -> dict[str, str]:
    return {item["section_id"]: item["reason"] for item in projection["omitted_sections"]}


def _validate(schema_name: str, record: dict[str, Any]) -> None:
    schema = json.loads((ROOT / "schemas" / schema_name).read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(record)


def test_p0_loses_the_dropped_work_and_p5_carries_it(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        revisions = _build(store)
        frozen = compile_projection(
            store,
            lineage_id=LINEAGE,
            source_revision_id=revisions[-1],
            target_substrate_id="p5-implementer",
            budget_limit=10000,
            handoff_reason="model_succession",
            target_responsibility="Continue the export command",
        )
        carry = _carry(store, "receiver-large.json")

    assert DROPPED_WORK not in json.dumps(frozen["included_sections"])
    assert frozen["omitted_sections"] == []

    sections = _sections(carry)
    assert sections["unaccounted-open_work-2"]["content"] == {
        "section": "open_work",
        "item": DROPPED_WORK,
        "last_seen_revision_id": revisions[2],
        "dropped_at_revision_id": revisions[3],
        "dropped_by_substrate_id": "p5-implementer",
    }
    assert sections["unaccounted-open_work-2"]["source_ref"] == f"{revisions[2]}:open_work"
    assert sections["unaccounted-constraints-1"]["content"]["item"] == DROPPED_CONSTRAINT
    assert COMPLETED_WORK not in json.dumps(carry["included_sections"])
    assert sections["receiver-fit"]["content"]["history_revisions_read"] == 4
    assert carry["compiler_version"] == "p5-1"
    _validate("execution-projection.schema.json", carry)


def test_carry_is_sized_and_shaped_by_the_receiver_from_unchanged_history(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        _build(store)
        before = [row[0] for row in store.connection.execute(
            "SELECT payload_json FROM revisions ORDER BY rowid"
        )]
        small = _carry(store, "receiver-small.json")
        large = _carry(store, "receiver-large.json")
        after = [row[0] for row in store.connection.execute(
            "SELECT payload_json FROM revisions ORDER BY rowid"
        )]

    assert before == after
    assert small["source_revision_id"] == large["source_revision_id"]
    assert small["budget"]["limit"] == 100
    assert _sections(small)["receiver-fit"]["content"]["budget_source"] == (
        "descriptor_carry_limit"
    )
    assert large["budget"]["limit"] == 10000
    assert _sections(large)["receiver-fit"]["content"]["budget_source"] == "descriptor_share"
    assert small["budget"]["estimated_used"] <= 100

    # The small receiver still gets both dropped items before any optional state.
    assert {"unaccounted-constraints-1", "unaccounted-open_work-2"} <= set(_sections(small))
    assert _sections(small)["settled-decisions"]["content"] == [
        "Exports are written as UTF-8 JSON"
    ]
    assert _omitted(small) == {
        "settled-decisions.remainder": "budget",
        "uncertainties": "budget",
        "methods": "budget",
        "artifact-refs": "capability_irrelevant",
    }
    assert _omitted(large) == {}
    assert "artifact-refs" in _sections(large)
    _validate("execution-projection.schema.json", small)


def test_required_continuity_must_fit_the_receiver(tmp_path: Path) -> None:
    receiver = _load("receiver-small.json")
    receiver["context_budget"]["carry_limit"] = 20
    with Store(tmp_path) as store:
        _build(store)
        with pytest.raises(ProjectionBudgetError, match="receiver budget is 20"):
            carry_operator_lineage(store, lineage_id=LINEAGE, substrate=receiver)
        stored = store.connection.execute("SELECT COUNT(*) FROM projections").fetchone()[0]
        registered = [item["substrate_id"] for item in store.list_substrates()]

    assert stored == 0
    assert registered == ["p5-implementer"]


def test_receiver_budget_comes_from_the_descriptor_and_a_cap_only_lowers_it() -> None:
    descriptor = {"context_budget": {"unit": "words", "limit": 32000}}
    assert receiver_budget(descriptor) == {
        "unit": "words",
        "limit": 1600,
        "source": "descriptor_share",
        "context_limit": 32000,
    }
    assert receiver_budget(descriptor, 1000)["source"] == "operator_cap"
    assert receiver_budget(descriptor, 1000)["limit"] == 1000
    assert receiver_budget(descriptor, 5000)["limit"] == 1600
    assert receiver_budget({"context_budget": {"limit": 300}})["limit"] == 200
    assert receiver_budget({"context_budget": {"limit": 120}})["limit"] == 120
    assert receiver_budget({"context_budget": {"unit": "characters", "limit": 9000}}) == {
        "unit": "characters",
        "limit": 1200,
        "source": "descriptor_share",
        "context_limit": 9000,
    }
    for context in (
        {"unit": "tokens", "limit": 1000},
        {"limit": 1000, "carry_limit": 2000},
        {"limit": 1000, "carry_limit": 0},
        {"limit": 1000, "carry_limit": True},
    ):
        with pytest.raises(InvalidInputError):
            receiver_budget({"context_budget": context})
    with pytest.raises(InvalidInputError):
        receiver_budget(descriptor, 0)


def test_unaccounted_drop_is_asked_about_until_restored_or_resolved(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        _build(store, through=3)
        dropped = _checkpoint(store, _load("state-4-last-summary.json"))
        asked = {(item["section"], item["item"]) for item in dropped["boundary"]["unaccounted"]}
        status = operator_lineage_status(store, LINEAGE)

        repaired = _load("state-4-last-summary.json")
        repaired["constraints"].append(DROPPED_CONSTRAINT)
        settled = _checkpoint(
            store,
            repaired,
            resolutions=[
                {
                    "section": "open_work",
                    "item": DROPPED_WORK,
                    "disposition": "withdrawn",
                    "note": "Exports are bounded by the state directory size",
                }
            ],
        )
        carry = _carry(store, "receiver-large.json")
        head = store.get_revision(settled["revision_id"])

    assert dropped["ok"] is True
    assert asked == {("constraints", DROPPED_CONSTRAINT), ("open_work", DROPPED_WORK)}
    assert status["boundary"]["unaccounted"] == dropped["boundary"]["unaccounted"]
    assert settled["boundary"]["unaccounted"] == []
    assert not [name for name in _sections(carry) if name.startswith("unaccounted-")]
    assert head["resolutions"][0]["disposition"] == "withdrawn"
    _validate("lineage-revision.schema.json", head)


@pytest.mark.parametrize(
    ("resolutions", "message"),
    (
        (
            [{"section": "open_work", "item": "Never existed", "disposition": "completed"}],
            "never dropped",
        ),
        (
            [
                {
                    "section": "open_work",
                    "item": "Write the export round-trip test",
                    "disposition": "completed",
                }
            ],
            "still present",
        ),
        (
            [{"section": "open_work", "item": COMPLETED_WORK, "disposition": "done"}],
            "disposition",
        ),
        (
            [{"section": "goals", "item": "Ship the export", "disposition": "completed"}],
            "section",
        ),
        (
            [
                {"section": "open_work", "item": DROPPED_WORK, "disposition": "completed"},
                {"section": "open_work", "item": DROPPED_WORK, "disposition": "withdrawn"},
            ],
            "duplicate",
        ),
        ([], "non-empty"),
    ),
)
def test_resolution_must_name_a_real_removal(
    tmp_path: Path, resolutions: list[dict[str, str]], message: str
) -> None:
    with Store(tmp_path) as store:
        revisions = _build(store, through=3)
        with pytest.raises(InvalidInputError, match=message):
            _checkpoint(store, _load("state-4-last-summary.json"), resolutions=resolutions)
        head = store.get_lineage(LINEAGE)["head_revision_id"]

    assert head == revisions[-1]


def test_revision_without_resolutions_keeps_its_recorded_shape(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        revisions = _build(store)
        plain = store.get_revision(revisions[1])
        resolved = store.get_revision(revisions[2])

    assert "resolutions" not in plain
    assert resolved["resolutions"] == _load("resolutions-3.json")
    _validate("lineage-revision.schema.json", plain)
    _validate("lineage-revision.schema.json", resolved)
    invalid = seal_record(
        {key: value for key, value in resolved.items() if key != "integrity"}
        | {"resolutions": [{"section": "open_work", "item": "x", "disposition": "done"}]},
        previous_revision_sha256=resolved["integrity"]["previous_revision_sha256"],
    )
    schema = json.loads(
        (ROOT / "schemas" / "lineage-revision.schema.json").read_text(encoding="utf-8")
    )
    assert not Draft202012Validator(schema).is_valid(invalid)


def test_rollback_accounts_for_what_it_removes(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        revisions = _build(store, through=2)
        rolled_back = rollback_operator_lineage(
            store,
            lineage_id=LINEAGE,
            activation_id=ACTIVATION,
            expected_head_revision_id=revisions[1],
            target_revision_id=revisions[0],
            operator_ref="operator-p5-rollback",
            rationale="The added work was recorded against the wrong lineage.",
            evidence_refs=["evidence-p5-rollback"],
        )
        status = operator_lineage_status(store, LINEAGE)

    assert rolled_back["ok"] is True
    assert DROPPED_WORK not in status["open_work"]
    assert status["boundary"]["unaccounted"] == []


def _handoff_plan() -> dict[str, Any]:
    return {
        "target_substrate": _load("receiver-large.json"),
        "target_activation_id": "activation-successor",
        "task_phase": "implementation",
        "requirements": {
            "capabilities": ["repository_read", "repository_write"],
            "policy_labels": ["local-workspace"],
            "minimum_context_units": 1000,
        },
        "target_responsibility": "Finish the lineage export command",
        "reason_code": "model_succession",
        "rationale": "A larger-context session takes over the export work.",
    }


def test_new_bearer_is_asked_to_restate_the_self_model_until_it_does(
    tmp_path: Path,
) -> None:
    with Store(tmp_path) as store:
        _build(store)
        prepared = prepare_operator_handoff(
            store,
            lineage_id=LINEAGE,
            source_activation_id=ACTIVATION,
            plan=_handoff_plan(),
        )
        projection = store.get_hashed_record(
            "projections", "projection_id", prepared["projection_id"]
        )
        brief = (store.state_dir / prepared["brief_path"]).read_text(encoding="utf-8")
        template = json.loads(
            (store.state_dir / prepared["reconstruction_template_path"]).read_text(
                encoding="utf-8"
            )
        )
        accepted = resolve_operator_handoff(
            store,
            handoff_id=prepared["handoff_id"],
            target_activation_id="activation-successor",
            reconstruction=template,
        )
        asked = operator_lineage_status(store, LINEAGE)["boundary"]["self_model"]

        restated = json.loads(json.dumps(store.get_revision(
            store.get_lineage(LINEAGE)["head_revision_id"]
        )["canonical_state"]))
        restated["self_model"]["methods"] = ["Stream exports in bounded chunks"]
        answered = _checkpoint(
            store,
            restated,
            activation_id="activation-successor",
            event_type="self_model_revised",
        )["boundary"]["self_model"]
        verification = verify_store(store, LINEAGE)

    assert projection["compiler_version"] == "p5-1"
    assert projection["budget"]["limit"] == 10000
    assert _sections(projection)["self-model-provenance"]["content"]["restatement_due"] is True
    assert DROPPED_WORK in brief
    assert accepted["disposition"] == "accepted"
    # The role copied at acceptance is TORC's bookkeeping, not a restatement.
    assert asked["authored_by_substrate_id"] == "p5-implementer"
    assert asked["bearer_substrate_id"] == "p5-receiver-large"
    assert asked["restatement_due"] is True
    assert answered["authored_by_substrate_id"] == "p5-receiver-large"
    assert answered["restatement_due"] is False
    assert verification["valid"] is True


def test_carry_reports_what_changed_while_the_receiver_was_away(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        revisions = _build(store, through=3)
        prepared = prepare_operator_handoff(
            store,
            lineage_id=LINEAGE,
            source_activation_id=ACTIVATION,
            plan=_handoff_plan(),
        )
        template = json.loads(
            (store.state_dir / prepared["reconstruction_template_path"]).read_text(
                encoding="utf-8"
            )
        )
        resolve_operator_handoff(
            store,
            handoff_id=prepared["handoff_id"],
            target_activation_id="activation-successor",
            reconstruction=template,
        )
        advanced = json.loads(json.dumps(store.get_revision(
            store.get_lineage(LINEAGE)["head_revision_id"]
        )["canonical_state"]))
        advanced["open_work"] = [DROPPED_WORK, "Publish the export guide"]
        _checkpoint(
            store,
            advanced,
            activation_id="activation-successor",
            resolutions=[
                {
                    "section": "open_work",
                    "item": "Write the export round-trip test",
                    "disposition": "completed",
                }
            ],
        )
        returning = carry_operator_lineage(
            store, lineage_id=LINEAGE, substrate=_load("source-substrate.json")
        )["projection"]
        unchanged = _carry(store, "receiver-large.json")

    changes = _sections(returning)["changes-since-receiver"]
    assert changes["source_ref"] == f"{revisions[2]}:canonical_state"
    assert changes["content"]["since_revision_id"] == revisions[2]
    assert changes["content"]["revisions_since"] == 2
    assert changes["content"]["added"] == {"open_work": ["Publish the export guide"]}
    assert changes["content"]["removed"] == {
        "open_work": [
            {"item": "Write the export round-trip test", "disposition": "completed"}
        ]
    }
    assert changes["content"]["self_model_changed"] is True
    assert _sections(returning)["session-purpose"]["content"] == {
        "purpose": "session_start",
        "authority": {
            "activation_id": "activation-successor",
            "substrate_id": "p5-receiver-large",
        },
        "receiver_is_authority_substrate": False,
    }
    # The current bearer authored the head, so nothing happened while it was away.
    assert "changes-since-receiver" not in _sections(unchanged)


def test_carry_changes_no_canonical_or_authority_record(tmp_path: Path) -> None:
    tables = ("revisions", "lineages", "activations", "leases", "authority_transitions")
    with Store(tmp_path) as store:
        _build(store)

        def snapshot() -> dict[str, list[tuple[Any, ...]]]:
            return {
                table: [tuple(row) for row in store.connection.execute(
                    f"SELECT * FROM {table} ORDER BY rowid"
                )]
                for table in tables
            }

        before = snapshot()
        carried = carry_operator_lineage(
            store, lineage_id=LINEAGE, substrate=_load("receiver-small.json")
        )
        after = snapshot()
        verification = verify_store(store, LINEAGE)

    assert before == after
    assert carried["authority_transferred"] is False
    assert verification["valid"] is True


def test_observer_carry_cannot_veto_a_later_handoff(tmp_path: Path) -> None:
    observer = _load("receiver-large.json") | {"substrate_id": "an-observer"}
    with Store(tmp_path) as store:
        _build(store)
        carry_operator_lineage(store, lineage_id=LINEAGE, substrate=observer)
        prepared = prepare_operator_handoff(
            store,
            lineage_id=LINEAGE,
            source_activation_id=ACTIVATION,
            plan=_handoff_plan(),
        )
        fit = store.get_hashed_record(
            "fit_decisions", "fit_decision_id", prepared["fit_decision_id"]
        )

    assert prepared["target_substrate_id"] == "p5-receiver-large"
    assert fit["selected_substrate_id"] == "p5-receiver-large"
    assert [item["substrate_id"] for item in fit["candidates"]] == [
        "p5-implementer",
        "p5-receiver-large",
    ]


def test_verify_detects_a_tampered_or_misattributed_carry(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        revisions = _build(store)
        carry = _carry(store, "receiver-large.json")
        other = create_operator_lineage(
            store,
            lineage_id="p5-other",
            canonical_state=_load("state-1-created.json"),
            substrate=_load("source-substrate.json"),
            activation_id="activation-other",
        )
        forged = seal_record(
            {key: value for key, value in carry.items() if key != "integrity"}
            | {
                "projection_id": "projection-forged",
                "included_sections": [
                    section | {"source_ref": f"{other['revision_id']}:open_work"}
                    if section["section_id"] == "unaccounted-open_work-2"
                    else section
                    for section in carry["included_sections"]
                ],
            }
        )
        store.insert_hashed_record("projections", "projection-forged", forged)
        misattributed = verify_store(store, LINEAGE)

        payload = dict(carry, schema_version=999)
        with store.connection:
            store.connection.execute("DROP TRIGGER projections_no_update")
            store.connection.execute(
                "UPDATE projections SET payload_json = ? WHERE projection_id = ?",
                (json.dumps(payload), carry["projection_id"]),
            )
        tampered = verify_store(store, LINEAGE)

    assert revisions
    assert [
        (error["code"], error["record_id"]) for error in misattributed["errors"]
    ] == [("projection_source_ref_invalid", "projection-forged")]
    assert "projection_hash_mismatch" in {error["code"] for error in tampered["errors"]}


def test_cli_checkpoint_resolutions_and_carry(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    state_dir = str(tmp_path / "state")

    def run(*argv: str) -> tuple[int, str]:
        status = main(list(argv))
        return status, capsys.readouterr().out

    assert run(
        "lineage", "create", "--state-dir", state_dir, "--lineage", LINEAGE,
        "--state-file", str(FIXTURE / "state-1-created.json"),
        "--substrate-file", str(FIXTURE / "source-substrate.json"),
        "--activation-id", ACTIVATION, "--json",
    )[0] == 0
    checkpoint = (
        "lineage", "checkpoint", "--state-dir", state_dir, "--lineage", LINEAGE,
        "--activation", ACTIVATION, "--json", "--state-file",
    )
    assert run(*checkpoint, str(FIXTURE / "state-2-work-added.json"))[0] == 0

    bad = tmp_path / "bad-resolutions.json"
    bad.write_text('[{"section": "open_work", "item": "x", "disposition": "done"}]')
    status, output = run(
        *checkpoint, str(FIXTURE / "state-3-item-completed.json"),
        "--resolutions-file", str(bad),
    )
    assert status == 1
    assert json.loads(output)["error"] == "InvalidInputError"

    status, output = run(
        *checkpoint, str(FIXTURE / "state-3-item-completed.json"),
        "--resolutions-file", str(FIXTURE / "resolutions-3.json"),
    )
    assert status == 0
    assert json.loads(output)["boundary"]["unaccounted"] == []
    status, output = run(*checkpoint, str(FIXTURE / "state-4-last-summary.json"))
    assert len(json.loads(output)["boundary"]["unaccounted"]) == 2

    carry = (
        "lineage", "carry", "--state-dir", state_dir, "--lineage", LINEAGE,
        "--substrate-file", str(FIXTURE / "receiver-large.json"),
    )
    status, output = run(*carry, "--json")
    payload = json.loads(output)
    assert status == 0
    assert payload["authority_transferred"] is False
    assert payload["projection"]["budget"]["limit"] == 10000

    status, output = run(*carry, "--budget-cap", "300")
    assert status == 0
    assert output.startswith("# TORC Carry projection-")
    assert "Receiving it grants no authority." in output
    assert "- Budget: " in output and " of 300 words" in output
    assert DROPPED_WORK in output

    status, output = run(*carry, "--budget-cap", "0", "--json")
    assert status == 1
    assert json.loads(output)["error"] == "InvalidInputError"
    assert run("verify", "--state-dir", state_dir, "--lineage", LINEAGE, "--json")[0] == 0


# --- Regressions from the PR 25 assessment -----------------------------------
#
# The history reader's dispositions and authorship were the under-tested region.
# These tests drive the exact sequences that were reproduced against the PR.

RECEIVER = "p5-receiver"
OTHER = "p5-other"


def _revision(
    revision_id: str,
    substrate: str | None,
    open_work: list[str],
    *,
    event_type: str = "checkpoint",
    resolutions: list[dict[str, str]] | None = None,
    rollback_target: str | None = None,
) -> dict[str, Any]:
    """A minimal in-memory revision for exercising the pure history functions."""

    revision: dict[str, Any] = {
        "revision_id": revision_id,
        "event_type": event_type,
        "actor": {
            "kind": "activation",
            "activation_id": None if substrate is None else f"activation-{substrate}",
            "substrate_id": substrate,
        },
        "canonical_state": {
            "constraints": [],
            "commitments": [],
            "open_work": list(open_work),
            "self_model": {"role": "Finish the export"},
        },
    }
    if resolutions is not None:
        revision["resolutions"] = resolutions
    if rollback_target is not None:
        revision["rollback_context"] = {"target_revision_id": rollback_target}
    return revision


COMPLETED = [{"section": "open_work", "item": DROPPED_WORK, "disposition": "completed"}]


@pytest.mark.parametrize(
    ("chain", "disposition", "unaccounted"),
    (
        pytest.param(
            [
                _revision("r0", RECEIVER, [DROPPED_WORK]),
                _revision("r1", OTHER, [], resolutions=COMPLETED),
                _revision("r2", OTHER, [DROPPED_WORK]),
                _revision("r3", OTHER, []),
            ],
            "unaccounted",
            ["r3"],
            id="resolve-restore-drop",
        ),
        pytest.param(
            [
                _revision("r0", RECEIVER, [DROPPED_WORK]),
                _revision("r1", OTHER, [], resolutions=COMPLETED),
                _revision("r2", OTHER, [DROPPED_WORK]),
                _revision("r3", OTHER, [], event_type="rollback_applied", rollback_target="r1"),
            ],
            "rolled_back",
            [],
            id="resolve-restore-rollback",
        ),
        pytest.param(
            [_revision("r0", RECEIVER, [DROPPED_WORK]), _revision("r1", OTHER, [])],
            "unaccounted",
            ["r1"],
            id="plain-unresolved-removal",
        ),
    ),
)
def test_disposition_describes_the_latest_removal_only(
    chain: list[dict[str, Any]], disposition: str, unaccounted: list[str]
) -> None:
    changes = changes_since_substrate(chain, RECEIVER)

    assert changes is not None
    assert changes["removed"] == {"open_work": [{"item": DROPPED_WORK, "disposition": disposition}]}
    assert [drop["dropped_at_revision_id"] for drop in unaccounted_drops(chain)] == unaccounted


def test_changes_since_receiver_reports_transient_and_late_resolutions() -> None:
    transient = [
        _revision("r0", RECEIVER, ["Define the export schema"]),
        _revision("r1", OTHER, ["Define the export schema", DROPPED_WORK]),
        _revision("r2", OTHER, ["Define the export schema"], resolutions=COMPLETED),
    ]
    late = [
        _revision("r0", OTHER, [DROPPED_WORK]),
        _revision("r1", OTHER, []),
        _revision("r2", RECEIVER, []),
        _revision("r3", OTHER, [], resolutions=COMPLETED),
    ]
    before_baseline = [
        _revision("r0", OTHER, [DROPPED_WORK]),
        _revision("r1", OTHER, [], resolutions=COMPLETED),
        _revision("r2", RECEIVER, []),
        _revision("r3", OTHER, ["Publish the export guide"]),
    ]

    added_then_resolved = changes_since_substrate(transient, RECEIVER)
    resolved_late = changes_since_substrate(late, RECEIVER)
    settled_earlier = changes_since_substrate(before_baseline, RECEIVER)

    # Added and completed while the receiver was away: absent from the net delta,
    # present in the events the receiver is told about.
    assert added_then_resolved is not None
    assert added_then_resolved["added"] == {}
    assert added_then_resolved["removed"] == {
        "open_work": [{"item": DROPPED_WORK, "disposition": "completed"}]
    }
    # Dropped before the baseline, resolved after it: the resolution is news.
    assert resolved_late is not None
    assert resolved_late["removed"] == {
        "open_work": [{"item": DROPPED_WORK, "disposition": "completed"}]
    }
    # Dropped and resolved before the baseline: nothing about it is news.
    assert settled_earlier is not None
    assert settled_earlier["removed"] == {}
    assert settled_earlier["added"] == {"open_work": ["Publish the export guide"]}


def _accept(store: Store, prepared: dict[str, Any], activation_id: str) -> dict[str, Any]:
    template = json.loads(
        (store.state_dir / prepared["reconstruction_template_path"]).read_text(
            encoding="utf-8"
        )
    )
    return resolve_operator_handoff(
        store,
        handoff_id=prepared["handoff_id"],
        target_activation_id=activation_id,
        reconstruction=template,
    )


def _head_state(store: Store) -> dict[str, Any]:
    head = store.get_revision(store.get_lineage(LINEAGE)["head_revision_id"])
    return json.loads(json.dumps(head["canonical_state"]))


def test_changes_since_receiver_survive_a_hand_back(tmp_path: Path) -> None:
    hand_back = _handoff_plan() | {
        "target_substrate": _load("source-substrate.json"),
        "target_activation_id": "activation-returning",
        "target_responsibility": "Resume the export work",
        "rationale": "The original session returns after the review.",
    }
    with Store(tmp_path) as store:
        revisions = _build(store, through=3)
        out = prepare_operator_handoff(
            store, lineage_id=LINEAGE, source_activation_id=ACTIVATION, plan=_handoff_plan()
        )
        assert _accept(store, out, "activation-successor")["disposition"] == "accepted"
        advanced = _head_state(store)
        advanced["open_work"] = [DROPPED_WORK, "Publish the export guide"]
        _checkpoint(
            store,
            advanced,
            activation_id="activation-successor",
            resolutions=[
                {
                    "section": "open_work",
                    "item": "Write the export round-trip test",
                    "disposition": "completed",
                }
            ],
        )
        back = prepare_operator_handoff(
            store,
            lineage_id=LINEAGE,
            source_activation_id="activation-successor",
            plan=hand_back,
        )
        assert _accept(store, back, "activation-returning")["disposition"] == "accepted"
        returning = _carry(store, "source-substrate.json")
        boundary = operator_lineage_status(store, LINEAGE)["boundary"]

    # The accepted hand-back is TORC's bookkeeping, not the returning bearer's work,
    # so the baseline stays at its last real checkpoint and the successor's work shows.
    changes = _sections(returning)["changes-since-receiver"]["content"]
    assert changes["since_revision_id"] == revisions[2]
    assert changes["revisions_since"] == 3
    assert changes["added"] == {"open_work": ["Publish the export guide"]}
    assert changes["removed"] == {
        "open_work": [{"item": "Write the export round-trip test", "disposition": "completed"}]
    }
    assert boundary["self_model"]["bearer_substrate_id"] == "p5-implementer"
    assert boundary["self_model"]["restatement_due"] is False


def test_verbatim_confirmation_is_a_restatement(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        _build(store)
        prepared = prepare_operator_handoff(
            store, lineage_id=LINEAGE, source_activation_id=ACTIVATION, plan=_handoff_plan()
        )
        _accept(store, prepared, "activation-successor")
        inherited = _head_state(store)
        plain = _checkpoint(store, inherited, activation_id="activation-successor")
        confirmed = _checkpoint(
            store,
            inherited,
            activation_id="activation-successor",
            event_type="self_model_revised",
        )
        carry = _carry(store, "receiver-large.json")
        verification = verify_store(store, LINEAGE)

    # A plain checkpoint of the inherited text is not a restatement.
    assert plain["boundary"]["self_model"]["restatement_due"] is True
    # The self_model_revised event is, even when the text is confirmed verbatim.
    answered = confirmed["boundary"]["self_model"]
    assert answered["authored_by_substrate_id"] == "p5-implementer"
    assert answered["restated_by_substrate_id"] == "p5-receiver-large"
    assert answered["restated_at_revision_id"] == confirmed["revision_id"]
    assert answered["restatement_due"] is False
    # The carry shows the confirmation as a confirmation.
    provenance = _sections(carry)["self-model-provenance"]["content"]
    assert provenance["authored_by_substrate_id"] == "p5-implementer"
    assert provenance["restated_by_substrate_id"] == "p5-receiver-large"
    assert provenance["restatement_due"] is False
    assert verification["valid"] is True


def _ledger(store: Store) -> dict[str, Any]:
    authority = store.current_authority(LINEAGE)
    return {
        "head": store.get_lineage(LINEAGE)["head_revision_id"],
        "lease_head": store.get_lease(authority["lease_id"])["head_revision_id"],
        "activation_revision": store.get_activation(ACTIVATION)["revision_id"],
        "revisions": len(store.lineage_revisions(LINEAGE)),
    }


@pytest.mark.parametrize(
    ("resolutions", "message"),
    (
        (
            [{"section": "open_work", "item": "Never existed", "disposition": "completed"}],
            "never dropped",
        ),
        (
            [{"section": "constraints", "item": DROPPED_WORK, "disposition": "completed"}],
            "never dropped",
        ),
        (
            [{"section": "open_work", "item": DROPPED_WORK, "disposition": "done"}],
            "disposition",
        ),
        (["not an object"], "JSON object"),
    ),
)
def test_store_rejects_resolutions_before_any_write(
    tmp_path: Path, resolutions: Any, message: str
) -> None:
    with Store(tmp_path) as store:
        _build(store, through=3)
        before = _ledger(store)
        with pytest.raises(InvalidInputError, match=message):
            store.append_revision(
                LINEAGE,
                _load("state-4-last-summary.json"),
                event_type="checkpoint",
                activation_id=ACTIVATION,
                resolutions=resolutions,
            )
        after = _ledger(store)
        verification = verify_store(store, LINEAGE)

    assert before == after
    assert verification["valid"] is True


def _append_raw(
    store: Store,
    canonical_state: dict[str, Any],
    *,
    event_type: str = "checkpoint",
    resolutions: list[Any] | None = None,
) -> dict[str, Any]:
    """Append a correctly sealed revision around the store's append rules."""

    parent = store.get_revision(store.get_lineage(LINEAGE)["head_revision_id"])
    payload: dict[str, Any] = {
        "schema_version": 1,
        "lineage_id": LINEAGE,
        "revision_id": new_id("revision"),
        "parent_revision_ids": [parent["revision_id"]],
        "created_at": utc_now(),
        "event_type": event_type,
        "actor": {
            "kind": "activation",
            "activation_id": ACTIVATION,
            "substrate_id": "p5-implementer",
        },
        "canonical_state": canonical_state,
        "evidence_refs": [],
    }
    if resolutions is not None:
        payload["resolutions"] = resolutions
    record = seal_record(
        payload, previous_revision_sha256=parent["integrity"]["canonical_payload_sha256"]
    )
    with store.transaction(immediate=True):
        authority = store.current_authority(LINEAGE)
        store._insert_revision(record)
        for table, column, key in (
            ("lineages", "lineage_id", LINEAGE),
            ("leases", "lease_id", authority["lease_id"]),
        ):
            store.connection.execute(
                f"UPDATE {table} SET head_revision_id = ? WHERE {column} = ?",
                (record["revision_id"], key),
            )
        store.connection.execute(
            "UPDATE activations SET revision_id = ? WHERE activation_id = ?",
            (record["revision_id"], ACTIVATION),
        )
    return record


@pytest.mark.parametrize(
    ("resolutions", "code"),
    (
        (
            [{"section": "open_work", "item": "Never existed", "disposition": "completed"}],
            "resolution_invalid",
        ),
        ([{"section": "open_work", "item": "x", "disposition": "done"}], "resolution_invalid"),
    ),
)
def test_verify_reports_a_resolution_stored_around_the_append_rules(
    tmp_path: Path, resolutions: list[Any], code: str
) -> None:
    with Store(tmp_path) as store:
        _build(store, through=3)
        forged = _append_raw(
            store, _load("state-4-last-summary.json"), resolutions=resolutions
        )
        verification = verify_store(store, LINEAGE)
        with pytest.raises(IntegrityError, match=code):
            _checkpoint(store, _load("state-4-last-summary.json"))
        with pytest.raises(IntegrityError, match=code):
            _carry(store, "receiver-large.json")

    assert verification["valid"] is False
    assert (code, forged["revision_id"]) in {
        (error["code"], error["record_id"]) for error in verification["errors"]
    }


def test_verify_reports_an_unknown_event_type(tmp_path: Path) -> None:
    with Store(tmp_path) as store:
        _build(store, through=3)
        bogus = _append_raw(store, _load("state-3-item-completed.json"), event_type="bogus")
        verification = verify_store(store, LINEAGE)

    assert ("event_type_unknown", bogus["revision_id"]) in {
        (error["code"], error["record_id"]) for error in verification["errors"]
    }


@pytest.mark.parametrize(
    "event_type",
    ("rollback_applied", "branch_created", "handoff_accepted", "lineage_created", "bogus"),
)
def test_reserved_event_types_are_refused_before_any_write(
    tmp_path: Path, event_type: str
) -> None:
    with Store(tmp_path) as store:
        _build(store, through=2)
        before = _ledger(store)
        with pytest.raises(InvalidInputError, match="reserved"):
            _checkpoint(
                store, _load("state-3-item-completed.json"), event_type=event_type
            )
        with pytest.raises(InvalidInputError, match="reserved"):
            store.append_revision(
                LINEAGE,
                _load("state-3-item-completed.json"),
                event_type=event_type,
                activation_id=ACTIVATION,
            )
        after = _ledger(store)
        verification = verify_store(store, LINEAGE)
        # The lineage is not poisoned: an ordinary checkpoint still lands.
        later = _checkpoint(
            store, _load("state-3-item-completed.json"), resolutions=_load("resolutions-3.json")
        )

    assert before == after
    assert verification["valid"] is True
    assert later["ok"] is True
    assert later["boundary"]["unaccounted"] == []


def _table_counts(store: Store) -> dict[str, int]:
    return {
        table: store.connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        for table in (
            "substrates",
            "activations",
            "fit_decisions",
            "projections",
            "handoffs",
            "artifacts",
        )
    }


def test_handoff_preparation_stores_nothing_when_an_export_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    real_metadata = operator_module.artifact_metadata

    def fail_on_second_export(*args: Any, **kwargs: Any) -> dict[str, Any]:
        if kwargs["record_kind"] == "handoff_reconstruction_template":
            raise OSError("disk full")
        return real_metadata(*args, **kwargs)

    with Store(tmp_path) as store:
        _build(store)
        before = _table_counts(store)
        monkeypatch.setattr(operator_module, "artifact_metadata", fail_on_second_export)
        with pytest.raises(OSError, match="disk full"):
            prepare_operator_handoff(
                store, lineage_id=LINEAGE, source_activation_id=ACTIVATION, plan=_handoff_plan()
            )
        after = _table_counts(store)
        leftovers = sorted(path.name for path in (store.state_dir / "artifacts").glob("*"))
        failed_verification = verify_store(store, LINEAGE)
        monkeypatch.undo()

        # The same plan, including the same target activation id, now succeeds.
        retried = prepare_operator_handoff(
            store, lineage_id=LINEAGE, source_activation_id=ACTIVATION, plan=_handoff_plan()
        )
        exported = sorted(path.name for path in (store.state_dir / "artifacts").glob("*"))
        verification = verify_store(store, LINEAGE)

    assert after == before
    assert leftovers == []
    assert failed_verification["valid"] is True
    assert retried["ok"] is True
    assert exported == sorted(
        [Path(retried["brief_path"]).name, Path(retried["reconstruction_template_path"]).name]
    )
    assert verification["valid"] is True
