"""Aggregate sanitized native-context pilot evidence without a model call."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC = REPO_ROOT / "src"
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

import native_context_request as request_builder  # noqa: E402

from torc.canonical import canonical_json  # noqa: E402


class NativeContextPilotReportError(RuntimeError):
    """Raised when pilot evidence is incomplete, duplicated, or inconsistent."""


def _read_object(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise NativeContextPilotReportError(f"cannot read {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise NativeContextPilotReportError(f"expected a JSON object: {path}")
    return value


def _number(value: Any, label: str) -> float:
    if (
        not isinstance(value, (int, float))
        or isinstance(value, bool)
        or value < 0
    ):
        raise NativeContextPilotReportError(f"pilot {label} is invalid")
    return float(value)


def _validate_record(record: dict[str, Any]) -> dict[str, Any]:
    if (
        record.get("schema_version") != 1
        or record.get("series_id") != "critic-transport-series-003"
        or record.get("status") != "validated"
    ):
        raise NativeContextPilotReportError("evidence is not a validated Series 003 result")
    arm = record.get("arm")
    if arm not in request_builder.ARMS:
        raise NativeContextPilotReportError("evidence has an unknown pilot arm")
    request = record.get("request")
    usage = record.get("usage")
    timing = record.get("timing")
    score = record.get("score")
    transport = record.get("transport")
    if not all(
        isinstance(item, dict)
        for item in (request, usage, timing, score, transport)
    ):
        raise NativeContextPilotReportError("evidence is missing a required section")
    expected_spawns = 0 if arm == "portable_direct" else 1
    if transport.get("spawn_call_count") != expected_spawns:
        raise NativeContextPilotReportError("evidence has the wrong spawn count")
    if score.get("arm") != arm or score.get("candidate_id") != record.get("candidate_id"):
        raise NativeContextPilotReportError("score identity does not match its evidence")
    candidate_id = record.get("candidate_id")
    model = record.get("model")
    if not isinstance(candidate_id, str) or not isinstance(model, str):
        raise NativeContextPilotReportError("evidence request identity is invalid")
    try:
        expected_request = request_builder.request_plan(
            candidate_id=candidate_id,
            arm=arm,
            model=model,
        )
    except request_builder.NativeContextRequestError as exc:
        raise NativeContextPilotReportError(
            f"evidence request is no longer reproducible: {exc}"
        ) from exc
    expected_fields = {
        "plan_sha256": expected_request["plan_sha256"],
        "input_sha256": expected_request["request_input_sha256"],
        "body_sha256": expected_request["request_body_sha256"],
        "input_bytes": expected_request["request_input_bytes"],
    }
    if any(request.get(key) != value for key, value in expected_fields.items()):
        raise NativeContextPilotReportError("evidence request hash or size has drifted")
    normalized = {
        "arm": arm,
        "candidate_id": candidate_id,
        "model": model,
        "response_id": record.get("response_id"),
        "plan_sha256": request.get("plan_sha256"),
        "request_body_sha256": request.get("body_sha256"),
        "request_input_bytes": _number(request.get("input_bytes"), "request bytes"),
        "input_tokens": _number(usage.get("input_tokens"), "input tokens"),
        "cached_input_tokens": _number(
            usage.get("cached_input_tokens"), "cached input tokens"
        ),
        "uncached_input_tokens": _number(
            usage.get("uncached_input_tokens"), "uncached input tokens"
        ),
        "output_tokens": _number(usage.get("output_tokens"), "output tokens"),
        "completion_ms": _number(timing.get("completion_ms"), "completion time"),
        "defect_area_recall": _number(
            score.get("defect_area_recall"), "defect-area recall"
        ),
        "unsupported_finding_count": _number(
            score.get("unsupported_finding_count"), "unsupported findings"
        ),
        "changes_requested_correct": score.get("changes_requested_correct") is True,
        "spawn_call_count": expected_spawns,
    }
    for label in ("candidate_id", "model", "response_id", "plan_sha256"):
        if not isinstance(normalized[label], str) or not normalized[label]:
            raise NativeContextPilotReportError(f"pilot {label} is invalid")
    return normalized


def _round(value: float) -> float:
    return round(value, 6)


def build_report(records: list[dict[str, Any]]) -> dict[str, Any]:
    """Validate zero to three arm results and apply the frozen pilot decisions."""
    normalized = [_validate_record(record) for record in records]
    by_arm: dict[str, dict[str, Any]] = {}
    for record in normalized:
        arm = record["arm"]
        if arm in by_arm:
            raise NativeContextPilotReportError(f"duplicate pilot arm: {arm}")
        by_arm[arm] = record
    identities = {
        (record["candidate_id"], record["model"], record["plan_sha256"])
        for record in normalized
    }
    if len(identities) > 1:
        raise NativeContextPilotReportError("pilot arms do not share one frozen identity")
    missing = [arm for arm in request_builder.ARMS if arm not in by_arm]
    report: dict[str, Any] = {
        "schema_version": 1,
        "series_id": "critic-transport-series-003",
        "status": "incomplete" if missing else "pilot_complete",
        "completed_arms": [arm for arm in request_builder.ARMS if arm in by_arm],
        "missing_arms": missing,
        "arms": [by_arm[arm] for arm in request_builder.ARMS if arm in by_arm],
        "comparisons": [],
        "surviving_native_arms": [],
        "recommendation": "collect_missing_pilot_arms" if missing else None,
    }
    if missing:
        return report

    direct = by_arm["portable_direct"]
    direct_uncached = direct["uncached_input_tokens"]
    direct_completion = direct["completion_ms"]
    if direct_uncached == 0 or direct_completion == 0:
        raise NativeContextPilotReportError("portable baseline cannot be zero")
    comparisons = []
    surviving = []
    for arm in ("native_isolated", "native_inherited"):
        native = by_arm[arm]
        input_savings = 100 * (
            direct_uncached - native["uncached_input_tokens"]
        ) / direct_uncached
        completion_overhead = 100 * (
            native["completion_ms"] - direct_completion
        ) / direct_completion
        quality_preserved = (
            native["changes_requested_correct"]
            and native["defect_area_recall"] >= direct["defect_area_recall"]
            and native["unsupported_finding_count"] == 0
        )
        pilot_survives = (
            quality_preserved
            and input_savings >= -10.0
            and completion_overhead <= 50.0
        )
        full_win_now = (
            quality_preserved
            and input_savings >= 15.0
            and completion_overhead <= 20.0
        )
        comparison = {
            "arm": arm,
            "uncached_input_savings_percent": _round(input_savings),
            "completion_overhead_percent": _round(completion_overhead),
            "quality_preserved": quality_preserved,
            "pilot_survives": pilot_survives,
            "meets_full_series_win_threshold_on_pilot": full_win_now,
        }
        comparisons.append(comparison)
        if pilot_survives:
            surviving.append(arm)
    report["comparisons"] = comparisons
    report["surviving_native_arms"] = surviving
    report["recommendation"] = (
        "continue_surviving_arms_to_repeats"
        if surviving
        else "stop_native_context_series"
    )
    return report


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("evidence", type=Path, nargs="*")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)
    try:
        print(canonical_json(build_report([_read_object(path) for path in args.evidence])))
        return 0
    except NativeContextPilotReportError as exc:
        print(canonical_json({"error": str(exc)}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
