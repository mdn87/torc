"""Provider-neutral experiment usage records without invented counters."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


class UsageNormalizationError(ValueError):
    """Raised when provider usage cannot be represented without ambiguity."""


TOKEN_FIELDS = (
    "input_tokens",
    "cached_input_tokens",
    "cache_write_input_tokens",
    "reasoning_output_tokens",
    "output_tokens",
)

_ALIASES = {
    "input_tokens": ("input_tokens", "inputTokens"),
    "cached_input_tokens": (
        "cached_input_tokens",
        "cachedInputTokens",
        "cache_read_input_tokens",
    ),
    "cache_write_input_tokens": (
        "cache_write_input_tokens",
        "cacheWriteInputTokens",
        "cache_creation_input_tokens",
    ),
    "reasoning_output_tokens": (
        "reasoning_output_tokens",
        "reasoningOutputTokens",
    ),
    "output_tokens": ("output_tokens", "outputTokens"),
}


def _counter(field: str, aliases: tuple[str, ...], raw: Mapping[str, Any]) -> int | None:
    observed: list[tuple[str, int]] = []
    for alias in aliases:
        if alias not in raw:
            continue
        value = raw[alias]
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            raise UsageNormalizationError(
                f"usage counter {alias!r} for {field!r} must be a non-negative integer"
            )
        observed.append((alias, value))
    values = {value for _, value in observed}
    if len(values) > 1:
        names = ", ".join(alias for alias, _ in observed)
        raise UsageNormalizationError(f"conflicting counters for {field!r}: {names}")
    return observed[0][1] if observed else None


def normalize_usage(
    source: str, raw: Mapping[str, Any] | None
) -> dict[str, Any]:
    """Normalize known token counters while retaining the provider record.

    A missing counter remains ``None``. Provider tokenizers and accounting rules
    differ, so this function deliberately does not manufacture a cross-provider
    total.
    """

    if not isinstance(source, str) or not source.strip():
        raise UsageNormalizationError("usage source must be a non-empty string")
    if raw is not None and not isinstance(raw, Mapping):
        raise UsageNormalizationError("provider usage must be an object or null")

    provider_usage = dict(raw or {})
    normalized = {
        field: _counter(field, aliases, provider_usage)
        for field, aliases in _ALIASES.items()
    }
    reported = [field for field in TOKEN_FIELDS if normalized[field] is not None]
    return {
        "schema_version": 1,
        "source": source.strip(),
        "supplied": raw is not None,
        **normalized,
        "reported_fields": reported,
        "unreported_fields": [field for field in TOKEN_FIELDS if field not in reported],
        "provider_usage": provider_usage,
    }


def latest_codex_usage(events: list[Mapping[str, Any]]) -> Mapping[str, Any] | None:
    """Return the last usage object emitted by Codex JSONL or app-server events."""

    for event in reversed(events):
        candidates: list[Any] = [event.get("usage")]
        params = event.get("params")
        if isinstance(params, Mapping):
            candidates.append(params.get("usage"))
            token_usage = params.get("tokenUsage")
            if isinstance(token_usage, Mapping):
                candidates.extend((token_usage.get("last"), token_usage.get("total")))
            candidates.append(token_usage)
        for candidate in candidates:
            if isinstance(candidate, Mapping):
                return candidate
    return None
