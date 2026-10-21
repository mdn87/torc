"""Offline whole-task accounting over explicit request inventories and usage groups.

Each request belongs to at most one group: a request's counters, or a session's
counters covering several requests. Overlapping alternatives reject instead of
guessing which exporter to trust. All inventory/completeness/semantics assertions
are supplied by the evidence owner; this module does not discover model calls.
"""

from __future__ import annotations

from copy import deepcopy

from .canonical import canonical_json, payload_sha256
from .experiment_usage import TOKEN_FIELDS, normalize_usage

VERSION = "torc.continuation_usage.v0"
NORMALIZATION_VERSION = "torc.experiment_usage.normalize_usage.v1"


def _text(value, label):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _bool(record, key):
    if type(record.get(key)) is not bool:
        raise ValueError(f"{key} must be boolean")
    return record[key]


def _sum(values):
    return None if any(v is None for v in values) else sum(values)


def _group(raw, known_requests):
    group = deepcopy(raw)
    _text(group["group_id"], "group_id")
    members = group["request_ids"]
    if (not isinstance(members, list) or not members or len(set(members)) != len(members)
            or not set(members) <= known_requests):
        raise ValueError("usage group needs unique inventoried request IDs")
    mode = group["mode"]
    if mode not in {"cumulative", "deltas"}:
        raise ValueError("usage mode must be cumulative or deltas")
    _bool(group, "complete")
    _text(group["exporter_version"], "exporter_version")
    _text(group["source"], "source")
    semantics = group["semantics"]
    for key in ("proxy_compatible", "input_cache_nonoverlap"):
        if _bool(semantics, key):
            _text(semantics.get("evidence_ref"), "semantics evidence_ref")
    by_id, by_sequence = {}, {}
    retained = []
    if not isinstance(group["observations"], list):
        raise ValueError("observations must be a list")
    for observation in group["observations"]:
        if observation.get("mode", mode) != mode:
            raise ValueError("mixed observation counter modes")
        identity = _text(observation["observation_id"], "observation_id")
        _text(observation["evidence_ref"], "observation evidence_ref")
        sequence = observation["sequence"]
        if type(sequence) is not int or sequence < 0:
            raise ValueError("observation sequence must be a non-negative integer")
        normalized = normalize_usage(group["source"], observation["usage"])
        retained.append({**deepcopy(observation), "normalized": normalized})
        if identity in by_id:
            if canonical_json(observation) != canonical_json(by_id[identity]):
                raise ValueError("conflicting repeated observation ID")
            continue
        if sequence in by_sequence:
            raise ValueError("ambiguous observation sequence")
        by_id[identity] = observation
        by_sequence[sequence] = normalized
    ordered = [by_sequence[s] for s in sorted(by_sequence)]
    if mode == "cumulative":
        previous = {}
        for normalized in ordered:
            for field in TOKEN_FIELDS:
                value = normalized[field]
                if value is not None:
                    if field in previous and value < previous[field]:
                        raise ValueError("cumulative counter decreased; split counter epochs")
                    previous[field] = value
        # Do not fill missing final fields from earlier observations.
        counters = {f: ordered[-1][f] if ordered else None for f in TOKEN_FIELDS}
    else:
        counters = {f: _sum([n[f] for n in ordered]) if ordered else None for f in TOKEN_FIELDS}
    return {**group, "observations": retained, "counters": counters,
            "duplicate_observation_count": len(retained) - len(ordered),
            "normalization_version": NORMALIZATION_VERSION}


def _aggregate(groups, request_ids, inventory_complete):
    selected = [g for g in groups if set(g["request_ids"]) & request_ids]
    unallocated = [g["group_id"] for g in selected if not set(g["request_ids"]) <= request_ids]
    usable = [g for g in selected if g["group_id"] not in unallocated]
    covered = {r for g in selected for r in g["request_ids"]}
    uncovered = sorted(request_ids - covered)
    complete = inventory_complete and not uncovered and not unallocated
    totals, subtotals, missing = {}, {}, {}
    for field in TOKEN_FIELDS:
        values = [g["counters"][field] if g["complete"] else None for g in usable]
        totals[field] = _sum(values) if complete else None
        observed = [g["counters"][field] for g in usable if g["counters"][field] is not None]
        subtotals[field] = sum(observed) if observed else (0 if not request_ids else None)
        missing[field] = [g["group_id"] for g in usable
                          if not g["complete"] or g["counters"][field] is None]
    proxy_fields = ("input_tokens", "cache_write_input_tokens", "output_tokens")
    context_fields = ("input_tokens", "cached_input_tokens", "cache_write_input_tokens")

    def metric(fields, flag):
        if not all(g["semantics"][flag] for g in selected):
            return None, "counter_semantics_unverified"
        value = _sum([totals[f] for f in fields])
        return value, "missing_or_unallocated_usage" if value is None else None

    proxy, proxy_reason = metric(proxy_fields, "proxy_compatible")
    context, context_reason = metric(context_fields, "input_cache_nonoverlap")
    return {
        "totals": totals, "known_subtotals": subtotals,
        "missing_group_ids_by_field": missing,
        "uncovered_request_ids": uncovered, "unallocated_group_ids": unallocated,
        "request_inventory_complete": inventory_complete,
        "uncached_processed_token_proxy": proxy, "proxy_unavailable_reason": proxy_reason,
        "total_context_tokens": context, "context_unavailable_reason": context_reason,
        "api_cost": None, "api_cost_unavailable_reason": "no_actual_billing_evidence",
    }


def account_task(task: dict) -> dict:
    """Retain every attempted start and request through the declared task endpoint.

    Missing/partial usage propagates to totals. Known subtotals are diagnostics,
    never eligible savings endpoints. Cross-attempt session groups can establish
    a task total but cannot invent attempt or fallback cost allocations.
    """
    task = deepcopy(task)
    for field in ("task_id", "arm"):
        _text(task[field], field)
    if task["outcome"] not in {"verified_completion", "declared_failure"}:
        raise ValueError("task must end in verified_completion or declared_failure")
    if task["outcome"] == "verified_completion":
        _text(task.get("completion_evidence_ref"), "completion_evidence_ref")
    if not isinstance(task["attempts"], list) or not task["attempts"]:
        raise ValueError("at least one attempted start required")
    attempts, requests = {}, set()
    for attempt in task["attempts"]:
        identity = _text(attempt["attempt_id"], "attempt_id")
        if identity in attempts:
            raise ValueError("duplicate attempt ID")
        if attempt["status"] not in {"failed", "completed"}:
            raise ValueError("attempt must be terminal")
        for flag in ("context_delivered", "arm_independent_setup_failure", "requests_complete"):
            _bool(attempt, flag)
        parent = attempt.get("fallback_from")
        if parent is not None and (parent not in attempts
                                   or attempts[parent]["status"] != "failed"):
            raise ValueError("fallback must reference a preceding failed attempt")
        if not isinstance(attempt["requests"], list):
            raise ValueError("requests must be a list")
        for request in attempt["requests"]:
            request_id = _text(request["request_id"], "request_id")
            for field in ("role", "phase"):
                _text(request[field], field)
            if request_id in requests:
                raise ValueError("duplicate request ID; scope IDs before accounting")
            requests.add(request_id)
        if attempt.get("exclusion_reason") is not None:
            _text(attempt["exclusion_reason"], "exclusion_reason")
            if (attempt["status"] != "failed" or attempt["context_delivered"]
                    or not attempt["arm_independent_setup_failure"] or attempt["requests"]
                    or not attempt["requests_complete"] or parent is not None):
                raise ValueError("invalid setup exclusion")
        attempts[identity] = attempt
    groups, covered, group_ids = [], set(), set()
    for raw in task["usage_groups"]:
        group = _group(raw, requests)
        if group["group_id"] in group_ids:
            raise ValueError("duplicate usage group ID")
        if covered & set(group["request_ids"]):
            raise ValueError("overlapping usage groups; choose one counter basis per request")
        covered.update(group["request_ids"])
        group_ids.add(group["group_id"])
        groups.append(group)
    details = []
    for attempt in attempts.values():
        members = {r["request_id"] for r in attempt["requests"]}
        details.append({**attempt, **_aggregate(groups, members, attempt["requests_complete"])})
    return {
        "schema_version": VERSION, "normalization_version": NORMALIZATION_VERSION,
        "input_sha256": payload_sha256(task), "task_id": task["task_id"], "arm": task["arm"],
        "outcome": task["outcome"], "completion_evidence_ref": task.get("completion_evidence_ref"),
        "attempt_count": len(attempts),
        "failed_attempt_count": sum(a["status"] == "failed" for a in attempts.values()),
        "fallback_attempt_count": sum(a.get("fallback_from") is not None
                                      for a in attempts.values()),
        "excluded_attempt_count": sum(a.get("exclusion_reason") is not None
                                      for a in attempts.values()),
        "request_count": len(requests), "attempts": details, "groups": groups,
        **_aggregate(groups, requests, all(a["requests_complete"] for a in attempts.values())),
        "input": task,
        "limitations": ["Supplied inventory and semantics are not independently verified.",
                        "Synthetic/offline arithmetic does not establish savings or task quality.",
                        "Known subtotals exclude unknown usage and are not full-task endpoints."],
    }
