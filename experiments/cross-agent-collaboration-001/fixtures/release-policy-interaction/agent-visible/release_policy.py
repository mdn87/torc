from __future__ import annotations

from collections.abc import Iterable, Mapping


def release_allowed(
    attested_digest: str,
    artifact_digest: str,
    changes: Iterable[Mapping[str, str]],
    allowed_roots: Iterable[str],
) -> bool:
    """Return whether a release is attested and every destination is in scope."""

    if attested_digest != artifact_digest:
        return False
    roots = tuple(allowed_roots)
    return all(
        any(change["path"].startswith(root) for root in roots) for change in changes
    )
