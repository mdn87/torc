from __future__ import annotations

from collections.abc import Mapping


def merge_headers(
    defaults: Mapping[str, str], overrides: Mapping[str, str]
) -> dict[str, str]:
    """Return defaults updated with request-specific overrides."""

    merged = dict(defaults)
    merged.update(overrides)
    return merged
