"""Deterministic target-fit execution projections."""

from __future__ import annotations

import re
from typing import Any

from .canonical import canonical_json, seal_record, utc_now
from .errors import ProjectionBudgetError
from .ids import new_id
from .store import Store

COMPILER_VERSION = "p0-1"
POLICY_VERSION = "p0-1"


def estimate_words(content: Any) -> int:
    return len(re.findall(r"\b[\w'-]+\b", canonical_json(content), flags=re.UNICODE))


def compile_projection(
    store: Store,
    *,
    lineage_id: str,
    source_revision_id: str,
    target_substrate_id: str,
    budget_limit: int,
    handoff_reason: str,
    target_responsibility: str,
    projection_id: str | None = None,
    compiled_at: str | None = None,
) -> dict[str, Any]:
    revision = store.get_revision(source_revision_id)
    if revision["lineage_id"] != lineage_id:
        raise ValueError("projection source revision belongs to another lineage")
    store.get_substrate(target_substrate_id)
    state = revision["canonical_state"]
    self_model = state["self_model"]
    required_specs = [
        (
            "identity-role",
            f"{source_revision_id}:identity",
            {
                "identity": state["identity"],
                "role": self_model.get("role", ""),
            },
        ),
        (
            "constraints",
            f"{source_revision_id}:constraints",
            state["constraints"],
        ),
        (
            "commitments",
            f"{source_revision_id}:commitments",
            state["commitments"],
        ),
        ("open-work", f"{source_revision_id}:open_work", state["open_work"]),
        (
            "handoff-purpose",
            f"{source_revision_id}:self_model",
            {
                "reason_code": handoff_reason,
                "target_responsibility": target_responsibility,
            },
        ),
    ]
    optional_specs = [
        ("goals", f"{source_revision_id}:goals", 80, state["goals"]),
        (
            "settled-decisions",
            f"{source_revision_id}:self_model",
            70,
            self_model.get("settled_decisions", []),
        ),
        (
            "uncertainties",
            f"{source_revision_id}:uncertainties",
            60,
            state["uncertainties"],
        ),
        (
            "methods",
            f"{source_revision_id}:self_model",
            50,
            self_model.get("methods", []),
        ),
        (
            "artifact-refs",
            f"{source_revision_id}:artifact_refs",
            40,
            state["artifact_refs"],
        ),
        (
            "memory-refs",
            f"{source_revision_id}:memory_refs",
            30,
            state["memory_refs"],
        ),
    ]

    included = [
        _section(section_id, source_ref, True, 100, content)
        for section_id, source_ref, content in required_specs
    ]
    used = sum(item["estimated_units"] for item in included)
    if used > budget_limit:
        raise ProjectionBudgetError(
            f"required continuity needs {used} words but budget is {budget_limit}"
        )

    omitted: list[dict[str, str]] = []
    for section_id, source_ref, priority, content in sorted(
        optional_specs, key=lambda item: (-item[2], item[0])
    ):
        section = _section(section_id, source_ref, False, priority, content)
        if used + section["estimated_units"] <= budget_limit:
            included.append(section)
            used += section["estimated_units"]
        else:
            omitted.append(
                {
                    "section_id": section_id,
                    "source_ref": source_ref,
                    "reason": "budget",
                }
            )

    record = seal_record(
        {
            "schema_version": 1,
            "projection_id": projection_id or new_id("projection"),
            "lineage_id": lineage_id,
            "source_revision_id": source_revision_id,
            "target_substrate_id": target_substrate_id,
            "compiler_version": COMPILER_VERSION,
            "policy_version": POLICY_VERSION,
            "compiled_at": compiled_at or utc_now(),
            "budget": {
                "unit": "words",
                "limit": budget_limit,
                "estimated_used": used,
            },
            "included_sections": included,
            "omitted_sections": omitted,
            "redactions": [],
        }
    )
    store.insert_hashed_record("projections", record["projection_id"], record)
    return record


def _section(
    section_id: str,
    source_ref: str,
    required: bool,
    priority: int,
    content: Any,
) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "source_ref": source_ref,
        "required": required,
        "priority": priority,
        "estimated_units": estimate_words(content),
        "content": content,
    }
