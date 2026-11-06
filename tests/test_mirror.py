"""Mirror preserves obligations and fact coverage while changing delivery."""

from copy import deepcopy

import pytest

from torc.errors import InvalidInputError
from torc.mirror import project_response, render_context, render_text, resolve_settings

NOW = "2026-11-06T12:00:00Z"
LATER = "2026-11-06T12:06:00Z"
BINDING = {
    "conversation_id": "session-1", "task_id": "analysis", "turn_id": "turn-2",
    "response_revision": 1,
}


def signal(setting, value, *, kind="request", source="user", scope=None, **changes):
    return {
        "setting": setting, "value": value, "kind": kind, "source": source,
        "evidence_refs": [f"user:{setting}"],
        "scope": scope if scope is not None else {"task_id": "analysis"},
        "observed_at": "2026-11-06T11:59:00Z", "expires_at": LATER,
        **changes,
    }


def result():
    return {
        "status": "in_progress", "verification": "partial",
        "facts": [
            {"id": "outcome", "kind": "outcome", "text": "The full report is written."},
            {"id": "checks", "kind": "verification", "text": "Fixture checks pass."},
            {"id": "limit", "kind": "limitation", "text": "Hardware playback is unverified."},
            {"id": "decision", "kind": "decision", "text": "Approve only after playback passes."},
            {"id": "detail", "kind": "detail", "text": "The appendix has every comparison."},
        ],
    }


def delivery(**kwargs):
    settings = resolve_settings(BINDING, [signal("turn_length", "brief")], now=NOW)
    facts = result()
    written = "\n\n".join(fact["text"] for fact in facts["facts"])
    return project_response(settings, facts, written, "reply-2", now=NOW, **kwargs)


def test_brief_speech_does_not_lower_depth_or_change_persona():
    signals = [
        signal("explanation_depth", "detailed", kind="preference", scope={}),
        signal("persona_ref", "masq:dean", kind="preference", scope={}),
        signal("turn_length", "brief"),
        signal("explanation_depth", "concise", kind="inference", source="agent"),
    ]
    before = deepcopy(signals)
    settings = resolve_settings(BINDING, signals, now=NOW)
    assert settings["values"]["turn_length"] == "brief"
    assert settings["values"]["explanation_depth"] == "detailed"
    assert settings["values"]["persona_ref"] == "masq:dean"
    assert settings["provenance"]["explanation_depth"]["kind"] == "preference"
    assert signals == before
    assert "task obligations" in render_context(settings, binding=BINDING, now=NOW)


def test_signal_order_and_echoes_cannot_change_resolution():
    signals = [signal("language", "plain"), signal("screen", "away")]
    expected = resolve_settings(BINDING, signals, now=NOW)
    assert resolve_settings(BINDING, signals[::-1] + signals, now=NOW) == expected


def test_scope_expiry_quotes_and_uncertain_transcription_are_not_preferences():
    signals = [
        signal("language", "technical", scope={"task_id": "unrelated"}),
        signal("screen", "away", expires_at=NOW),
        signal("persona_ref", "masq:quoted", source="quoted"),
        signal("turn_length", "brief", source="uncertain_transcript"),
    ]
    settings = resolve_settings(BINDING, signals, now=NOW)
    assert settings["values"]["language"] == "plain"
    assert settings["values"]["screen"] == "unknown"
    assert settings["values"]["persona_ref"] == "default"
    assert settings["values"]["turn_length"] == "normal"


def test_return_to_screen_applies_per_setting_and_expiry_recomputes():
    signals = [signal("screen", "away"), signal("turn_length", "brief")]
    signals += [
        signal("screen", "available", observed_at=NOW),
        signal("turn_length", "full", observed_at=NOW),
    ]
    resolved = resolve_settings(BINDING, signals, now=NOW)
    assert resolved["values"]["screen"] == "available"
    assert resolved["values"]["turn_length"] == "full"
    assert resolve_settings(BINDING, signals, now=LATER)["values"]["screen"] == "unknown"


def test_current_turn_intent_overrides_an_older_task_request_with_more_scope_keys():
    settings = resolve_settings(BINDING, [
        signal("screen", "away", scope={"conversation_id": "session-1", "task_id": "analysis"}),
        signal("screen", "available", scope={"turn_id": "turn-2"}, observed_at=NOW),
    ], now=NOW)
    assert settings["values"]["screen"] == "available"


@pytest.mark.parametrize("changes", [
    {"expires_at": None}, {"scope": {}}, {"source": "user"},
])
def test_inferences_require_source_task_scope_and_expiration(changes):
    with pytest.raises(InvalidInputError):
        resolve_settings(BINDING, [signal(
            "language", "technical", kind="inference", source="agent", **{
                key: value for key, value in changes.items() if key != "source"
            },
        ) | ({"source": changes["source"]} if "source" in changes else {})], now=NOW)


def test_equal_priority_conflicting_evidence_is_explicit_error():
    with pytest.raises(InvalidInputError, match="conflicting"):
        resolve_settings(BINDING, [
            signal("screen", "away", evidence_refs=["event-1"]),
            signal("screen", "available", evidence_refs=["event-2"]),
        ], now=NOW)


def test_brief_projection_preserves_every_required_fact_and_full_written_result():
    record = delivery()
    assert record["speech"]["fact_ids"] == ["outcome", "checks", "limit", "decision"]
    speech = " ".join(record["speech"]["segments"])
    for fact in result()["facts"][:-1]:
        assert fact["text"] in speech
    assert result()["facts"][-1]["text"] not in speech
    assert result()["facts"][-1]["text"] in render_text(
        record, binding=BINDING, response_id="reply-2", now=NOW,
    )
    assert record["result"]["status"] == "in_progress"
    assert record["result"]["verification"] == "partial"
    assert record["speech"]["restyle"] is False


def test_long_decision_is_segmented_without_losing_conditions():
    settings = resolve_settings(BINDING, [], now=NOW)
    facts = result()
    facts["facts"][3]["text"] = (
        "Only approve after every required hardware check passes. " * 10
    ).strip()
    written = "\n\n".join(fact["text"] for fact in facts["facts"])
    record = project_response(settings, facts, written, "reply-2", now=NOW, target_chars=100)
    assert len(record["speech"]["segments"]) > 5
    assert all(len(segment) <= 100 for segment in record["speech"]["segments"])
    assert " ".join(record["speech"]["segments"]) == " ".join(written.split())


def test_fact_not_in_written_result_cannot_be_promoted_to_speech():
    settings = resolve_settings(BINDING, [], now=NOW)
    with pytest.raises(InvalidInputError, match="written"):
        project_response(settings, result(), "Everything is finished!", "reply-2", now=NOW)


@pytest.mark.parametrize("mutation", ["stale", "revision", "source", "drop", "rewrite"])
def test_text_adapter_rejects_invalid_or_superseded_delivery(mutation):
    record = delivery()
    binding, response_id, now = dict(BINDING), "reply-2", NOW
    if mutation == "stale":
        now = LATER
    elif mutation == "revision":
        binding["response_revision"] = 2
    elif mutation == "source":
        response_id = "reply-3"
    elif mutation == "drop":
        record["speech"]["fact_ids"].remove("limit")
    else:
        record["speech"]["segments"] = ["Everything is complete and verified."]
    with pytest.raises(InvalidInputError):
        render_text(record, binding=binding, response_id=response_id, now=now)


def test_settings_expire_at_earliest_selected_signal_and_cannot_be_reused():
    settings = resolve_settings(BINDING, [signal(
        "screen", "away", expires_at="2026-11-06T12:00:30Z",
    )], now=NOW)
    assert settings["expires_at"] == "2026-11-06T12:00:30Z"
    with pytest.raises(InvalidInputError):
        render_context(settings, binding=BINDING, now=LATER)


@pytest.mark.parametrize("field", ["kind", "setting", "source", "value"])
def test_malformed_signal_fields_are_domain_errors(field):
    malformed = signal("screen", "away")
    malformed[field] = ["not a string"]
    with pytest.raises(InvalidInputError):
        resolve_settings(BINDING, [malformed], now=NOW)


@pytest.mark.parametrize("binding,now", [
    (BINDING | {"response_revision": 2**53}, NOW),
    (BINDING, "2026-11-06T12:00Z"),
])
def test_contract_uses_portable_integer_and_timestamp_forms(binding, now):
    with pytest.raises(InvalidInputError):
        resolve_settings(binding, [], now=now)
