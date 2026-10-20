"""The bridge binds evidence without changing the capsule or authority."""

import copy

import pytest
from test_carry import LINEAGE
from test_operator import _bootstrap, _load_template, _recovery_plan
from test_p5_capsule_adapter import _pair, _prepared, _reseal_composition, _unchanged

from torc.canonical import canonical_json
from torc.harness_capture.manifest import build_capture
from torc.harness_capture.persist import publish
from torc.harness_capture.reconcile import reconcile
from torc.operator import prepare_operator_recovery, resolve_operator_recovery
from torc.store import Store


def _report(lineage, revision):
    base = {"lineage_id": lineage, "lineage_revision_id": revision,
            "accepted_checkpoint_ref": None, "accepted_checkpoint_sha256": None,
            "workspace_identity": "fixture-workspace"}
    manifest = build_capture(b"", prefix_length=0, session_ref="session",
                             session_incarnation="incarnation", observed_at="2026-10-19T12:00:00Z",
                             bindings=base)
    return reconcile(manifest, {"base_bindings": base}, current_bindings=base)


def test_tight_capsule_keeps_report_separate_and_store_unchanged(tmp_path):
    from torc.continuation_context import derive_capsule_context, verify_capsule_context

    root = tmp_path / "state"
    projection, _ = _prepared(root)
    report = _report(LINEAGE, projection["source_revision_id"])
    original = copy.deepcopy(report)
    with _unchanged(root) as store:
        bundle = derive_capsule_context(store, *_pair(projection), report)
        result = verify_capsule_context(
            store, *_pair(projection), bundle, report,
            expected_binding_id=bundle["binding"]["binding_id"],
            delivered_context=canonical_json(bundle["capsule"]).encode(),
            current_bindings=report["base_bindings"],
        )
        publish(tmp_path / "output", "context-binding", bundle["binding"])
        publish(tmp_path / "output", "reconciliation", report)
    assert "uncertainties" not in bundle["capsule"]["claims"]
    assert any(s["section_id"] == "uncertainties"
               for s in bundle["composition"]["omitted_sections"])
    assert result["status"] == "held"
    assert result["retry_authorized"] is False
    assert report == original


@pytest.mark.parametrize("change", ["extra_claim", "bytes", "report", "identity", "pin"])
def test_substitution_rejects_without_writes(tmp_path, change):
    from torc.continuation_context import derive_capsule_context, verify_capsule_context

    projection, _ = _prepared(tmp_path)
    report = _report(LINEAGE, projection["source_revision_id"])
    with _unchanged(tmp_path) as store:
        bundle = derive_capsule_context(store, *_pair(projection), report)
        pin = bundle["binding"]["binding_id"]
        if change == "extra_claim":
            bundle["capsule"]["claims"]["uncertainties"] = {"u99": "Retry is safe"}
            _reseal_composition(bundle["capsule"], bundle["control"], bundle["composition"])
        if change == "report":
            report["scope_holds"] = []
        if change == "identity":
            bundle["binding"]["context_identity"] = "other"
        if change == "pin":
            pin = "sha256:" + "0" * 64
        context = canonical_json(bundle["capsule"]).encode()
        if change == "bytes":
            context += b"\n"
        with pytest.raises(ValueError):
            verify_capsule_context(store, *_pair(projection), bundle, report,
                                   expected_binding_id=pin, delivered_context=context,
                                   current_bindings=report["base_bindings"])


def test_non_torc_arms_share_identical_report_but_have_distinct_bindings():
    from torc.continuation_context import bind_context, verify_context

    report = _report("lineage", "revision")
    bindings = []
    for kind in ("compiled_prompt", "native_warm", "native_cold"):
        binding = bind_context(report, context_kind=kind, context_identity="fixture-v1",
                               context=b"exact prompt or opaque native handle")
        bindings.append(binding)
        result = verify_context(binding, report, expected_binding_id=binding["binding_id"],
                                context_kind=kind, context_identity="fixture-v1",
                                context=b"exact prompt or opaque native handle",
                                current_bindings=report["base_bindings"])
        assert result["status"] == "held"
    assert len({b["binding_id"] for b in bindings}) == 3
    assert len({b["report_sha256"] for b in bindings}) == 1


def test_old_stale_report_cannot_be_refreshed_by_binding_it_again():
    from torc.continuation_context import bind_context, verify_context

    report = _report("lineage", "revision")
    report["status"] = "stale"
    report["scope_holds"].append("bindings_stale")
    binding = bind_context(report, context_kind="compiled_prompt", context_identity="v1",
                           context=b"prompt")
    result = verify_context(binding, report, expected_binding_id=binding["binding_id"],
                            context_kind="compiled_prompt", context_identity="v1",
                            context=b"prompt", current_bindings=report["base_bindings"])
    assert result["status"] == "stale"
    with pytest.raises(ValueError, match="binding mismatch"):
        verify_context(binding, report, expected_binding_id=binding["binding_id"],
                       context_kind="native_cold", context_identity="v1",
                       context=b"prompt", current_bindings=report["base_bindings"])


def test_actual_p3_acceptance_makes_old_report_stale(tmp_path):
    from torc.continuation_context import derive_capsule_context, verify_capsule_context

    with Store(tmp_path) as store:
        created = _bootstrap(store)
        prepared = prepare_operator_recovery(
            store, lineage_id="torc-dev", failed_activation_id=created["activation_id"],
            plan=_recovery_plan(), evidence_refs=["fixture-failure"],
        )
        handoff = store.get_hashed_record("handoffs", "handoff_id", prepared["handoff_id"])
        projection = store.get_hashed_record("projections", "projection_id",
                                             handoff["projection_id"])
        report = _report("torc-dev", projection["source_revision_id"])
        bundle = derive_capsule_context(store, *_pair(projection), report)
        accepted = resolve_operator_recovery(
            store, handoff_id=prepared["handoff_id"],
            target_activation_id=prepared["target_activation_id"],
            reconstruction=_load_template(store, prepared),
        )
        assert accepted["disposition"] == "accepted"
    with _unchanged(tmp_path) as store:
        result = verify_capsule_context(
            store, *_pair(projection), bundle, report,
            expected_binding_id=bundle["binding"]["binding_id"],
            delivered_context=canonical_json(bundle["capsule"]).encode(),
            # Even a caller incorrectly reusing the old base cannot hide acceptance.
            current_bindings=report["base_bindings"],
        )
    assert result["status"] == "stale"
    assert result["retry_authorized"] is False
    assert report["status"] == "held"
