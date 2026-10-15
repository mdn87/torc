"""Composition uses the carry's expected ID/hash, never a caller's replacement text."""

from __future__ import annotations

import copy
import hashlib
import json
from contextlib import contextmanager

import pytest
from test_carry import (
    ACTIVATION,
    LINEAGE,
    _build,
    _carry,
    _checkpoint,
    _handoff_plan,
    _load,
    _validate,
)

from torc.canonical import canonical_json, payload_sha256, seal_record
from torc.execution_capsules import capsule_binding_is_valid
from torc.operator import (
    create_operator_lineage,
    prepare_operator_handoff,
    resolve_operator_handoff,
)
from torc.store import Store


def _pair(projection):
    return projection["projection_id"], projection["integrity"]["canonical_payload_sha256"]


@contextmanager
def _unchanged(root):
    def files():
        return {
            p.relative_to(root).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*")
            if p.is_file()
        }

    before = files()
    with Store(root, read_only=True) as store:
        dump = list(store.connection.iterdump())
        try:
            yield store
        finally:
            assert list(store.connection.iterdump()) == dump
    assert files() == before


def _prepared(root, receiver="receiver-small.json", **kwargs):
    with Store(root) as store:
        revisions = _build(store)
        projection = _carry(store, receiver, **kwargs)
    return projection, revisions


@pytest.mark.parametrize(
    "receiver,cap,count",
    [
        ("receiver-small.json", None, 8),
        ("receiver-large.json", None, 12),
        ("receiver-large.json", 80, 7),
    ],
)
def test_derive_and_verify_preserve_the_fitted_projection(tmp_path, receiver, cap, count):
    from torc.p5_capsules import derive, verify

    projection, revisions = _prepared(tmp_path, receiver, budget_cap=cap)
    with _unchanged(tmp_path) as store:
        capsule, control, record = derive(store, *_pair(projection))
        verify(store, *_pair(projection), capsule, control, record)
    assert len(control["claim_sources"]) == count
    assert capsule_binding_is_valid(capsule, control)
    _validate("execution-capsule.schema.json", capsule)
    _validate("claim-control-envelope.schema.json", control)
    assert record["budget"] == projection["budget"]
    assert record["omitted_sections"] == projection["omitted_sections"]
    assert record["redactions"] == projection["redactions"]
    assert record["authority_transferred"] is False
    assert record["target_substrate_id"] == projection["target_substrate_id"]
    assert record["compiler_version"] == record["policy_version"] == "p5-1"
    assert record["projection_record_sha256"] == _pair(projection)[1]
    assert record["capsule_sha256"] == payload_sha256(capsule)
    assert record["control_sha256"] == payload_sha256(control)
    if receiver == "receiver-small.json":
        assert capsule["claims"] == {
            "constraints": {"x1": "Do not add a network dependency"},
            "commitments": {"c1": "Keep the export format backward compatible"},
            "open-work": {"w1": "Write the export round-trip test"},
            "unaccounted-constraints-1": {"za1": "Never write outside the state directory"},
            "unaccounted-open_work-2": {"zb1": "Handle exports larger than memory"},
            "goals": {"g1": "Ship a lineage export command", "g2": "Document the export command"},
            "settled-decisions": {"d1": "Exports are written as UTF-8 JSON"},
        }
        assert record["claim_paths"]["zb1"] == {
            "projection_section_id": "unaccounted-open_work-2",
            "field_path": "item",
        }
        assert control["claim_sources"]["zb1"]["source_ref"] == f"{revisions[2]}:open_work"
        assert "authority" in record["recorded_fields"]["session-purpose"]
        assert "receiver-fit" in record["recorded_fields"]
        assert "self-model-provenance" in record["recorded_fields"]


def test_expected_hash_is_required_even_for_a_valid_stored_projection(tmp_path):
    from torc.p5_capsules import CapsuleCompositionError, derive

    projection, _ = _prepared(tmp_path)
    with _unchanged(tmp_path) as store:
        with pytest.raises(CapsuleCompositionError, match="projection_hash_unexpected"):
            derive(store, projection["projection_id"], "0" * 64)


def _reseal_composition(capsule, control, record):
    control["capsule_sha256"] = payload_sha256(capsule)
    record["capsule_sha256"] = payload_sha256(capsule)
    record["control_sha256"] = payload_sha256(control)
    assert capsule_binding_is_valid(capsule, control)


@pytest.mark.parametrize(
    "change,code",
    [
        ("claim_text", "claim_text_mismatch"),
        ("source", "claim_source_mismatch"),
        ("field_path", "claim_source_mismatch"),
        ("drop_handle", "claim_set_mismatch"),
        ("drop_section", "claim_set_mismatch"),
        ("drop_history", "claim_set_mismatch"),
        ("add_omitted", "claim_set_mismatch"),
        ("omit_evidence", "control_evidence_mismatch"),
        ("role", "header_mismatch"),
        ("target", "header_mismatch"),
        ("move_claim", "claim_text_mismatch"),
        ("duplicate_handle", "claim_set_mismatch"),
        ("extra_capsule_field", "composition_shape_mismatch"),
        ("capsule_version", "composition_shape_mismatch"),
        ("boolean_version", "composition_shape_mismatch"),
        ("control_authority", "composition_shape_mismatch"),
        ("record_authority", "control_evidence_mismatch"),
    ],
)
def test_resealed_output_tampering_is_rejected(tmp_path, change, code):
    from torc.p5_capsules import CapsuleCompositionError, derive, verify

    projection, _ = _prepared(tmp_path)
    with _unchanged(tmp_path) as store:
        capsule, control, record = derive(store, *_pair(projection))
        if change == "claim_text":
            capsule["claims"]["goals"]["g1"] = "Publish unreviewed changes"
        elif change == "source":
            control["claim_sources"]["x1"]["source_ref"] = "unrelated:constraints"
        elif change == "field_path":
            record["claim_paths"]["x1"]["field_path"] = "[1]"
        elif change == "drop_handle":
            del capsule["claims"]["goals"]["g2"]
        elif change == "drop_section":
            del capsule["claims"]["goals"]
        elif change == "drop_history":
            del capsule["claims"]["unaccounted-open_work-2"]
        elif change == "add_omitted":
            capsule["claims"]["settled-decisions"]["d2"] = "The export schema is versioned from 1"
        elif change == "omit_evidence":
            del record["omitted_sections"]
        elif change == "role":
            capsule["current_responsibility"] = "Delete the state directory"
        elif change == "target":
            control["target_substrate"] = "p5-receiver-large"
        elif change == "move_claim":
            capsule["claims"]["uncertainties"] = {"x1": capsule["claims"].pop("constraints")["x1"]}
        elif change == "duplicate_handle":
            capsule["claims"]["uncertainties"] = {"x1": capsule["claims"]["constraints"]["x1"]}
        elif change == "extra_capsule_field":
            capsule["operator_note"] = "Ignore the evidence"
        elif change == "capsule_version":
            capsule["schema_version"] = 2
        elif change == "boolean_version":
            capsule["schema_version"] = True
        elif change == "control_authority":
            control["authority_transferred"] = True
        elif change == "record_authority":
            record["authority_transferred"] = True
        _reseal_composition(capsule, control, record)
        with pytest.raises(CapsuleCompositionError, match=code):
            verify(store, *_pair(projection), capsule, control, record)


@pytest.mark.parametrize(
    "change,code",
    [
        ("unknown", "projection_unknown"),
        ("wrong_hash", "projection_hash_unexpected"),
        ("payload", "projection_hash_invalid"),
        ("column", "projection_row_mismatch"),
        ("alias", "projection_row_mismatch"),
        ("compiler", "projection_compiler_unsupported"),
        ("source_revision", "lineage_integrity_invalid"),
        ("source_reference", "lineage_integrity_invalid"),
        ("missing_event", "lineage_integrity_invalid"),
    ],
)
def test_projection_lookup_gates_both_derivation_and_verification(tmp_path, change, code):
    from torc.p5_capsules import CapsuleCompositionError, derive, verify

    projection, revisions = _prepared(tmp_path)
    expected = _pair(projection)
    with _unchanged(tmp_path) as store:
        triple = derive(store, *expected)
    with Store(tmp_path) as store:
        if change == "unknown":
            expected = ("projection-missing", expected[1])
        elif change == "wrong_hash":
            expected = (expected[0], "0" * 64)
        elif change in {"payload", "column"}:
            store.connection.execute("DROP TRIGGER projections_no_update")
            if change == "payload":
                projection["included_sections"][1]["content"] = ["Network access is required"]
                store.connection.execute(
                    "UPDATE projections SET payload_json = ? WHERE projection_id = ?",
                    (canonical_json(projection), expected[0]),
                )
            else:
                store.connection.execute(
                    "UPDATE projections SET target_substrate_id = ? WHERE projection_id = ?",
                    ("p5-implementer", expected[0]),
                )
        elif change == "alias":
            store.insert_hashed_record("projections", "projection-alias", projection)
            expected = ("projection-alias", expected[1])
        elif change in {"compiler", "source_reference"}:
            changed = copy.deepcopy(projection)
            changed["projection_id"] = "projection-changed"
            if change == "compiler":
                changed["compiler_version"] = "p0-1"
            else:
                changed["included_sections"][0]["source_ref"] = "foreign-revision:identity"
            changed = seal_record(changed)
            store.insert_hashed_record("projections", changed["projection_id"], changed)
            expected = _pair(changed)
        else:
            revision = store.get_revision(revisions[-1])
            if change == "missing_event":
                del revision["event_type"]
            else:
                revision["canonical_state"]["constraints"] = ["Network access is required"]
            store.connection.execute("DROP TRIGGER revisions_no_update")
            store.connection.execute(
                "UPDATE revisions SET payload_json = ? WHERE revision_id = ?",
                (canonical_json(revision), revisions[-1]),
            )
        store.connection.commit()
    with _unchanged(tmp_path) as store:
        for call in (lambda: derive(store, *expected), lambda: verify(store, *expected, *triple)):
            with pytest.raises(CapsuleCompositionError, match=code) as failure:
                call()
            if code == "lineage_integrity_invalid":
                assert failure.value.errors


@pytest.mark.parametrize(
    "field,value,code",
    [
        ("goals", [""], "claim_item_invalid"),
        ("methods", [{"step": "test first"}], "claim_item_invalid"),
        ("methods", "test first", "claim_section_invalid"),
        ("methods", 7, "claim_section_invalid"),
        ("settled_decisions", "", "claim_section_invalid"),
        ("settled_decisions", {"format": "JSON"}, "claim_section_invalid"),
        ("role", None, "header_missing"),
        ("label", None, "header_missing"),
        ("label", ["P5", "fixture"], "header_missing"),
        ("empty", None, "claims_empty"),
    ],
)
def test_unrenderable_carry_is_rejected_without_repair(tmp_path, field, value, code):
    from torc.p5_capsules import CapsuleCompositionError, derive

    state = _load("state-1-created.json")
    if field == "empty":
        state = {key: [] if isinstance(item, list) else item for key, item in state.items()}
        state["self_model"] = {"role": "Implement the export"}
    else:
        owner = (
            state["identity"]
            if field == "label"
            else (
                state["self_model"] if field in {"role", "methods", "settled_decisions"} else state
            )
        )
        if value is None:
            del owner[field]
        else:
            owner[field] = value
    with Store(tmp_path) as store:
        create_operator_lineage(
            store,
            lineage_id=LINEAGE,
            canonical_state=state,
            substrate=_load("source-substrate.json"),
            activation_id=ACTIVATION,
        )
        projection = _carry(store, "receiver-large.json")
    with _unchanged(tmp_path) as store:
        with pytest.raises(CapsuleCompositionError, match=code):
            derive(store, *_pair(projection))


def test_identity_details_remain_in_the_control_record(tmp_path):
    from torc.p5_capsules import derive, verify

    state = _load("state-1-created.json")
    state["identity"]["mission"] = "Never publish to the production index"
    with Store(tmp_path) as store:
        create_operator_lineage(
            store,
            lineage_id=LINEAGE,
            canonical_state=state,
            substrate=_load("source-substrate.json"),
            activation_id=ACTIVATION,
        )
        projection = _carry(store, "receiver-large.json")
    with _unchanged(tmp_path) as store:
        capsule, control, record = derive(store, *_pair(projection))
        verify(store, *_pair(projection), capsule, control, record)
    assert len(control["claim_sources"]) == 9
    assert record["recorded_fields"]["identity-role"]["identity"] == {
        "mission": "Never publish to the production index",
    }


@pytest.mark.parametrize("silent,count", [(False, 13), (True, 14)])
def test_returning_receiver_keeps_history_dispositions_and_repeated_items(tmp_path, silent, count):
    from torc.p5_capsules import derive, verify

    with Store(tmp_path) as store:
        revisions = _build(store, through=3)
        prepared = prepare_operator_handoff(
            store,
            lineage_id=LINEAGE,
            source_activation_id=ACTIVATION,
            plan=_handoff_plan(),
        )
        template = json.loads(
            (store.state_dir / prepared["reconstruction_template_path"]).read_text()
        )
        resolve_operator_handoff(
            store,
            handoff_id=prepared["handoff_id"],
            target_activation_id="activation-successor",
            reconstruction=template,
        )
        state = copy.deepcopy(
            store.get_revision(store.get_lineage(LINEAGE)["head_revision_id"])["canonical_state"]
        )
        state["open_work"] = ["Publish the export guide"]
        if not silent:
            state["open_work"].insert(0, "Handle exports larger than memory")
        _checkpoint(
            store,
            state,
            activation_id="activation-successor",
            resolutions=[
                {
                    "section": "open_work",
                    "item": "Write the export round-trip test",
                    "disposition": "completed",
                }
            ],
        )
        projection = _carry(store, "source-substrate.json")
    with _unchanged(tmp_path) as store:
        capsule, control, record = derive(store, *_pair(projection))
        verify(store, *_pair(projection), capsule, control, record)
    assert len(control["claim_sources"]) == count
    key = "zb1" if silent else "za1"
    assert capsule["claims"]["changes-since-receiver.removed.open_work.completed"] == {
        key: "Write the export round-trip test",
    }
    assert record["claim_paths"][key]["field_path"] == "removed.open_work[0].item"
    assert control["claim_sources"][key]["source_ref"] == f"{revisions[2]}:canonical_state"
    assert record["recorded_fields"]["changes-since-receiver"]["added"] == {
        "open_work": ["Publish the export guide"],
    }
    if silent:
        assert (
            capsule["claims"]["unaccounted-open_work-1"]["za1"]
            == (capsule["claims"]["changes-since-receiver.removed.open_work.unaccounted"]["zc1"])
        )


def test_substitution_fails_but_an_older_correctly_bound_projection_still_verifies(tmp_path):
    from torc.p5_capsules import CapsuleCompositionError, derive, verify

    projection, _ = _prepared(tmp_path)
    with Store(tmp_path) as store:
        large = _carry(store, "receiver-large.json")
    with _unchanged(tmp_path) as store:
        small_triple = derive(store, *_pair(projection))
        large_triple = derive(store, *_pair(large))
        with pytest.raises(CapsuleCompositionError, match="composition_unbound"):
            verify(store, *_pair(projection), *large_triple)
    with Store(tmp_path) as store:
        _checkpoint(store, _load("state-4-last-summary.json"))
    with _unchanged(tmp_path) as store:
        verify(store, *_pair(projection), *small_triple)


def test_bad_projection_elsewhere_in_the_lineage_prevents_publication(tmp_path):
    from torc.p5_capsules import CapsuleCompositionError, derive

    projection, _ = _prepared(tmp_path)
    forged = copy.deepcopy(projection)
    forged["projection_id"] = "projection-forged"
    forged["included_sections"][0]["source_ref"] = "foreign:identity"
    with Store(tmp_path) as store:
        store.insert_hashed_record("projections", forged["projection_id"], seal_record(forged))
    with _unchanged(tmp_path) as store:
        with pytest.raises(CapsuleCompositionError, match="lineage_integrity_invalid") as failure:
            derive(store, *_pair(projection))
    assert [(e["code"], e["record_id"]) for e in failure.value.errors] == [
        ("projection_source_ref_invalid", "projection-forged"),
    ]


def test_projection_capsule_cli_is_a_read_only_consumer(tmp_path, capsys):
    from torc.cli import main

    projection, _ = _prepared(tmp_path)
    argv = [
        "projection",
        "capsule",
        "--state-dir",
        str(tmp_path),
        "--projection",
        _pair(projection)[0],
        "--record-sha256",
        _pair(projection)[1],
        "--json",
    ]
    with _unchanged(tmp_path):
        assert main(argv) == 0
        payload = json.loads(capsys.readouterr().out)
        assert payload["report_kind"] == "projection_capsule"
        assert payload["trusted"] is True
        assert payload["canonical"] is False
        assert payload["authority_transferred"] is False
        assert len(payload["control"]["claim_sources"]) == 8
        argv[-2] = "0" * 64
        assert main(argv) == 1
        refusal = json.loads(capsys.readouterr().out)
        assert refusal["trusted"] is False
        assert refusal["code"] == "projection_hash_unexpected"
        assert "capsule" not in refusal


def test_capsule_cli_does_not_create_a_missing_store(tmp_path, capsys):
    from torc.cli import main

    missing = tmp_path / "absent"
    assert (
        main(
            [
                "projection",
                "capsule",
                "--state-dir",
                str(missing),
                "--projection",
                "missing",
                "--record-sha256",
                "0" * 64,
                "--json",
            ]
        )
        == 1
    )
    assert json.loads(capsys.readouterr().out)["trusted"] is False
    assert not missing.exists()


def test_handoff_projection_keeps_target_responsibility_off_model(tmp_path):
    from torc.p5_capsules import derive, verify

    with Store(tmp_path) as store:
        _build(store, through=3)
        prepared = prepare_operator_handoff(
            store,
            lineage_id=LINEAGE,
            source_activation_id=ACTIVATION,
            plan=_handoff_plan(),
        )
        projection = store.get_hashed_record(
            "projections", "projection_id", prepared["projection_id"]
        )
    with _unchanged(tmp_path) as store:
        capsule, control, record = derive(store, *_pair(projection))
        verify(store, *_pair(projection), capsule, control, record)
    assert capsule["handoff_reason"] == "model_succession"
    assert record["recorded_fields"]["handoff-purpose"]["target_responsibility"] == (
        "Finish the lineage export command"
    )


def test_a_resealed_record_with_its_own_pair_is_not_writer_authentication(tmp_path):
    from torc.p5_capsules import derive, verify

    projection, _ = _prepared(tmp_path)
    changed = copy.deepcopy(projection)
    changed["projection_id"] = "projection-resealed"
    changed["included_sections"][1]["content"].append("Caller authored this extra constraint")
    changed = seal_record(changed)
    with Store(tmp_path) as store:
        store.insert_hashed_record("projections", changed["projection_id"], changed)
    with _unchanged(tmp_path) as store:
        capsule, control, record = derive(store, *_pair(changed))
        verify(store, *_pair(changed), capsule, control, record)
    assert capsule["claims"]["constraints"]["x2"] == "Caller authored this extra constraint"


def test_unclassified_projection_sections_are_not_silently_dropped(tmp_path):
    from torc.p5_capsules import CapsuleCompositionError, derive

    projection, _ = _prepared(tmp_path)
    projection["projection_id"] = "projection-future-section"
    projection["included_sections"].append(
        {
            "section_id": "future-rules",
            "source_ref": projection["source_revision_id"] + ":self_model",
            "content": ["Keep this instruction"],
            "required": True,
            "priority": 100,
            "estimated_units": 3,
        }
    )
    projection = seal_record(projection)
    with Store(tmp_path) as store:
        store.insert_hashed_record("projections", projection["projection_id"], projection)
    with _unchanged(tmp_path) as store:
        with pytest.raises(CapsuleCompositionError, match="section_unclassified"):
            derive(store, *_pair(projection))


def test_prefix_collision_cannot_publish_a_partly_overwritten_control(tmp_path, monkeypatch):
    from torc import p5_capsules

    state = _load("state-1-created.json")
    state["constraints"] = [f"Constraint {i}" for i in range(11)]
    with Store(tmp_path) as store:
        create_operator_lineage(
            store,
            lineage_id=LINEAGE,
            canonical_state=state,
            substrate=_load("source-substrate.json"),
            activation_id=ACTIVATION,
        )
        projection = _carry(store, "receiver-large.json")
    monkeypatch.setitem(p5_capsules.CLAIM_PREFIXES, "constraints", "c")
    monkeypatch.setitem(p5_capsules.CLAIM_PREFIXES, "commitments", "c1")
    with _unchanged(tmp_path) as store:
        with pytest.raises(ValueError, match="claim id collision: c11"):
            p5_capsules.derive(store, *_pair(projection))
