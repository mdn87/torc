"""Lane-specific continuity materialization for P1a."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .canonical import canonical_json
from .fit import evaluate_fit
from .handoffs import prepare_handoff, resolve_handoff
from .projections import compile_projection, estimate_words
from .store import Store


def _payload(
    context: dict[str, Any],
    *,
    mechanism: str,
    status: str,
    content: Any,
) -> dict[str, Any]:
    encoded = canonical_json(content).encode("utf-8")
    return {
        "schema_version": 1,
        "run_id": context["manifest"]["run_id"],
        "lane": context["manifest"]["selected_lane"],
        "fixture_sha256": context["manifest"]["fixture"]["agent_visible"][0]["sha256"],
        "status": status,
        "mechanism": mechanism,
        "content": content,
        "context": {
            "utf8_bytes": len(encoded),
            "estimated_words": estimate_words(content),
        },
    }


def materialize_compiled_prompt(
    run_context: dict[str, Any], source_capture: dict[str, Any]
) -> dict[str, Any]:
    continuity = source_capture["continuity"]
    content = {
        "instruction": (
            "Continue the independent review using only this frozen continuity "
            "and the referenced visible fixture."
        ),
        "continuity": continuity,
        "fixture_references": ["task.json"],
    }
    return _payload(
        run_context, mechanism="compiled-prompt", status="ready", content=content
    )


def materialize_native_persistence(
    run_context: dict[str, Any], probe_evidence: dict[str, Any]
) -> dict[str, Any]:
    content = {
        "reason": "no equivalent Codex-to-Claude Code native continuation",
        "probe_evidence": probe_evidence,
    }
    return _payload(
        run_context, mechanism="native-persistence", status="unavailable", content=content
    )


def materialize_torc_projection(
    run_context: dict[str, Any], source_capture: dict[str, Any]
) -> dict[str, Any]:
    root = Path(run_context["run_dir"])
    continuity = source_capture["continuity"]
    state = {
        "identity": {"label": continuity["lineage_identity"]},
        "self_model": {
            "role": "Complete implementation and transfer to independent review",
            "settled_decisions": continuity["settled_decisions"],
            "methods": ["Preserve authority until reconstruction is accepted"],
        },
        "goals": ["Complete a bounded independent implementation review"],
        "commitments": continuity["active_commitments"],
        "constraints": continuity["hard_constraints"],
        "open_work": continuity["unresolved_work"],
        "uncertainties": continuity["uncertainties"],
        "artifact_refs": continuity["evidence_refs"],
        "memory_refs": [],
    }
    with Store(root / "torc-state") as store:
        store.register_substrate(
            {
                "schema_version": 1,
                "substrate_id": "p1a-source",
                "label": "Codex source",
                "adapter": "codex",
                "capabilities": ["repository_read"],
                "policy_labels": ["p1a-local"],
                "context_budget": {"unit": "words", "limit": 1000},
                "task_affinities": ["implementation"],
            }
        )
        store.register_substrate(
            {
                "schema_version": 1,
                "substrate_id": "p1a-target",
                "label": "Claude Code target",
                "adapter": "claude-code",
                "capabilities": ["repository_read", "independent_review"],
                "policy_labels": ["p1a-local"],
                "context_budget": {"unit": "words", "limit": 1000},
                "task_affinities": ["review"],
            }
        )
        initial = store.create_lineage(
            "p1a-lineage",
            state,
            revision_id="p1a-revision-0001",
            created_at="2026-08-06T12:00:00Z",
        )
        source = store.create_activation(
            "p1a-lineage",
            initial["revision_id"],
            "p1a-source",
            activation_id="p1a-source-activation",
            started_at="2026-08-06T12:01:00Z",
        )
        store.acquire_lease(
            "p1a-lineage",
            source["activation_id"],
            lease_id="p1a-source-lease",
            issued_at="2026-08-06T12:02:00Z",
        )
        checkpoint = store.append_revision(
            "p1a-lineage",
            state,
            event_type="checkpoint",
            activation_id=source["activation_id"],
            revision_id="p1a-revision-0002",
            created_at="2026-08-06T12:03:00Z",
            evidence_refs=continuity["evidence_refs"],
        )
        fit = evaluate_fit(
            store,
            lineage_id="p1a-lineage",
            source_revision_id=checkpoint["revision_id"],
            source_substrate_id="p1a-source",
            task_phase="independent-review",
            requirements={
                "capabilities": ["repository_read", "independent_review"],
                "policy_labels": ["p1a-local"],
                "minimum_context_units": 100,
            },
            fit_decision_id="p1a-fit",
            decided_at="2026-08-06T12:04:00Z",
        )
        projection = compile_projection(
            store,
            lineage_id="p1a-lineage",
            source_revision_id=checkpoint["revision_id"],
            target_substrate_id=fit["selected_substrate_id"],
            budget_limit=500,
            handoff_reason="task_phase_transition",
            target_responsibility=continuity["current_responsibility"],
            projection_id="p1a-projection",
            compiled_at="2026-08-06T12:05:00Z",
        )
        snapshot = prepare_handoff(
            store,
            lineage_id="p1a-lineage",
            source_activation_id=source["activation_id"],
            fit_decision_id=fit["fit_decision_id"],
            projection_id=projection["projection_id"],
            reason_code="task_phase_transition",
            rationale="Implementation is ready for bounded independent review.",
            handoff_id="p1a-handoff",
            prepared_at="2026-08-06T12:06:00Z",
        )
        authority = store.current_authority("p1a-lineage")
    content = {
        "projection": projection,
        "handoff_snapshot": snapshot,
        "source_authority": authority,
        "fixture_references": ["task.json"],
    }
    return _payload(run_context, mechanism="torc-projection", status="ready", content=content)


def record_torc_reconstruction(
    run_context: dict[str, Any],
    attempt: dict[str, Any],
    reconstruction: dict[str, Any],
) -> dict[str, Any]:
    root = Path(run_context["run_dir"])
    with Store(root / "torc-state") as store:
        target = store.create_activation(
            "p1a-lineage",
            "p1a-revision-0002",
            "p1a-target",
            activation_id=f"p1a-target-{attempt['attempt_id']}",
            started_at=attempt["started_at"],
        )
        return resolve_handoff(
            store,
            handoff_id="p1a-handoff",
            target_activation_id=target["activation_id"],
            reconstruction=reconstruction,
            handoff_result_id=f"p1a-result-{attempt['attempt_id']}",
            target_lease_id="p1a-target-lease",
            resulting_revision_id="p1a-revision-0003",
            resolved_at=attempt["ended_at"],
        )
