"""Shared builders for the P5 review repros. Only the public operator API is used."""

from __future__ import annotations

import json
from typing import Any

from torc.operator import prepare_operator_handoff, resolve_operator_handoff
from torc.store import Store


def substrate(
    sid: str,
    *,
    limit: int = 32000,
    unit: str = "words",
    carry_limit: int | None = None,
    capabilities: list[str] | None = None,
    affinities: list[str] | None = None,
) -> dict[str, Any]:
    context: dict[str, Any] = {"unit": unit, "limit": limit}
    if carry_limit is not None:
        context["carry_limit"] = carry_limit
    return {
        "schema_version": 1,
        "substrate_id": sid,
        "label": sid,
        "adapter": "manual",
        "capabilities": capabilities or ["repository_read", "repository_write"],
        "policy_labels": ["local-workspace"],
        "context_budget": context,
        "task_affinities": affinities or ["implementation"],
    }


def state(
    *,
    open_work: list[str] | None = None,
    constraints: list[str] | None = None,
    commitments: list[str] | None = None,
    goals: list[str] | None = None,
    uncertainties: list[str] | None = None,
    self_model: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "identity": {"label": "review fixture"},
        "self_model": self_model
        or {"role": "Implement the thing", "methods": ["m1"], "settled_decisions": ["d1"]},
        "goals": list(goals or []),
        "commitments": list(commitments or []),
        "constraints": list(constraints or []),
        "open_work": list(open_work or []),
        "uncertainties": list(uncertainties or []),
        "artifact_refs": [],
        "memory_refs": [],
    }


def head_state(store: Store, lineage: str) -> dict[str, Any]:
    head = store.get_lineage(lineage)["head_revision_id"]
    return json.loads(json.dumps(store.get_revision(head)["canonical_state"]))


def plan(target: dict[str, Any], target_activation: str, responsibility: str = "Carry on") -> dict[str, Any]:
    return {
        "target_substrate": target,
        "target_activation_id": target_activation,
        "task_phase": "implementation",
        "requirements": {
            "capabilities": ["repository_read"],
            "policy_labels": ["local-workspace"],
            "minimum_context_units": 100,
        },
        "target_responsibility": responsibility,
        "reason_code": "model_succession",
        "rationale": "review repro",
    }


def handoff(
    store: Store,
    lineage: str,
    source_activation: str,
    target: dict[str, Any],
    target_activation: str,
    responsibility: str = "Carry on",
) -> dict[str, Any]:
    prepared = prepare_operator_handoff(
        store,
        lineage_id=lineage,
        source_activation_id=source_activation,
        plan=plan(target, target_activation, responsibility),
    )
    template = json.loads(
        (store.state_dir / prepared["reconstruction_template_path"]).read_text(encoding="utf-8")
    )
    result = resolve_operator_handoff(
        store,
        handoff_id=prepared["handoff_id"],
        target_activation_id=target_activation,
        reconstruction=template,
    )
    assert result["disposition"] == "accepted", result
    return result


def sections(projection: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {item["section_id"]: item for item in projection["included_sections"]}


def show(label: str, value: Any) -> None:
    print(f"{label}: {json.dumps(value, indent=2, sort_keys=True)}")
