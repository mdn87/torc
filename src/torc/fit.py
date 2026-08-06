"""Deterministic, explainable synthetic substrate fit evaluation."""

from __future__ import annotations

from typing import Any

from .canonical import seal_record, utc_now
from .ids import new_id
from .store import Store

POLICY_VERSION = "p0-1"


def evaluate_fit(
    store: Store,
    *,
    lineage_id: str,
    source_revision_id: str,
    source_substrate_id: str,
    task_phase: str,
    requirements: dict[str, Any],
    fit_decision_id: str | None = None,
    decided_at: str | None = None,
) -> dict[str, Any]:
    required_capabilities = set(requirements["capabilities"])
    required_labels = set(requirements["policy_labels"])
    minimum_context = int(requirements["minimum_context_units"])
    candidates: list[dict[str, Any]] = []

    for substrate in store.list_substrates():
        capabilities = set(substrate["capabilities"])
        labels = set(substrate["policy_labels"])
        context_limit = int(substrate["context_budget"]["limit"])
        disqualifications = []
        if missing := sorted(required_capabilities - capabilities):
            disqualifications.append(f"missing capabilities: {', '.join(missing)}")
        if missing := sorted(required_labels - labels):
            disqualifications.append(f"missing policy labels: {', '.join(missing)}")
        if context_limit < minimum_context:
            disqualifications.append(
                f"context limit {context_limit} below required {minimum_context}"
            )

        eligible = not disqualifications
        affinity = task_phase.replace("independent-", "").split("-")[-1]
        factors = [
            _factor(
                "capability_coverage",
                len(required_capabilities & capabilities) / max(len(required_capabilities), 1),
                3,
                f"{len(required_capabilities & capabilities)}/"
                f"{len(required_capabilities)} required capabilities",
            ),
            _factor(
                "context_headroom",
                min(context_limit / max(minimum_context, 1), 2) / 2,
                2,
                f"{context_limit} available for {minimum_context} required units",
            ),
            _factor(
                "task_affinity",
                float(affinity in substrate.get("task_affinities", [])),
                4,
                f"declared affinities: {', '.join(substrate.get('task_affinities', []))}",
            ),
            _factor(
                "independence",
                float(substrate["substrate_id"] != source_substrate_id),
                5,
                (
                    "candidate differs from the source implementation substrate"
                    if substrate["substrate_id"] != source_substrate_id
                    else "candidate is the source implementation substrate"
                ),
            ),
        ]
        total = round(sum(factor["score"] for factor in factors), 6) if eligible else 0
        candidates.append(
            {
                "substrate_id": substrate["substrate_id"],
                "eligible": eligible,
                "disqualifications": disqualifications,
                "factors": factors,
                "total_score": total,
            }
        )

    eligible_candidates = [item for item in candidates if item["eligible"]]
    selected = (
        sorted(
            eligible_candidates,
            key=lambda item: (-item["total_score"], item["substrate_id"]),
        )[0]["substrate_id"]
        if eligible_candidates
        else None
    )
    record = seal_record(
        {
            "schema_version": 1,
            "fit_decision_id": fit_decision_id or new_id("fit"),
            "lineage_id": lineage_id,
            "source_revision_id": source_revision_id,
            "task_phase": task_phase,
            "requirements": requirements,
            "candidates": candidates,
            "selected_substrate_id": selected,
            "policy_version": POLICY_VERSION,
            "decided_at": decided_at or utc_now(),
        }
    )
    store.insert_hashed_record(
        "fit_decisions", record["fit_decision_id"], record
    )
    return record


def _factor(name: str, value: float, weight: float, evidence: str) -> dict[str, Any]:
    return {
        "name": name,
        "value": round(value, 6),
        "weight": weight,
        "score": round(value * weight, 6),
        "evidence": evidence,
    }
