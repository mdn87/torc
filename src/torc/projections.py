"""Deterministic target-fit execution projections.

`compile_projection` is the frozen P0 compiler. The demo and the P1 experiment
lanes depend on its exact output, so it must not change.
`compile_receiver_projection` is the P5 compiler: it sizes and shapes the carry
for the receiving substrate and reads the lineage history behind the head.
"""

from __future__ import annotations

import re
from typing import Any

from .canonical import canonical_json, seal_record, utc_now
from .errors import InvalidInputError, LeaseConflictError, ProjectionBudgetError
from .history import (
    changes_since_substrate,
    restatement_due,
    revision_chain,
    self_model_provenance,
    unaccounted_drops,
)
from .ids import new_id
from .store import Store

COMPILER_VERSION = "p0-1"
POLICY_VERSION = "p0-1"

RECEIVER_COMPILER_VERSION = "p5-1"
RECEIVER_POLICY_VERSION = "p5-1"
CARRY_PURPOSES = ("handoff", "session_start")
CARRY_SHARE_PERCENT = 5
CARRY_FLOOR = {"words": 200, "characters": 1200}
# A receiver that lacks the capability cannot use what the section points to.
SECTION_CAPABILITIES = {"artifact-refs": "repository_read"}


def estimate_words(content: Any) -> int:
    return len(re.findall(r"\b[\w'-]+\b", canonical_json(content), flags=re.UNICODE))


def estimate_units(content: Any, unit: str) -> int:
    if unit == "characters":
        return len(canonical_json(content))
    return estimate_words(content)


def receiver_budget(substrate: dict[str, Any], budget_cap: int | None = None) -> dict[str, Any]:
    """Derive the carry budget from the receiver's descriptor.

    An operator cap can only lower the budget.
    """

    context = substrate["context_budget"]
    unit = context.get("unit", "words")
    if unit not in CARRY_FLOOR:
        raise InvalidInputError(f"unsupported context budget unit: {unit}")
    context_limit = int(context["limit"])
    declared = context.get("carry_limit")
    if declared is not None:
        if isinstance(declared, bool) or not isinstance(declared, int) or declared <= 0:
            raise InvalidInputError("context_budget.carry_limit must be a positive integer")
        if declared > context_limit:
            raise InvalidInputError("context_budget.carry_limit exceeds the context limit")
        limit, source = declared, "descriptor_carry_limit"
    else:
        share = context_limit * CARRY_SHARE_PERCENT // 100
        limit, source = min(context_limit, max(CARRY_FLOOR[unit], share)), "descriptor_share"
    if budget_cap is not None:
        if isinstance(budget_cap, bool) or not isinstance(budget_cap, int) or budget_cap <= 0:
            raise InvalidInputError("budget cap must be a positive integer")
        if budget_cap < limit:
            limit, source = budget_cap, "operator_cap"
    return {"unit": unit, "limit": limit, "source": source, "context_limit": context_limit}


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


def compile_receiver_projection(
    store: Store,
    *,
    lineage_id: str,
    source_revision_id: str,
    receiver_substrate_id: str,
    purpose: str,
    handoff_reason: str | None = None,
    target_responsibility: str | None = None,
    budget_cap: int | None = None,
    projection_id: str | None = None,
    compiled_at: str | None = None,
) -> dict[str, Any]:
    """Compile the carry for one receiver from the head revision and its history."""

    if purpose not in CARRY_PURPOSES:
        raise ValueError(f"unsupported carry purpose: {purpose}")
    revision = store.get_revision(source_revision_id)
    if revision["lineage_id"] != lineage_id:
        raise ValueError("projection source revision belongs to another lineage")
    receiver = store.get_substrate(receiver_substrate_id)
    budget = receiver_budget(receiver, budget_cap)
    unit = budget["unit"]
    chain = revision_chain(store, source_revision_id)
    drops = unaccounted_drops(chain)
    provenance = self_model_provenance(chain)
    state = revision["canonical_state"]
    self_model = state["self_model"]

    if purpose == "handoff":
        if not handoff_reason or not target_responsibility:
            raise ValueError("a handoff carry requires a reason and a target responsibility")
        purpose_spec = (
            "handoff-purpose",
            f"{source_revision_id}:self_model",
            {"reason_code": handoff_reason, "target_responsibility": target_responsibility},
        )
    else:
        try:
            authority = store.current_authority(lineage_id)
        except LeaseConflictError:
            authority = None
        purpose_spec = (
            "session-purpose",
            f"{source_revision_id}:self_model",
            {
                "purpose": purpose,
                "authority": authority
                and {
                    "activation_id": authority["activation_id"],
                    "substrate_id": authority["substrate_id"],
                },
                "receiver_is_authority_substrate": bool(
                    authority and authority["substrate_id"] == receiver_substrate_id
                ),
            },
        )
    required_specs = [
        (
            "identity-role",
            f"{source_revision_id}:identity",
            {"identity": state["identity"], "role": self_model.get("role", "")},
        ),
        ("constraints", f"{source_revision_id}:constraints", state["constraints"]),
        ("commitments", f"{source_revision_id}:commitments", state["commitments"]),
        ("open-work", f"{source_revision_id}:open_work", state["open_work"]),
        purpose_spec,
        (
            "receiver-fit",
            f"{source_revision_id}:receiver_fit",
            {
                "receiver_substrate_id": receiver_substrate_id,
                "budget_source": budget["source"],
                "context_limit": budget["context_limit"],
                "history_revisions_read": len(chain),
            },
        ),
        (
            "self-model-provenance",
            f"{provenance['authored_at_revision_id']}:self_model",
            provenance
            | {
                "receiver_substrate_id": receiver_substrate_id,
                "restatement_due": restatement_due(provenance, receiver_substrate_id),
            },
        ),
    ]
    included = [
        _fitted_section(section_id, source_ref, True, 100, content, unit)
        for section_id, source_ref, content in required_specs
    ]
    used = sum(item["estimated_units"] for item in included)
    if used > budget["limit"]:
        raise ProjectionBudgetError(
            f"required continuity needs {used} {unit} but the receiver budget is "
            f"{budget['limit']}"
        )

    omitted: list[dict[str, str]] = []

    def fit_whole(section: dict[str, Any]) -> bool:
        nonlocal used
        if used + section["estimated_units"] > budget["limit"]:
            return False
        included.append(section)
        used += section["estimated_units"]
        return True

    def omit(section_id: str, source_ref: str, reason: str) -> None:
        omitted.append({"section_id": section_id, "source_ref": source_ref, "reason": reason})

    # History tier. The most recently dropped items are fitted first, and within one
    # revision constraints come before commitments and open work. Identifiers follow
    # drop order so they stay stable as the budget changes.
    position = {item["revision_id"]: index for index, item in enumerate(chain)}
    for index, drop in sorted(
        enumerate(drops, start=1),
        key=lambda pair: (-position[pair[1]["dropped_at_revision_id"]], pair[0]),
    ):
        section_id = f"unaccounted-{drop['section']}-{index}"
        source_ref = f"{drop['last_seen_revision_id']}:{drop['section']}"
        if not fit_whole(_fitted_section(section_id, source_ref, False, 90, drop, unit)):
            omit(section_id, source_ref, "budget")
    changes = changes_since_substrate(chain, receiver_substrate_id)
    if changes is not None:
        source_ref = f"{changes['since_revision_id']}:canonical_state"
        section = _fitted_section(
            "changes-since-receiver", source_ref, False, 85, changes, unit
        )
        if not fit_whole(section):
            omit("changes-since-receiver", source_ref, "budget")

    optional_specs = [
        ("goals", f"{source_revision_id}:goals", 80, state["goals"]),
        (
            "settled-decisions",
            f"{source_revision_id}:self_model",
            70,
            self_model.get("settled_decisions", []),
        ),
        ("uncertainties", f"{source_revision_id}:uncertainties", 60, state["uncertainties"]),
        ("methods", f"{source_revision_id}:self_model", 50, self_model.get("methods", [])),
        ("artifact-refs", f"{source_revision_id}:artifact_refs", 40, state["artifact_refs"]),
        ("memory-refs", f"{source_revision_id}:memory_refs", 30, state["memory_refs"]),
    ]
    capabilities = set(receiver.get("capabilities", []))
    for section_id, source_ref, priority, content in optional_specs:
        needed = SECTION_CAPABILITIES.get(section_id)
        if needed is not None and needed not in capabilities:
            omit(section_id, source_ref, "capability_irrelevant")
            continue
        if fit_whole(_fitted_section(section_id, source_ref, False, priority, content, unit)):
            continue
        # Keep the leading items that fit and record the rest as omitted.
        kept: list[Any] = []
        if isinstance(content, list):
            for item in content:
                candidate = kept + [item]
                if used + estimate_units(candidate, unit) > budget["limit"]:
                    break
                kept = candidate
        if kept:
            fit_whole(_fitted_section(section_id, source_ref, False, priority, kept, unit))
            omit(f"{section_id}.remainder", source_ref, "budget")
        else:
            omit(section_id, source_ref, "budget")

    record = seal_record(
        {
            "schema_version": 1,
            "projection_id": projection_id or new_id("projection"),
            "lineage_id": lineage_id,
            "source_revision_id": source_revision_id,
            "target_substrate_id": receiver_substrate_id,
            "compiler_version": RECEIVER_COMPILER_VERSION,
            "policy_version": RECEIVER_POLICY_VERSION,
            "compiled_at": compiled_at or utc_now(),
            "budget": {
                "unit": unit,
                "limit": budget["limit"],
                "estimated_used": used,
            },
            "included_sections": included,
            "omitted_sections": omitted,
            "redactions": [],
        }
    )
    store.insert_hashed_record("projections", record["projection_id"], record)
    return record


def _fitted_section(
    section_id: str,
    source_ref: str,
    required: bool,
    priority: int,
    content: Any,
    unit: str,
) -> dict[str, Any]:
    return {
        "section_id": section_id,
        "source_ref": source_ref,
        "required": required,
        "priority": priority,
        "estimated_units": estimate_units(content, unit),
        "content": content,
    }
