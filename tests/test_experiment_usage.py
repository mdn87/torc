from __future__ import annotations

import pytest

from torc.experiment_usage import (
    UsageNormalizationError,
    latest_codex_usage,
    normalize_usage,
)


def test_normalizes_claude_usage_without_inventing_reasoning_tokens() -> None:
    raw = {
        "input_tokens": 100,
        "cache_read_input_tokens": 70,
        "cache_creation_input_tokens": 20,
        "output_tokens": 30,
    }

    result = normalize_usage("claude-code", raw)

    assert result["supplied"] is True
    assert result["input_tokens"] == 100
    assert result["cached_input_tokens"] == 70
    assert result["cache_write_input_tokens"] == 20
    assert result["reasoning_output_tokens"] is None
    assert result["output_tokens"] == 30
    assert result["provider_usage"] == raw
    assert result["unreported_fields"] == ["reasoning_output_tokens"]


def test_normalizes_codex_app_server_usage() -> None:
    result = normalize_usage(
        "codex-app-server",
        {
            "inputTokens": 101,
            "cachedInputTokens": 71,
            "cacheWriteInputTokens": 11,
            "reasoningOutputTokens": 21,
            "outputTokens": 31,
        },
    )

    assert result["reported_fields"] == [
        "input_tokens",
        "cached_input_tokens",
        "cache_write_input_tokens",
        "reasoning_output_tokens",
        "output_tokens",
    ]
    assert result["reasoning_output_tokens"] == 21


def test_missing_usage_is_distinct_from_a_supplied_zero() -> None:
    missing = normalize_usage("replay", None)
    zero = normalize_usage("provider", {"output_tokens": 0})

    assert missing["supplied"] is False
    assert missing["output_tokens"] is None
    assert zero["supplied"] is True
    assert zero["output_tokens"] == 0


@pytest.mark.parametrize("value", [-1, 1.5, True, "1"])
def test_invalid_counters_fail_closed(value: object) -> None:
    with pytest.raises(UsageNormalizationError, match="non-negative integer"):
        normalize_usage("provider", {"input_tokens": value})


def test_conflicting_aliases_fail_closed() -> None:
    with pytest.raises(UsageNormalizationError, match="conflicting counters"):
        normalize_usage("provider", {"input_tokens": 1, "inputTokens": 2})


def test_latest_codex_usage_accepts_jsonl_and_app_server_shapes() -> None:
    assert latest_codex_usage(
        [{"type": "turn.completed", "usage": {"input_tokens": 3}}]
    ) == {"input_tokens": 3}
    assert latest_codex_usage(
        [
            {
                "method": "thread/tokenUsage/updated",
                "params": {"tokenUsage": {"total": {"inputTokens": 9}}},
            }
        ]
    ) == {"inputTokens": 9}
