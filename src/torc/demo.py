"""Deterministic local P0 handoff demonstration."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .errors import TorcError
from .fit import evaluate_fit
from .handoffs import expected_reconstruction, prepare_handoff, resolve_handoff
from .projections import compile_projection
from .store import Store
from .verify import artifact_metadata, verify_store

_TIMES = {
    "lineage": "2026-08-06T12:00:00Z",
    "source_activation": "2026-08-06T12:01:00Z",
    "source_lease": "2026-08-06T12:02:00Z",
    "checkpoint": "2026-08-06T12:03:00Z",
    "self_model": "2026-08-06T12:04:00Z",
    "fit": "2026-08-06T12:05:00Z",
    "projection": "2026-08-06T12:06:00Z",
    "handoff": "2026-08-06T12:07:00Z",
    "target_activation": "2026-08-06T12:08:00Z",
    "result": "2026-08-06T12:09:00Z",
}


def run_demo(state_dir: Path | str) -> dict[str, Any]:
    with Store(state_dir) as store:
        count = store.connection.execute("SELECT COUNT(*) FROM lineages").fetchone()[0]
        if count:
            raise TorcError("demo state directory already contains a lineage")
        substrate_a, substrate_b = _substrates()
        store.register_substrate(substrate_a)
        store.register_substrate(substrate_b)
        initial = store.create_lineage(
            "demo-lineage",
            _initial_state(),
            revision_id="revision-demo-0001",
            created_at=_TIMES["lineage"],
        )
        source = store.create_activation(
            "demo-lineage",
            initial["revision_id"],
            "substrate-a",
            activation_id="activation-source",
            started_at=_TIMES["source_activation"],
        )
        store.acquire_lease(
            "demo-lineage",
            source["activation_id"],
            lease_id="lease-source",
            issued_at=_TIMES["source_lease"],
        )
        authority_before = store.current_authority("demo-lineage")

        checkpoint_state = initial["canonical_state"] | {
            "open_work": [
                "Independently review the P0 handoff implementation",
                "Compare TORC against the compiled-prompt baseline after P0",
            ]
        }
        store.append_revision(
            "demo-lineage",
            checkpoint_state,
            event_type="checkpoint",
            activation_id=source["activation_id"],
            revision_id="revision-demo-0002",
            created_at=_TIMES["checkpoint"],
            evidence_refs=["artifact-p0-implementation"],
        )
        self_model_state = checkpoint_state | {
            "self_model": checkpoint_state["self_model"]
            | {
                "role": "Complete implementation and transfer to independent review",
                "methods": [
                    "Preserve required continuity before optional context",
                    "Keep authority transfer acceptance-gated",
                    "Report inherited facts separately from new inference",
                ],
            }
        }
        source_revision = store.append_revision(
            "demo-lineage",
            self_model_state,
            event_type="self_model_revised",
            activation_id=source["activation_id"],
            revision_id="revision-demo-0003",
            created_at=_TIMES["self_model"],
            evidence_refs=["artifact-p0-tests"],
        )
        fit = evaluate_fit(
            store,
            lineage_id="demo-lineage",
            source_revision_id=source_revision["revision_id"],
            source_substrate_id="substrate-a",
            task_phase="independent-review",
            requirements={
                "capabilities": ["repository_read", "independent_review"],
                "policy_labels": ["local-synthetic"],
                "minimum_context_units": 60,
            },
            fit_decision_id="fit-demo-review",
            decided_at=_TIMES["fit"],
        )
        projection = compile_projection(
            store,
            lineage_id="demo-lineage",
            source_revision_id=source_revision["revision_id"],
            target_substrate_id=fit["selected_substrate_id"],
            budget_limit=70,
            handoff_reason="task_phase_transition",
            target_responsibility="Independently review the P0 handoff implementation",
            projection_id="projection-demo-review",
            compiled_at=_TIMES["projection"],
        )
        snapshot = prepare_handoff(
            store,
            lineage_id="demo-lineage",
            source_activation_id=source["activation_id"],
            fit_decision_id=fit["fit_decision_id"],
            projection_id=projection["projection_id"],
            reason_code="task_phase_transition",
            rationale="Implementation completed and now requires independent review.",
            handoff_id="handoff-demo-review",
            prepared_at=_TIMES["handoff"],
        )
        authority_after_prepare = store.current_authority("demo-lineage")
        target = store.create_activation(
            "demo-lineage",
            source_revision["revision_id"],
            "substrate-b",
            activation_id="activation-target",
            started_at=_TIMES["target_activation"],
        )
        reconstruction = expected_reconstruction(store, snapshot)
        reconstruction["new_inferences"] = [
            "Provider-backed comparison remains outside this P0 demonstration"
        ]
        result = resolve_handoff(
            store,
            handoff_id=snapshot["handoff_id"],
            target_activation_id=target["activation_id"],
            reconstruction=reconstruction,
            handoff_result_id="handoff-result-demo-review",
            target_lease_id="lease-target",
            resulting_revision_id="revision-demo-0004",
            resolved_at=_TIMES["result"],
        )
        authority_after = store.current_authority("demo-lineage")
        exported = _export_records(
            store,
            [
                ("lineage-revision", initial["revision_id"], initial),
                ("lineage-revision", source_revision["revision_id"], source_revision),
                ("fit-decision", fit["fit_decision_id"], fit),
                ("execution-projection", projection["projection_id"], projection),
                ("handoff-snapshot", snapshot["handoff_id"], snapshot),
                ("handoff-result", result["handoff_result_id"], result),
                (
                    "lineage-revision",
                    result["resulting_authority"]["lineage_head_revision_id"],
                    store.get_revision(
                        result["resulting_authority"]["lineage_head_revision_id"]
                    ),
                ),
            ],
        )
        verification = verify_store(store, "demo-lineage")
        return {
            "lineage_id": "demo-lineage",
            "source_revision_id": source_revision["revision_id"],
            "resulting_revision_id": result["resulting_authority"][
                "lineage_head_revision_id"
            ],
            "source_activation_id": source["activation_id"],
            "target_activation_id": target["activation_id"],
            "source_substrate_id": "substrate-a",
            "target_substrate_id": fit["selected_substrate_id"],
            "fit_decision_id": fit["fit_decision_id"],
            "fit_reason": "deterministic eligibility and weighted evidence selected "
            "the independent review substrate",
            "projection": {
                "projection_id": projection["projection_id"],
                "budget": projection["budget"],
                "included_sections": [
                    item["section_id"] for item in projection["included_sections"]
                ],
                "omitted_sections": [
                    item["section_id"] for item in projection["omitted_sections"]
                ],
            },
            "handoff_id": snapshot["handoff_id"],
            "handoff_result_id": result["handoff_result_id"],
            "lease_holder_before": authority_before["activation_id"],
            "lease_holder_after_prepare": authority_after_prepare["activation_id"],
            "lease_holder_after": authority_after["activation_id"],
            "artifact_paths": [item["relative_path"] for item in exported],
            "verification": verification,
        }


def inspect_lineage(store: Store, lineage_id: str) -> dict[str, Any]:
    return {
        "lineage": store.get_lineage(lineage_id),
        "lineage_head": store.get_revision(store.get_lineage(lineage_id)["head_revision_id"]),
        "revision_history": store.lineage_revisions(lineage_id),
        "current_authority": store.current_authority(lineage_id),
        "activations": store.list_activations(lineage_id),
        "fit_decisions": store.list_hashed_records("fit_decisions", lineage_id),
        "projections": store.list_hashed_records("projections", lineage_id),
        "handoffs": store.list_hashed_records("handoffs", lineage_id),
        "handoff_results": store.list_hashed_records("handoff_results", lineage_id),
        "artifacts": [
            dict(row)
            for row in store.connection.execute(
                "SELECT * FROM artifacts ORDER BY artifact_id"
            )
        ],
        "integrity": verify_store(store, lineage_id),
    }


def _export_records(
    store: Store, records: list[tuple[str, str, dict[str, Any]]]
) -> list[dict[str, Any]]:
    artifact_dir = store.state_dir / "artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    exported = []
    for index, (kind, record_id, record) in enumerate(records, start=1):
        filename = f"{kind}-{record_id}.json"
        relative_path = str(Path("artifacts") / filename).replace("\\", "/")
        path = store.state_dir / relative_path
        path.write_text(
            json.dumps(record, indent=2, sort_keys=True) + "\n", encoding="utf-8"
        )
        exported.append(
            artifact_metadata(
                store,
                artifact_id=f"artifact-demo-{index:04d}",
                record_kind=kind,
                record_id=record_id,
                relative_path=relative_path,
                created_at=_TIMES["result"],
            )
        )
    return exported


def _substrates() -> tuple[dict[str, Any], dict[str, Any]]:
    return (
        {
            "schema_version": 1,
            "substrate_id": "substrate-a",
            "label": "Synthetic implementation bearer",
            "adapter": "synthetic",
            "capabilities": [
                "repository_read",
                "repository_write",
                "verification_execute",
            ],
            "policy_labels": ["local-synthetic"],
            "context_budget": {"unit": "words", "limit": 800},
            "task_affinities": ["implementation"],
        },
        {
            "schema_version": 1,
            "substrate_id": "substrate-b",
            "label": "Synthetic independent review bearer",
            "adapter": "synthetic",
            "capabilities": ["repository_read", "independent_review"],
            "policy_labels": ["local-synthetic"],
            "context_budget": {"unit": "words", "limit": 300},
            "task_affinities": ["review"],
        },
    )


def _initial_state() -> dict[str, Any]:
    return {
        "identity": {"label": "TORC demo lineage"},
        "self_model": {
            "role": "Implement the P0 continuity slice",
            "settled_decisions": [
                "Canonical lineage and execution projections remain separate",
                "Authority transfers only after continuity acceptance",
            ],
            "methods": ["Use deterministic local evidence"],
        },
        "goals": [
            "Prove an acceptance-gated lineage handoff",
            "Produce inspectable provenance for every authority change",
        ],
        "commitments": [
            "Do not broaden execution authority during handoff",
            "Preserve canonical state when deriving target projections",
        ],
        "constraints": [
            "No network calls",
            "No daemon or background process",
            "SHA-256 is tamper evidence only",
        ],
        "open_work": ["Implement the local vertical slice"],
        "uncertainties": [
            "Whether TORC outperforms a carefully compiled prompt",
            "How provider tokenization changes projection efficiency",
        ],
        "artifact_refs": ["artifact-project-brief", "artifact-vertical-slice"],
        "memory_refs": [],
    }
