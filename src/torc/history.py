"""Deterministic reading of one lineage's canonical history.

A head revision holds only what its bearer chose to keep. These functions read
the revisions behind it so that an omission by one bearer does not become
permanent. They compare exact strings and perform no inference.
"""

from __future__ import annotations

from itertools import pairwise
from typing import Any

from .errors import IntegrityError, InvalidInputError
from .store import Store
from .vocabulary import RESOLUTION_DISPOSITIONS, TRACKED_CONTINUITY_SECTIONS


def revision_chain(store: Store, source_revision_id: str) -> list[dict[str, Any]]:
    """Return the source revision and its ancestors in the same lineage, oldest first."""

    revision = store.get_revision(source_revision_id)
    lineage_id = revision["lineage_id"]
    chain = [revision]
    seen = {revision["revision_id"]}
    while revision["parent_revision_ids"]:
        parent = store.get_revision(revision["parent_revision_ids"][0])
        if parent["lineage_id"] != lineage_id:
            break
        if parent["revision_id"] in seen:
            raise IntegrityError(f"revision ancestry loops at {parent['revision_id']}")
        seen.add(parent["revision_id"])
        chain.append(parent)
        revision = parent
    chain.reverse()
    return chain


def unaccounted_drops(chain: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return tracked items removed without a resolution, oldest drop first.

    A removal is accounted for by a resolution on the removing or a later
    revision, by an explicit rollback, or by the item returning to the state.
    """

    open_drops: dict[tuple[str, str], dict[str, Any]] = {}
    for previous, current in pairwise(chain):
        resolved = {
            (item["section"], item["item"]) for item in current.get("resolutions") or []
        }
        for key in resolved:
            open_drops.pop(key, None)
        rolled_back = current["event_type"] == "rollback_applied"
        for section in TRACKED_CONTINUITY_SECTIONS:
            present = set(current["canonical_state"][section])
            for item in previous["canonical_state"][section]:
                key = (section, item)
                if item in present or key in resolved or rolled_back:
                    continue
                open_drops.pop(key, None)
                open_drops[key] = {
                    "section": section,
                    "item": item,
                    "last_seen_revision_id": previous["revision_id"],
                    "dropped_at_revision_id": current["revision_id"],
                    "dropped_by_substrate_id": current["actor"]["substrate_id"],
                }
            for item in present:
                open_drops.pop((section, item), None)
    return list(open_drops.values())


def self_model_provenance(chain: list[dict[str, Any]]) -> dict[str, Any]:
    """Identify the revision whose actor last authored the self-model.

    An accepted handoff copies the recipient's responsibility into the role. That
    is TORC's bookkeeping, not a restatement, so it does not change authorship.
    A rollback restores the authorship of the revision it restored.
    """

    authors = {chain[0]["revision_id"]: chain[0]}
    author = chain[0]
    for previous, current in pairwise(chain):
        if current["event_type"] == "rollback_applied":
            target = (current.get("rollback_context") or {}).get("target_revision_id")
            author = authors.get(target, author)
        elif current["event_type"] != "handoff_accepted" and (
            current["canonical_state"]["self_model"]
            != previous["canonical_state"]["self_model"]
        ):
            author = current
        authors[current["revision_id"]] = author
    return {
        "authored_at_revision_id": author["revision_id"],
        "authored_by_activation_id": author["actor"]["activation_id"],
        "authored_by_substrate_id": author["actor"]["substrate_id"],
    }


def restatement_due(provenance: dict[str, Any], bearer_substrate_id: str | None) -> bool:
    """A self-model written under another substrate should be restated by the bearer.

    An operator-authored self-model is the operator's definition and is not due.
    """

    author = provenance["authored_by_substrate_id"]
    return author is not None and author != bearer_substrate_id


def changes_since_substrate(
    chain: list[dict[str, Any]], substrate_id: str
) -> dict[str, Any] | None:
    """Summarize tracked changes since the substrate last authored a revision."""

    index = max(
        (
            position
            for position, revision in enumerate(chain)
            if revision["actor"]["substrate_id"] == substrate_id
        ),
        default=None,
    )
    if index is None or index == len(chain) - 1:
        return None
    base, head = chain[index], chain[-1]
    dispositions = {
        (item["section"], item["item"]): item["disposition"]
        for revision in chain[index + 1 :]
        for item in revision.get("resolutions") or []
    }
    unaccounted = {(item["section"], item["item"]) for item in unaccounted_drops(chain)}
    added: dict[str, list[str]] = {}
    removed: dict[str, list[dict[str, str]]] = {}
    for section in TRACKED_CONTINUITY_SECTIONS:
        before = base["canonical_state"][section]
        after = head["canonical_state"][section]
        if new := [item for item in after if item not in before]:
            added[section] = new
        gone = []
        for item in before:
            if item in after:
                continue
            key = (section, item)
            disposition = dispositions.get(
                key, "unaccounted" if key in unaccounted else "rolled_back"
            )
            gone.append({"item": item, "disposition": disposition})
        if gone:
            removed[section] = gone
    self_model_changed = (
        base["canonical_state"]["self_model"] != head["canonical_state"]["self_model"]
    )
    if not added and not removed and not self_model_changed:
        return None
    return {
        "since_revision_id": base["revision_id"],
        "revisions_since": len(chain) - 1 - index,
        "added": added,
        "removed": removed,
        "self_model_changed": self_model_changed,
    }


def boundary_report(
    chain: list[dict[str, Any]], bearer_substrate_id: str | None
) -> dict[str, Any]:
    """State what the current bearer still owes the lineage at a control boundary."""

    provenance = self_model_provenance(chain)
    return {
        "unaccounted": unaccounted_drops(chain),
        "self_model": provenance
        | {
            "bearer_substrate_id": bearer_substrate_id,
            "restatement_due": restatement_due(provenance, bearer_substrate_id),
        },
    }


def validate_resolutions(
    chain: list[dict[str, Any]],
    new_state: dict[str, Any],
    resolutions: Any,
) -> list[dict[str, str]]:
    """Reject resolutions that do not name a real removal, before any write."""

    validate_resolution_shape(resolutions)
    head_state = chain[-1]["canonical_state"]
    open_keys = {(item["section"], item["item"]) for item in unaccounted_drops(chain)}
    for resolution in resolutions:
        section, item = resolution["section"], resolution["item"]
        if item in new_state[section]:
            raise InvalidInputError(
                f"resolution names an item still present in {section}: {item}"
            )
        if item not in head_state[section] and (section, item) not in open_keys:
            raise InvalidInputError(
                f"resolution names an item that was never dropped from {section}: {item}"
            )
    return [dict(resolution) for resolution in resolutions]


def validate_resolution_shape(resolutions: Any) -> None:
    """Check resolution structure without reading a store."""

    if not isinstance(resolutions, list) or not resolutions:
        raise InvalidInputError("resolutions must be a non-empty JSON array")
    seen: set[tuple[str, str]] = set()
    for resolution in resolutions:
        if not isinstance(resolution, dict):
            raise InvalidInputError("each resolution must be a JSON object")
        if unknown := sorted(set(resolution) - {"section", "item", "disposition", "note"}):
            raise InvalidInputError(
                f"resolution has unsupported fields: {', '.join(unknown)}"
            )
        section = resolution.get("section")
        item = resolution.get("item")
        if section not in TRACKED_CONTINUITY_SECTIONS:
            raise InvalidInputError(
                "resolution section must be one of: "
                + ", ".join(TRACKED_CONTINUITY_SECTIONS)
            )
        if not isinstance(item, str) or not item:
            raise InvalidInputError("resolution item must be a non-empty string")
        if resolution.get("disposition") not in RESOLUTION_DISPOSITIONS:
            raise InvalidInputError(
                "resolution disposition must be one of: "
                + ", ".join(RESOLUTION_DISPOSITIONS)
            )
        if "note" in resolution and not isinstance(resolution["note"], str):
            raise InvalidInputError("resolution note must be a string")
        if (section, item) in seen:
            raise InvalidInputError(f"duplicate resolution for {section}: {item}")
        seen.add((section, item))
