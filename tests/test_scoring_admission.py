"""Only externally pinned, terminal owner evidence may freeze a scoring candidate."""

from __future__ import annotations

import copy
import importlib.util
import sys
from pathlib import Path

import pytest

from torc.canonical import payload_sha256

ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "experiments/session-continuation-001"


def _module(name):
    path = EXPERIMENT / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"continuation_{name}", path)
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(EXPERIMENT))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.pop(0)
    return module


@pytest.fixture(scope="module")
def modules():
    return _module("scoring_admission"), _module("workloads")


@pytest.fixture
def trusted_fixture(tmp_path, modules):
    admission, workloads = modules
    candidate = tmp_path / "candidate"
    workloads.stage("capsule-context", candidate)
    candidate_hash = workloads.tree_sha256(candidate)
    packet = {
        "trial_id": "trial-001",
        "candidate_sha256": candidate_hash,
        "scoring_refs": [{"path": "sealed-hidden-tests", "sha256": "a" * 64}],
    }
    packet_hash = payload_sha256(packet)
    receipt = {
        "trial_id": "trial-001",
        "attempt_id": "attempt-001",
        "candidate_sha256": candidate_hash,
        "packet_sha256": packet_hash,
        "owner_receipt_ref": "trusted-owner-store/attempt-001.json",
        "status": "completed",
        "capture_complete": True,
        "process_tree_absent": True,
    }
    return {
        "admission": admission,
        "workloads": workloads,
        "candidate": candidate,
        "packet": packet,
        "receipt": receipt,
        "receipt_hash": payload_sha256(receipt),
        "packet_hash": packet_hash,
        "destination": tmp_path / "score",
    }


def _freeze(case, **changes):
    values = {
        "workload_id": "capsule-context",
        "candidate": case["candidate"],
        "destination": case["destination"],
        "trial_id": "trial-001",
        "owner_receipt": case["receipt"],
        "expected_receipt_sha256": case["receipt_hash"],
        "packet": case["packet"],
        "expected_packet_sha256": case["packet_hash"],
    }
    values.update(changes)
    return case["admission"].freeze_candidate(**values)


@pytest.mark.parametrize(
    ("change", "message"),
    [
        ({"missing": "capture_complete"}, "missing"),
        ({"status": "running"}, "terminal"),
        ({"capture_complete": False}, "capture"),
        ({"process_tree_absent": False}, "process tree"),
        ({"owner_receipt_ref": ""}, "owner receipt ref"),
        ({"attempt_id": ""}, "attempt"),
        ({"trial_id": "other-trial"}, "trial"),
        ({"candidate_sha256": "0" * 64}, "candidate"),
        ({"packet_sha256": "0" * 64}, "packet"),
    ],
)
def test_missing_nonterminal_or_mismatched_receipt_rejects_before_freeze(
    trusted_fixture, change, message
):
    receipt = copy.deepcopy(trusted_fixture["receipt"])
    missing = change.get("missing")
    if missing:
        receipt.pop(missing)
    else:
        receipt.update(change)
    with pytest.raises(ValueError, match=message):
        _freeze(
            trusted_fixture,
            owner_receipt=receipt,
            expected_receipt_sha256=payload_sha256(receipt),
        )
    assert not trusted_fixture["destination"].exists()


def test_tampered_receipt_or_packet_rejects_external_pin_before_freeze(trusted_fixture):
    receipt = {**trusted_fixture["receipt"], "status": "failed"}
    with pytest.raises(ValueError, match="receipt.*pin"):
        _freeze(trusted_fixture, owner_receipt=receipt)
    assert not trusted_fixture["destination"].exists()

    packet = {**trusted_fixture["packet"], "scoring_refs": []}
    with pytest.raises(ValueError, match="packet.*pin"):
        _freeze(trusted_fixture, packet=packet)
    assert not trusted_fixture["destination"].exists()


@pytest.mark.parametrize("variant", ["extra", "trial", "refs"])
def test_packet_must_have_exact_shape_and_current_bindings(trusted_fixture, variant):
    packet = copy.deepcopy(trusted_fixture["packet"])
    if variant == "extra":
        packet["arm"] = "torc_capsule"
        message = "shape"
    elif variant == "trial":
        packet["trial_id"] = "other-trial"
        message = "trial"
    else:
        packet["scoring_refs"] = []
        message = "scoring refs"
    with pytest.raises(ValueError, match=message):
        _freeze(
            trusted_fixture,
            packet=packet,
            expected_packet_sha256=payload_sha256(packet),
        )
    assert not trusted_fixture["destination"].exists()


def test_stale_candidate_and_packet_reject_before_freeze(trusted_fixture):
    target = trusted_fixture["candidate"] / "src/torc/continuation_context.py"
    target.write_text("# candidate changed after owner capture\n")
    with pytest.raises(ValueError, match="candidate"):
        _freeze(trusted_fixture)
    assert not trusted_fixture["destination"].exists()


def test_prepare_score_rejects_protected_changes_without_destination(trusted_fixture):
    protected = trusted_fixture["candidate"] / "src/torc/p5_capsules.py"
    protected.write_text("# forbidden replacement\n")
    candidate_hash = trusted_fixture["workloads"].tree_sha256(trusted_fixture["candidate"])
    packet = {**trusted_fixture["packet"], "candidate_sha256": candidate_hash}
    packet_hash = payload_sha256(packet)
    receipt = {
        **trusted_fixture["receipt"],
        "candidate_sha256": candidate_hash,
        "packet_sha256": packet_hash,
    }
    with pytest.raises(ValueError, match="protected"):
        _freeze(
            trusted_fixture,
            packet=packet,
            expected_packet_sha256=packet_hash,
            owner_receipt=receipt,
            expected_receipt_sha256=payload_sha256(receipt),
        )
    assert not trusted_fixture["destination"].exists()


def test_candidate_tree_is_rechecked_after_freeze(trusted_fixture, monkeypatch):
    admission = trusted_fixture["admission"]
    prepare_score = admission.prepare_score

    def change_after_freeze(*args, **kwargs):
        job = prepare_score(*args, **kwargs)
        target = trusted_fixture["candidate"] / "src/torc/continuation_context.py"
        target.write_text("# changed after the scoring copy was frozen\n")
        return job

    monkeypatch.setattr(admission, "prepare_score", change_after_freeze)
    with pytest.raises(ValueError, match="changed after"):
        _freeze(trusted_fixture)


@pytest.mark.parametrize("status", ["completed", "failed"])
def test_trusted_terminal_fixture_freezes_without_running_candidate(trusted_fixture, status):
    receipt = {**trusted_fixture["receipt"], "status": status}
    result = _freeze(
        trusted_fixture,
        owner_receipt=receipt,
        expected_receipt_sha256=payload_sha256(receipt),
    )

    assert result["owner_receipt_sha256"] == payload_sha256(receipt)
    assert result["packet_sha256"] == trusted_fixture["packet_hash"]
    assert result["job"]["candidate_sha256"] == trusted_fixture["packet"][
        "candidate_sha256"
    ]
    assert result["requires_qualified_isolated_execution"] is True
    assert result["job"]["requires_qualified_isolated_execution"] is True
    assert trusted_fixture["destination"].is_dir()
    assert not (trusted_fixture["candidate"] / "tests/test_continuation_context.py").exists()
    assert (trusted_fixture["destination"] / "tests/test_continuation_context.py").is_file()
