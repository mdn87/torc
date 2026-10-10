"""Deterministic reading of one lineage's canonical history.

A head revision holds only what its bearer chose to keep. These functions read
the revisions behind it so that an omission by one bearer does not become
permanent. They compare exact strings and perform no inference.
"""

from __future__ import annotations

from itertools import pairwise
from typing import TYPE_CHECKING, Any

from .errors import IntegrityError, InvalidInputError
from .vocabulary import (
    BOOKKEEPING_EVENT_TYPES,
    RESOLUTION_DISPOSITIONS,
    TRACKED_CONTINUITY_SECTIONS,
)

if TYPE_CHECKING:
    from .store import Store

DROP_FIELDS = (
    "section",
    "item",
    "last_seen_revision_id",
    "dropped_at_revision_id",
    "dropped_by_substrate_id",
)


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


def removal_epochs(chain: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return every removal of a tracked item, oldest first, with how it was accounted for.

    One epoch runs from the revision that removed the item until a resolution
    names it, a later revision restores it, or the removing revision is itself an
    explicit rollback. A resolution accounts for the latest open removal of its
    item and for nothing earlier or later, so an item that is resolved, restored,
    and removed again opens a new epoch that the old resolution does not cover.
    `disposition` is the resolution's disposition, `rolled_back`, `restored`, or
    None while the removal is still unaccounted.
    """

    epochs: list[dict[str, Any]] = []
    open_by_key: dict[tuple[str, str], dict[str, Any]] = {}
    for index, (previous, current) in enumerate(pairwise(chain), start=1):
        resolved = {
            (item["section"], item["item"]): item["disposition"]
            for item in current.get("resolutions") or []
        }
        rolled_back = current["event_type"] == "rollback_applied"
        removed_now: set[tuple[str, str]] = set()
        for section in TRACKED_CONTINUITY_SECTIONS:
            present = set(current["canonical_state"][section])
            for item in previous["canonical_state"][section]:
                if item in present:
                    continue
                key = (section, item)
                removed_now.add(key)
                disposition = resolved.get(key, "rolled_back" if rolled_back else None)
                epoch = {
                    "section": section,
                    "item": item,
                    "last_seen_revision_id": previous["revision_id"],
                    "dropped_at_revision_id": current["revision_id"],
                    "dropped_by_substrate_id": current["actor"]["substrate_id"],
                    "dropped_at_index": index,
                    "disposition": disposition,
                    "accounted_at_index": None if disposition is None else index,
                }
                if disposition is None:
                    open_by_key[key] = epoch
                epochs.append(epoch)
            for item in present:
                epoch = open_by_key.pop((section, item), None)
                if epoch is not None:
                    epoch["disposition"] = "restored"
                    epoch["accounted_at_index"] = index
        for key, disposition in resolved.items():
            if key in removed_now:
                continue
            epoch = open_by_key.pop(key, None)
            if epoch is not None:
                epoch["disposition"] = disposition
                epoch["accounted_at_index"] = index
    return epochs


def unaccounted_drops(chain: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Return tracked items removed without a resolution, oldest drop first.

    A removal is accounted for by a resolution on the removing or a later
    revision, by an explicit rollback, or by the item returning to the state.
    """

    return [
        {field: epoch[field] for field in DROP_FIELDS}
        for epoch in removal_epochs(chain)
        if epoch["disposition"] is None
    ]


def self_model_provenance(chain: list[dict[str, Any]]) -> dict[str, Any]:
    """Identify who last authored the self-model and who last restated it.

    Authorship follows content: the revision whose actor last changed the
    self-model. Restatement follows the protocol: a `self_model_revised`
    checkpoint restates the self-model even when its text is confirmed verbatim,
    so a bearer's confirmation is visible as a confirmation. An accepted handoff
    copies the recipient's responsibility into the role. That is TORC's
    bookkeeping, not a restatement, so it changes neither. A rollback restores
    the authorship and restatement of the revision it restored.
    """

    authors = {chain[0]["revision_id"]: chain[0]}
    restaters = {chain[0]["revision_id"]: chain[0]}
    author = restater = chain[0]
    for previous, current in pairwise(chain):
        if current["event_type"] == "rollback_applied":
            target = (current.get("rollback_context") or {}).get("target_revision_id")
            author = authors.get(target, author)
            restater = restaters.get(target, restater)
        elif current["event_type"] not in BOOKKEEPING_EVENT_TYPES:
            if (
                current["canonical_state"]["self_model"]
                != previous["canonical_state"]["self_model"]
            ):
                author = restater = current
            elif current["event_type"] == "self_model_revised":
                restater = current
        authors[current["revision_id"]] = author
        restaters[current["revision_id"]] = restater
    return {
        "authored_at_revision_id": author["revision_id"],
        "authored_by_activation_id": author["actor"]["activation_id"],
        "authored_by_substrate_id": author["actor"]["substrate_id"],
        "restated_at_revision_id": restater["revision_id"],
        "restated_by_activation_id": restater["actor"]["activation_id"],
        "restated_by_substrate_id": restater["actor"]["substrate_id"],
    }


def restatement_due(provenance: dict[str, Any], bearer_substrate_id: str | None) -> bool:
    """A self-model last restated under another substrate should be restated by the bearer.

    An operator-authored self-model is the operator's definition and is not due.
    """

    restater = provenance["restated_by_substrate_id"]
    return restater is not None and restater != bearer_substrate_id


def receiver_baseline_index(chain: list[dict[str, Any]], substrate_id: str) -> int | None:
    """Return the position of the revision the substrate last authored, if any.

    Authored revisions define the baseline. Revisions TORC writes on the
    substrate's behalf, such as an accepted handoff, do not count, and neither
    does an interval during which the substrate bore the lineage without
    checkpointing.
    """

    return max(
        (
            position
            for position, revision in enumerate(chain)
            if revision["actor"]["substrate_id"] == substrate_id
            and revision["event_type"] not in BOOKKEEPING_EVENT_TYPES
        ),
        default=None,
    )


def changes_since_substrate(
    chain: list[dict[str, Any]], substrate_id: str
) -> dict[str, Any] | None:
    """Summarize tracked changes since the substrate last authored a revision.

    `added` is the net addition between the baseline and the head. `removed`
    reports every item that is absent from the head and whose latest removal
    happened, or was accounted for, after the baseline, with the disposition of
    that removal. An item added and resolved while the substrate was away is
    therefore reported, and a disposition recorded for an earlier removal never
    describes a later one.
    """

    index = receiver_baseline_index(chain, substrate_id)
    if index is None or index == len(chain) - 1:
        return None
    base, head = chain[index], chain[-1]
    latest: dict[tuple[str, str], dict[str, Any]] = {}
    for epoch in removal_epochs(chain):
        latest[(epoch["section"], epoch["item"])] = epoch
    added: dict[str, list[str]] = {}
    removed: dict[str, list[dict[str, str]]] = {}
    for section in TRACKED_CONTINUITY_SECTIONS:
        before = base["canonical_state"][section]
        after = head["canonical_state"][section]
        if new := [item for item in after if item not in before]:
            added[section] = new
        gone = []
        for (epoch_section, item), epoch in latest.items():
            if epoch_section != section or item in after or epoch["disposition"] == "restored":
                continue
            accounted_at = epoch["accounted_at_index"]
            if epoch["dropped_at_index"] <= index and (
                accounted_at is None or accounted_at <= index
            ):
                continue
            gone.append({"item": item, "disposition": epoch["disposition"] or "unaccounted"})
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
