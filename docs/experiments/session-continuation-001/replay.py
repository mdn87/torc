"""Reproduce the offline milestone report; no model, hook or network execution."""

from __future__ import annotations

import argparse
import hashlib
import json
import tempfile
from pathlib import Path

from torc.canonical import canonical_json
from torc.continuation_context import (
    bind_context,
    derive_capsule_context,
    verify_capsule_context,
)
from torc.continuation_usage import account_task
from torc.harness_capture.manifest import build_capture
from torc.harness_capture.persist import publish
from torc.harness_capture.reconcile import reconcile
from torc.projections import compile_receiver_projection
from torc.store import Store

ROOT = Path(__file__).resolve().parents[3]
HERE = Path(__file__).resolve().parent
P5 = ROOT / "examples/p5-dropped-work"
TIME = "2026-10-19T12:00:00Z"


def _load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def _files(root):
    return {str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
            for p in root.rglob("*") if p.is_file()}


def replay(output: Path) -> dict:
    """Fixture setup owns its disposable state; the measured bridge is read-only."""
    with tempfile.TemporaryDirectory(prefix="torc-offline-state-") as directory:
        root = Path(directory)
        with Store(root) as store:
            source = _load(P5 / "source-substrate.json")
            receiver = _load(P5 / "receiver-small.json")
            store.register_substrate(source)
            store.register_substrate(receiver)
            store.create_lineage("offline-lineage", _load(P5 / "state-1-created.json"),
                                 revision_id="offline-r1", created_at=TIME)
            store.create_activation("offline-lineage", "offline-r1", source["substrate_id"],
                                    activation_id="offline-activation", started_at=TIME)
            store.acquire_lease("offline-lineage", "offline-activation",
                                lease_id="offline-lease", issued_at=TIME)
            for n, filename in enumerate(("state-2-work-added.json", "state-3-item-completed.json",
                                          "state-4-last-summary.json"), 2):
                store.append_revision(
                    "offline-lineage", _load(P5 / filename), event_type="checkpoint",
                    activation_id="offline-activation", revision_id=f"offline-r{n}",
                    created_at=TIME,
                    resolutions=_load(P5 / "resolutions-3.json") if n == 3 else None,
                )
            projection = compile_receiver_projection(
                store, lineage_id="offline-lineage", source_revision_id="offline-r4",
                receiver_substrate_id=receiver["substrate_id"], purpose="session_start",
                projection_id="offline-projection", compiled_at=TIME,
            )
        before = _files(root)
        base = {"lineage_id": "offline-lineage", "lineage_revision_id": "offline-r4",
                "accepted_checkpoint_ref": None, "accepted_checkpoint_sha256": None,
                "workspace_identity": "synthetic-workspace-v1"}
        raw = (HERE / "fixtures/interrupted.jsonl").read_bytes()
        capture = build_capture(raw, prefix_length=len(raw), session_ref="offline-session",
                                session_incarnation="offline-incarnation", observed_at=TIME,
                                bindings=base)
        report = reconcile(capture, {"base_bindings": base}, current_bindings=base)
        with Store(root, read_only=True) as store:
            dump = list(store.connection.iterdump())
            pair = projection["projection_id"], projection["integrity"]["canonical_payload_sha256"]
            bundle = derive_capsule_context(store, *pair, report)
            result = verify_capsule_context(
                store, *pair, bundle, report,
                expected_binding_id=bundle["binding"]["binding_id"],
                delivered_context=canonical_json(bundle["capsule"]).encode("utf-8"),
                current_bindings=base,
            )
            assert list(store.connection.iterdump()) == dump
        references = {}
        for kind, payload in (("capture", capture), ("reconciliation", report),
                              ("capsule-bundle", bundle), ("context-binding", bundle["binding"])):
            references[kind] = publish(output, kind, payload).relative_to(output).as_posix()
        for kind in ("compiled_prompt", "native_warm", "native_cold"):
            binding = bind_context(report, context_kind=kind, context_identity="synthetic-v1",
                                   context=b"synthetic prompt or opaque native handle")
            path = publish(output, "context-binding", binding)
            references[kind] = path.relative_to(output).as_posix()
        unchanged = before == _files(root)
        assert unchanged
    usage = []
    for task in _load(HERE / "fixtures/offline-usage.json")["cases"]:
        accounting = account_task(task)
        path = publish(output, "usage", accounting)
        usage.append({key: accounting[key] for key in (
            "task_id", "input_sha256", "attempt_count", "failed_attempt_count",
            "fallback_attempt_count", "request_count", "totals", "known_subtotals",
            "uncached_processed_token_proxy", "proxy_unavailable_reason", "total_context_tokens",
            "api_cost", "api_cost_unavailable_reason",
        )} | {"artifact": path.relative_to(output).as_posix()})
    sources = [*P5.glob("*.json"), *(HERE / "fixtures").glob("*"), Path(__file__)]
    sources += [ROOT / "src/torc" / name for name in (
        "continuation_context.py", "continuation_usage.py", "experiment_usage.py",
        "p5_capsules.py", "projections.py", "canonical.py", "store.py", "verify.py",
        "execution_capsules.py", "history.py", "harness_capture/manifest.py",
        "harness_capture/parser.py", "harness_capture/classify.py", "harness_capture/reconcile.py",
        "harness_capture/persist.py",
    )]
    return {
        "schema_version": "torc.offline_continuation_report.v0", "baseline_commit": "a798bbc",
        "evidence_kind": "synthetic_mechanics_only", "live_model_trials": 0,
        "state_store_unchanged": unchanged, "bridge": result,
        "capsule_omits_uncertainties": "uncertainties" not in bundle["capsule"]["claims"],
        "artifacts": references, "usage_cases": usage,
        "source_sha256": {p.relative_to(ROOT).as_posix(): hashlib.sha256(p.read_bytes()).hexdigest()
                          for p in sorted(sources)},
        "savings_conclusion": "unmeasured; no model trials or adoption evidence",
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True,
                        help="private derived-output directory outside canonical state")
    args = parser.parse_args()
    print(json.dumps(replay(args.output_dir), sort_keys=True, indent=2))
