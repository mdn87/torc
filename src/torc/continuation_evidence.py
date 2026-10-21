"""Import supplied Codex response counters as offline diagnostics.

The importer does not discover responses or authenticate evidence references.
It only deduplicates and accounts for records supplied by an evidence owner.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from copy import deepcopy
from typing import Any

from .canonical import canonical_json, payload_sha256
from .experiment_usage import TOKEN_FIELDS, normalize_usage

VERSION = "torc.continuation_evidence.v0"
NORMALIZATION_VERSION = "torc.experiment_usage.normalize_usage.v1"


def _text(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _epoch(value: Any) -> str | int:
    if isinstance(value, str) and value.strip():
        return value
    if not isinstance(value, bool) and isinstance(value, int) and value >= 0:
        return value
    raise ValueError("counter_epoch must be a nonempty string or non-negative integer")


def _owned_ids(values: Iterable[str]) -> list[str]:
    if isinstance(values, (str, bytes)):
        raise ValueError("owned_attempt_ids must be an iterable of attempt IDs")
    try:
        result = list(values)
    except TypeError as error:
        raise ValueError("owned_attempt_ids must be an iterable of attempt IDs") from error
    for value in result:
        _text(value, "owned attempt ID")
    if len(set(result)) != len(result):
        raise ValueError("owned_attempt_ids must be unique")
    return sorted(result)


def _sum_increments(responses: list[dict[str, Any]]) -> dict[str, int | None]:
    sums: dict[str, int | None] = {}
    for field in TOKEN_FIELDS:
        values = [response["incremental_usage"][field] for response in responses]
        sums[field] = sum(values) if values and all(value is not None for value in values) else None
    return sums


def _increment(
    total: Mapping[str, Any], baseline: Mapping[str, Any]
) -> dict[str, int | None]:
    result: dict[str, int | None] = {}
    for field in TOKEN_FIELDS:
        total_value = total[field]
        baseline_value = baseline[field]
        if total_value is not None and baseline_value is not None and baseline_value > total_value:
            raise ValueError(f"baseline counter exceeds cumulative counter for {field}")
        result[field] = (
            total_value - baseline_value
            if total_value is not None and baseline_value is not None
            else None
        )
    return result


def import_responses(
    records: list[Mapping[str, Any]], *, owned_attempt_ids: Iterable[str]
) -> dict[str, Any]:
    """Return diagnostics for owner-supplied cumulative response counters.

    Input order is the counter order within an epoch. Exact repeated response
    records are retained in ``input`` but contribute only once to diagnostics.
    The first record may omit a baseline, in which case its increment remains
    unknown. Every subsequently introduced epoch needs an explicit baseline.
    """

    if not isinstance(records, list):
        raise ValueError("records must be a list")
    owned = _owned_ids(owned_attempt_ids)
    owned_set = set(owned)
    supplied = deepcopy(records)

    unique: list[dict[str, Any]] = []
    by_response_id: dict[str, str] = {}
    duplicate_count = 0
    for raw in records:
        if not isinstance(raw, Mapping):
            raise ValueError("each response record must be an object")
        record = deepcopy(dict(raw))
        required = {
            "response_id", "attempt_id", "evidence_ref", "counter_epoch",
            "cumulative_usage", "baseline_usage",
        }
        missing = sorted(required - record.keys())
        if missing:
            raise ValueError(f"response record missing required fields: {', '.join(missing)}")
        response_id = _text(record["response_id"], "response_id")
        attempt_id = _text(record["attempt_id"], "attempt_id")
        _text(record["evidence_ref"], "evidence_ref")
        _epoch(record["counter_epoch"])
        if attempt_id not in owned_set:
            raise ValueError(f"response references unknown attempt: {attempt_id}")
        if not isinstance(record["cumulative_usage"], Mapping):
            raise ValueError("cumulative_usage must be an object")
        if record["baseline_usage"] is not None:
            if not isinstance(record["baseline_usage"], Mapping):
                raise ValueError("baseline_usage must be an object or null")
            _text(record.get("baseline_evidence_ref"), "baseline_evidence_ref")

        serialized = canonical_json(record)
        if response_id in by_response_id:
            if serialized != by_response_id[response_id]:
                raise ValueError("conflicting repeated response ID")
            duplicate_count += 1
            continue
        by_response_id[response_id] = serialized
        unique.append(record)

    responses: list[dict[str, Any]] = []
    epoch_previous: dict[str | int, dict[str, Any]] = {}
    epoch_maximum: dict[str | int, dict[str, int]] = {}
    first_epoch: str | int | None = None
    for record in unique:
        epoch = record["counter_epoch"]
        total = normalize_usage("codex", record["cumulative_usage"])
        explicit_baseline = record["baseline_usage"] is not None
        if first_epoch is None:
            first_epoch = epoch
        if epoch not in epoch_previous and epoch != first_epoch and not explicit_baseline:
            raise ValueError("distinct counter epoch requires explicit baseline")

        previous_maximum = epoch_maximum.setdefault(epoch, {})
        for field in TOKEN_FIELDS:
            value = total[field]
            if value is None:
                continue
            if field in previous_maximum and value < previous_maximum[field]:
                raise ValueError(f"cumulative counter decreased within epoch for {field}")
            previous_maximum[field] = value

        if explicit_baseline:
            baseline = normalize_usage("codex", record["baseline_usage"])
            if epoch in epoch_previous:
                previous = epoch_previous[epoch]["normalized_cumulative_usage"]
                if any(baseline[field] is not None and previous[field] is not None
                       and baseline[field] < previous[field] for field in TOKEN_FIELDS):
                    raise ValueError("explicit baseline overlaps an already counted response")
            baseline_source = "explicit"
        elif epoch in epoch_previous:
            baseline = epoch_previous[epoch]["normalized_cumulative_usage"]
            baseline_source = "preceding_response"
        else:
            baseline = normalize_usage("codex", None)
            baseline_source = "missing"

        incremental = _increment(total, baseline)
        response = {
            **record,
            "normalized_cumulative_usage": total,
            "normalized_baseline_usage": baseline,
            "baseline_source": baseline_source,
            "incremental_usage": incremental,
            "missing_incremental_fields": [
                field for field in TOKEN_FIELDS if incremental[field] is None
            ],
        }
        responses.append(response)
        epoch_previous[epoch] = response

    attempts = []
    for attempt_id in owned:
        attempt_responses = [
            response for response in responses if response["attempt_id"] == attempt_id
        ]
        attempts.append({
            "attempt_id": attempt_id,
            "response_count": len(attempt_responses),
            "response_evidence_missing": not attempt_responses,
            "observed_incremental_sums": _sum_increments(attempt_responses),
        })
    missing_attempts = [
        attempt["attempt_id"] for attempt in attempts if attempt["response_evidence_missing"]
    ]

    return {
        "schema_version": VERSION,
        "normalization_version": NORMALIZATION_VERSION,
        "input_sha256": payload_sha256(supplied),
        "input": supplied,
        "owned_attempt_ids": owned,
        "response_count": len(responses),
        "duplicate_response_count": duplicate_count,
        "responses": responses,
        "attempts": attempts,
        "missing_attempt_ids": missing_attempts,
        "observed_incremental_sums": _sum_increments(responses),
        "provider_coverage_complete": None,
        "proxy_compatible": None,
        "api_cost": None,
        "savings_eligible": None,
        "whole_task_savings_available": False,
        "whole_task_savings_unavailable_reason": (
            "hidden_retries_and_failed_request_coverage_unknown"
        ),
        "limitations": [
            "Supplied response records and evidence references are not authenticated.",
            "Hidden retries and failed-request coverage remain unknown.",
            "Observed increments do not establish complete provider usage, API cost, or savings.",
        ],
    }
