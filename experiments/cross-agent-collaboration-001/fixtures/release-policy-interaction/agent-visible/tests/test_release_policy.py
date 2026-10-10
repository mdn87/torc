from release_policy import release_allowed


def test_allows_attested_changes_below_declared_roots() -> None:
    changes = [
        {"action": "modify", "path": "services/api/config.py"},
        {"action": "add", "path": "docs/release.md"},
    ]

    assert release_allowed("sha256:abc", "sha256:abc", changes, ["services/api", "docs"])


def test_denies_digest_mismatch() -> None:
    changes = [{"action": "modify", "path": "services/api/config.py"}]

    assert not release_allowed("sha256:abc", "sha256:def", changes, ["services/api"])


def test_denies_obvious_out_of_scope_destination() -> None:
    changes = [{"action": "delete", "path": "infrastructure/prod.tf"}]

    assert not release_allowed("sha256:abc", "sha256:abc", changes, ["services/api"])
