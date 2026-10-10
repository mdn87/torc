from __future__ import annotations

from unittest.mock import patch

import pytest
from release_policy import release_allowed


def _allowed(changes: list[dict[str, str]], roots: list[str] | None = None) -> bool:
    return release_allowed(
        "sha256:trusted",
        "sha256:trusted",
        changes,
        roots if roots is not None else ["services/api"],
    )


def test_digest_uses_constant_time_comparison() -> None:
    with patch("release_policy.hmac.compare_digest", return_value=True) as compare:
        assert _allowed([{"action": "modify", "path": "services/api/app.py"}])

    compare.assert_called_once_with("sha256:trusted", "sha256:trusted")


@pytest.mark.parametrize(
    "path",
    [
        "services/api-evil/config.py",
        "services/api/../secrets.txt",
        "/services/api/config.py",
        "services\\api\\config.py",
        "services//api/config.py",
    ],
)
def test_lookalike_or_malformed_paths_are_denied(path: str) -> None:
    assert not _allowed([{"action": "modify", "path": path}])


def test_rename_requires_both_endpoints_in_scope() -> None:
    assert not _allowed(
        [
            {
                "action": "rename",
                "from_path": "infrastructure/prod.tf",
                "path": "services/api/prod.tf",
            }
        ]
    )


def test_valid_in_scope_rename_is_allowed() -> None:
    assert _allowed(
        [
            {
                "action": "rename",
                "from_path": "services/api/old.py",
                "path": "services/api/new.py",
            }
        ]
    )


@pytest.mark.parametrize(
    "changes,roots",
    [
        ([{"action": "copy", "path": "services/api/a.py"}], ["services/api"]),
        ([{"action": "rename", "path": "services/api/a.py"}], ["services/api"]),
        ([{"action": "modify"}], ["services/api"]),
        ([{"action": "modify", "path": "services/api/a.py"}], []),
        ([{"action": "modify", "path": "services/api/a.py"}], ["services/../api"]),
    ],
)
def test_malformed_inputs_fail_closed(
    changes: list[dict[str, str]], roots: list[str]
) -> None:
    assert not release_allowed("sha256:x", "sha256:x", changes, roots)


def test_inputs_are_not_mutated() -> None:
    change = {"action": "modify", "path": "services/api/a.py"}
    roots = ["services/api"]

    assert _allowed([change], roots)
    assert change == {"action": "modify", "path": "services/api/a.py"}
    assert roots == ["services/api"]
