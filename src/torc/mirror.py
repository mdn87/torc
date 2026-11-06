"""Scoped response projection; no inference, persistence, or execution authority."""

from __future__ import annotations

import hashlib
import json
import re
import textwrap
from copy import deepcopy
from datetime import datetime, timedelta

from .errors import InvalidInputError

SETTINGS_FORMAT = "torc-response-settings-v1"
DELIVERY_FORMAT = "torc-response-delivery-v1"
DEFAULTS = {
    "language": "plain", "explanation_depth": "detailed", "turn_length": "normal",
    "interaction": "continue", "screen": "unknown", "persona_ref": "default",
}
CHOICES = {
    "language": {"plain", "technical"}, "explanation_depth": {"concise", "detailed"},
    "turn_length": {"brief", "normal", "full"},
    "interaction": {"answer", "continue", "repair"},
    "screen": {"unknown", "available", "away"},
}
PRIORITY = {"inference": 1, "observation": 2, "preference": 3, "request": 4}
FACT_KINDS = {"outcome", "verification", "limitation", "decision", "next_action", "detail"}


def _require(condition, message):
    if not condition:
        raise InvalidInputError(f"Mirror: {message}")


def _text(value):
    return isinstance(value, str) and bool(value.strip())


def _keys(value, keys, name):
    _require(isinstance(value, dict) and set(value) == set(keys), f"invalid {name} fields")


def _time(value):
    _require(isinstance(value, str) and re.fullmatch(
        r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z", value,
    ), "timestamp must be UTC RFC 3339")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InvalidInputError("Mirror: invalid timestamp") from exc
    _require("T" in value and parsed.utcoffset() == timedelta(0), "invalid UTC timestamp")
    return parsed


def _stamp(value):
    return value.isoformat().replace("+00:00", "Z")


def _hash(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _settings_id(settings):
    payload = {key: value for key, value in settings.items() if key != "settings_id"}
    return "settings-" + _hash(json.dumps(payload, sort_keys=True, separators=(",", ":")))


def _binding(binding):
    _keys(binding, ["conversation_id", "task_id", "turn_id", "response_revision"], "binding")
    _require(all(_text(binding[key]) for key in ("conversation_id", "task_id", "turn_id")),
             "binding identifiers must be nonempty")
    _require(type(binding["response_revision"]) is int
             and 0 < binding["response_revision"] <= 2**53 - 1,
             "response revision must be a positive integer")


def _value(setting, value):
    _require(isinstance(setting, str) and setting in DEFAULTS and _text(value),
             "unknown setting or empty value")
    _require(setting not in CHOICES or value in CHOICES[setting], "invalid setting value")
    if setting == "persona_ref":
        _require(len(value) <= 200 and not any(c.isspace() for c in value),
                 "persona_ref must be a compact reference, not instructions")


def resolve_settings(binding, signals, *, now, ttl_seconds=300):
    """Resolve independently per setting. Evidence is supplied, never inferred here."""
    _binding(binding)
    current = _time(now)
    _require(type(ttl_seconds) is int and 0 < ttl_seconds <= 3600, "invalid settings TTL")
    _require(isinstance(signals, list), "signals must be a list")
    candidates = {name: [] for name in DEFAULTS}
    for signal in signals:
        _keys(signal, ["setting", "value", "kind", "source", "evidence_refs", "scope",
                       "observed_at", "expires_at"], "signal")
        setting, value, kind = signal["setting"], signal["value"], signal["kind"]
        _value(setting, value)
        _require(isinstance(kind, str) and kind in PRIORITY, "unknown signal kind")
        _require(isinstance(signal["source"], str) and signal["source"] in {
            "user", "surface", "agent", "quoted", "uncertain_transcript",
        }, "unknown signal source")
        refs, scope = signal["evidence_refs"], signal["scope"]
        _require(isinstance(refs, list) and refs and all(_text(ref) for ref in refs),
                 "signal requires evidence references")
        _require(isinstance(scope, dict) and set(scope) <= set(binding) - {"response_revision"}
                 and all(_text(v) for v in scope.values()), "invalid signal scope")
        observed = _time(signal["observed_at"])
        expires = _time(signal["expires_at"]) if signal["expires_at"] is not None else None
        _require(expires is None or expires > observed, "signal expires before observation")
        # Copied prose and uncertain ASR never acquire the authority of a user turn.
        if signal["source"] in {"quoted", "uncertain_transcript"}:
            continue
        if kind in {"request", "preference"}:
            _require(signal["source"] == "user", "explicit settings require user evidence")
        elif kind == "observation":
            _require(signal["source"] == "surface" and setting == "screen" and scope,
                     "only scoped screen observations are supported")
            _require(expires is not None, "surface observations must expire")
        else:
            _require(signal["source"] == "agent" and "task_id" in scope and expires,
                     "inferences require an agent, task scope, and expiration")
        _require(scope or kind == "preference", "only preferences may have global scope")
        if observed > current or (expires is not None and expires <= current):
            continue
        if any(binding[key] != value for key, value in scope.items()):
            continue
        candidates[setting].append((
            (PRIORITY[kind], len(scope), observed), value,
            {"kind": kind, "source": signal["source"], "evidence_refs": sorted(set(refs)),
             "scope": dict(scope), "observed_at": signal["observed_at"],
             "expires_at": signal["expires_at"],
             "confidence": "tentative" if kind == "inference" else (
                 "observed" if kind == "observation" else "explicit")},
        ))
    values, provenance = dict(DEFAULTS), {}
    expiry = current + timedelta(seconds=ttl_seconds)
    for setting, options in candidates.items():
        if not options:
            provenance[setting] = {"kind": "default", "evidence_refs": []}
            continue
        rank = max(option[0] for option in options)
        winners = [option for option in options if option[0] == rank]
        _require(len({option[1] for option in winners}) == 1,
                 f"conflicting equally ranked evidence for {setting}")
        # Stable choice, with no vote count: echoes of one event cannot strengthen it.
        chosen = min(winners, key=lambda option: json.dumps(option[2], sort_keys=True))
        values[setting], provenance[setting] = chosen[1], chosen[2]
        if chosen[2]["expires_at"] is not None:
            expiry = min(expiry, _time(chosen[2]["expires_at"]))
    settings = {
        "format": SETTINGS_FORMAT, "binding": deepcopy(binding), "issued_at": now,
        "expires_at": _stamp(expiry), "values": values, "provenance": provenance,
    }
    settings["settings_id"] = _settings_id(settings)
    return settings


def _fresh(record, now):
    _require(_time(record["issued_at"]) <= _time(now) < _time(record["expires_at"]),
             "record is stale or issued in the future")


def _validate_settings(settings, binding, now):
    _keys(settings, ["format", "settings_id", "binding", "issued_at", "expires_at",
                     "values", "provenance"], "settings")
    _require(settings["format"] == SETTINGS_FORMAT, "unsupported settings version")
    _binding(binding)
    _require(settings["binding"] == binding, "settings binding does not match")
    _fresh(settings, now)
    _keys(settings["values"], DEFAULTS, "setting values")
    _keys(settings["provenance"], DEFAULTS, "setting provenance")
    for name, value in settings["values"].items():
        _value(name, value)
    _require(settings["settings_id"] == _settings_id(settings), "settings digest mismatch")


def render_context(settings, *, binding, now):
    """A small text-adapter input. Rendering is not proof of model compliance."""
    _validate_settings(settings, binding, now)
    return "\n".join([
        f"Mirror settings {settings['settings_id']} (expires {settings['expires_at']}).",
        "Preserve full task obligations, required verification, and permission boundaries.",
        "Delivery length does not reduce the work required. No setting grants approval.",
        *[f"{name}: {value}" for name, value in settings["values"].items()],
        "Use repair to correct the interpretation; continue the original authorized objective.",
        "The persona reference selects expression only; inferred settings remain tentative.",
    ])


def _result(result, written):
    _keys(result, ["status", "verification", "facts"], "result")
    _require(isinstance(result["status"], str)
             and result["status"] in {"in_progress", "blocked", "complete"}, "invalid work status")
    _require(isinstance(result["verification"], str)
             and result["verification"] in {"not_run", "partial", "passed", "failed"},
             "invalid verification status")
    facts = result["facts"]
    _require(isinstance(facts, list) and facts, "result requires facts")
    ids, kinds = set(), set()
    for fact in facts:
        _keys(fact, ["id", "kind", "text"], "fact")
        _require(_text(fact["id"]) and fact["id"] not in ids, "duplicate or empty fact id")
        _require(isinstance(fact["kind"], str) and fact["kind"] in FACT_KINDS
                 and _text(fact["text"]), "invalid fact")
        _require(fact["text"] in written, "fact is absent from the written result")
        ids.add(fact["id"])
        kinds.add(fact["kind"])
    _require({"outcome", "verification"} <= kinds, "outcome and verification facts are required")


def project_response(settings, result, written, response_id, *, now, target_chars=240):
    """Select supplied facts without paraphrase. The producer owns their truth/completeness."""
    binding = settings.get("binding") if isinstance(settings, dict) else None
    _validate_settings(settings, binding, now)
    _require(_text(written) and _text(response_id), "written result and response id are required")
    _require(type(target_chars) is int and 40 <= target_chars <= 2000, "invalid speech target")
    written = written.strip()
    _result(result, written)
    selected = [fact for fact in result["facts"]
                if fact["kind"] != "detail" or settings["values"]["turn_length"] != "brief"]
    speech = " ".join(" ".join(fact["text"].split()) for fact in selected)
    segments = textwrap.wrap(speech, width=target_chars, break_long_words=False,
                             break_on_hyphens=False)
    return {
        "format": DELIVERY_FORMAT, "binding": deepcopy(settings["binding"]),
        "settings_id": settings["settings_id"], "issued_at": now,
        "expires_at": settings["expires_at"],
        "source": {"response_id": response_id, "text_sha256": _hash(written)},
        "result": deepcopy(result), "written": written,
        "speech": {"fact_ids": [fact["id"] for fact in selected], "segments": segments,
                   "target_chars": target_chars, "restyle": False},
    }


def validate_delivery(record, *, binding, response_id, written, now):
    """Validate content fidelity and freshness against independently known source identity."""
    _keys(record, ["format", "binding", "settings_id", "issued_at", "expires_at", "source",
                   "result", "written", "speech"], "delivery")
    _require(record["format"] == DELIVERY_FORMAT, "unsupported delivery version")
    _binding(binding)
    _require(record["binding"] == binding, "delivery binding does not match")
    _require(isinstance(record["settings_id"], str)
             and re.fullmatch(r"settings-[a-f0-9]{64}", record["settings_id"]),
             "settings reference is invalid")
    _fresh(record, now)
    _keys(record["source"], ["response_id", "text_sha256"], "source")
    _require(_text(written) and record["written"] == written.strip(), "written source differs")
    expected_source = {"response_id": response_id, "text_sha256": _hash(written.strip())}
    _require(record["source"] == expected_source,
             "source identity or digest differs")
    _result(record["result"], record["written"])
    speech = record["speech"]
    _keys(speech, ["fact_ids", "segments", "target_chars", "restyle"], "speech")
    _require(speech["restyle"] is False, "protected speech cannot be restyled")
    _require(type(speech["target_chars"]) is int and 40 <= speech["target_chars"] <= 2000,
             "invalid speech target")
    ids, segments = speech["fact_ids"], speech["segments"]
    _require(isinstance(ids, list) and all(_text(item) for item in ids)
             and len(ids) == len(set(ids)), "invalid selected facts")
    facts = record["result"]["facts"]
    _require([fact["id"] for fact in facts if fact["id"] in ids] == ids,
             "selected facts are unknown or reordered")
    _require(all(fact["id"] in ids for fact in facts if fact["kind"] != "detail"),
             "required fact omitted")
    _require(isinstance(segments, list) and segments and all(_text(s) for s in segments),
             "speech segments are required")
    expected = " ".join(" ".join(fact["text"].split()) for fact in facts if fact["id"] in ids)
    _require(" ".join(" ".join(s.split()) for s in segments) == expected,
             "speech changed or omitted selected facts")


def render_text(record, *, binding, response_id, now):
    """Render the complete result; the caller separately supplies current binding."""
    validate_delivery(record, binding=binding, response_id=response_id,
                      written=record.get("written") if isinstance(record, dict) else None, now=now)
    return record["written"]
