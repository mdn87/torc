"""Pure projection of supplied continuation traces into blinded observations.

The collector validates and summarizes evidence.  It neither authenticates the
execution owner nor calls an assessor, provider, tool, or execution runtime.
"""

from __future__ import annotations

import math
from copy import deepcopy
from typing import Any

from .canonical import payload_sha256

VERSION = "torc.continuation_observations.v0"
ACTION_KINDS = frozenset({"read", "search", "edit", "test", "other"})
RESULT_STATUSES = frozenset({"success", "failure", "unknown"})
PHASES = frozenset({"preparation", "queue", "attempt", "worker_execution", "execution",
                    "recovery", "verification", "scoring"})


def _finite_nonnegative(value: Any, field: str) -> float | int:
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{field} must be finite and nonnegative")
    return value


def _required_mapping_list(trace: dict[str, Any], field: str) -> list[dict[str, Any]]:
    value = trace.get(field)
    if not isinstance(value, list) or any(not isinstance(item, dict) for item in value):
        raise ValueError(f"{field} must be a list of objects")
    return value


def _public_events(events: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    public = []
    previous_sequence: int | None = None
    previous_time: float | int | None = None
    seen: set[int] = set()
    assessable = 0
    repeated = 0
    unknown = 0

    for event in events:
        sequence = event.get("sequence")
        if type(sequence) is not int or sequence in seen or (
            previous_sequence is not None and sequence <= previous_sequence
        ):
            raise ValueError("event sequence must be ordered and unique integers")
        relative_seconds = event.get("relative_seconds")
        if relative_seconds is not None:
            _finite_nonnegative(relative_seconds, "event relative_seconds")
            if previous_time is not None and relative_seconds < previous_time:
                raise ValueError("event relative_seconds must be monotonic")

        action_kind = event.get("action_kind", "other")
        result_status = event.get("result_status", "unknown")
        if action_kind not in ACTION_KINDS:
            raise ValueError("invalid action_kind")
        if result_status not in RESULT_STATUSES:
            raise ValueError("invalid result_status")

        # Raw content is withheld, so this packet cannot substantiate a supplied
        # investigation judgment. A separate blinded assessment is required.
        classification = "unassessable"

        item = {
            "sequence": sequence,
            "action_kind": action_kind,
            "result_status": result_status,
            "relative_seconds": relative_seconds,
            "classification": classification,
        }
        unknown += 1
        public.append(item)
        seen.add(sequence)
        previous_sequence = sequence
        if relative_seconds is not None:
            previous_time = relative_seconds

    return public, {
        "event_count": len(events),
        "assessable_event_count": assessable,
        "repeated_investigation_count": repeated,
        "unknown_event_count": unknown,
    }


def _public_timing(intervals: list[dict[str, Any]]) -> dict[str, Any]:
    validated = []
    bounds = []
    clock_ids = set()
    clocks_known = True
    for interval in intervals:
        phase = interval.get("phase")
        if not isinstance(phase, str) or not phase:
            raise ValueError("interval phase must be a nonempty string")
        start = interval.get("start_monotonic")
        end = interval.get("end_monotonic")
        if (
            type(start) not in (int, float)
            or type(end) not in (int, float)
            or not math.isfinite(start)
            or not math.isfinite(end)
            or end < start
        ):
            raise ValueError("interval bounds must be finite and not inverted")
        clock_id = interval.get("clock_id")
        if not isinstance(clock_id, str) or not clock_id:
            clocks_known = False
        else:
            clock_ids.add(clock_id)
        validated.append((phase if phase in PHASES else "other", end - start))
        bounds.append((start, end))

    one_known_clock = clocks_known and len(clock_ids) == 1
    public_intervals = [
        {"phase": phase, "duration_seconds": duration if one_known_clock else None}
        for phase, duration in validated
    ]
    return {
        "clock_id": "one_monotonic_clock" if one_known_clock else None,
        "duration_seconds": (
            max(end for _, end in bounds) - min(start for start, _ in bounds)
            if one_known_clock else None
        ),
        "intervals": public_intervals,
    }


def _public_interventions(
    interventions: list[dict[str, Any]], *, capture_complete: bool
) -> dict[str, Any]:
    active_seconds = []
    every_entry_explicit = True
    for intervention in interventions:
        if "active_seconds" not in intervention:
            every_entry_explicit = False
            continue
        active_seconds.append(
            _finite_nonnegative(intervention["active_seconds"], "intervention active_seconds")
        )
    return {
        "count": len(interventions),
        "active_seconds": (
            sum(active_seconds) if capture_complete and every_entry_explicit else None
        ),
    }


def collect_observations(
    trace: dict[str, Any], *, opaque_id: str
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Return a blinded public packet and hash-bound private provenance.

    Classifications and owner assertions are treated only as supplied evidence.
    Missing evidence remains unknown; no value is inferred from raw content.
    """
    if not isinstance(trace, dict):
        raise ValueError("trace must be an object")
    if not isinstance(opaque_id, str) or not opaque_id:
        raise ValueError("opaque_id must be a nonempty string")
    for field in ("trial_id", "attempt_id"):
        if not isinstance(trace.get(field), str) or not trace[field]:
            raise ValueError(f"{field} must be a nonempty string")
    for field in ("candidate_sha256", "workspace_sha256"):
        value = trace.get(field)
        if (
            not isinstance(value, str)
            or len(value) != 64
            or any(character not in "0123456789abcdef" for character in value)
        ):
            raise ValueError(f"{field} must be a lowercase SHA-256 digest")
    if type(trace.get("complete")) is not bool:
        raise ValueError("complete must be a boolean")
    for field in ("process_tree_absent",):
        if field in trace and trace[field] is not None and type(trace[field]) is not bool:
            raise ValueError(f"{field} must be a boolean or null")
    owner_receipt_ref = trace.get("owner_receipt_ref")
    if owner_receipt_ref is not None and (
        not isinstance(owner_receipt_ref, str) or not owner_receipt_ref
    ):
        raise ValueError("owner_receipt_ref must be a nonempty string or null")

    events = _required_mapping_list(trace, "events")
    intervals = _required_mapping_list(trace, "intervals")
    interventions = _required_mapping_list(trace, "interventions")
    public_events, investigation = _public_events(events)
    if not trace["complete"] or investigation["assessable_event_count"] == 0:
        investigation["repeated_investigation_rate"] = None
    else:
        investigation["repeated_investigation_rate"] = (
            investigation["repeated_investigation_count"]
            / investigation["assessable_event_count"]
        )

    public_packet = {
        "schema_version": VERSION,
        "opaque_id": opaque_id,
        "candidate_sha256": trace["candidate_sha256"],
        "owner_receipt_ref": None,  # Raw owner paths can reveal the arm or session.
        "capture_complete": trace["complete"],
        "process_tree_absent": trace.get("process_tree_absent"),
        "events": public_events,
        "investigation": investigation,
        "timing": _public_timing(intervals),
        "interventions": _public_interventions(
            interventions, capture_complete=trace["complete"]
        ),
        "redaction": {
            "content_redacted": True,
            "fields_retained_privately": ["action", "evidence_ref", "result"],
        },
    }
    private_provenance = {
        "schema_version": VERSION,
        "opaque_id": opaque_id,
        "trial_id": trace["trial_id"],
        "attempt_id": trace["attempt_id"],
        "candidate_sha256": trace["candidate_sha256"],
        "workspace_sha256": trace["workspace_sha256"],
        "packet_sha256": payload_sha256(public_packet),
        "owner_receipt_ref": owner_receipt_ref,
        "capture_complete": trace["complete"],
        "process_tree_absent": trace.get("process_tree_absent"),
        "events": deepcopy(events),
        "intervals": deepcopy(intervals),
        "interventions": deepcopy(interventions),
        "trace": deepcopy(trace),
    }
    return public_packet, private_provenance
