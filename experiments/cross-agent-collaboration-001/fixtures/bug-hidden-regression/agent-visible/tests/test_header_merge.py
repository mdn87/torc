from header_merge import merge_headers


def test_override_replaces_case_variant_in_place() -> None:
    result = merge_headers(
        {"Content-Type": "application/json", "Accept": "application/json"},
        {"content-type": "text/plain", "X-Trace": "trace-1"},
    )

    assert list(result.items()) == [
        ("content-type", "text/plain"),
        ("Accept", "application/json"),
        ("X-Trace", "trace-1"),
    ]


def test_new_overrides_keep_their_order() -> None:
    result = merge_headers({}, {"X-First": "1", "X-Second": "2"})

    assert list(result) == ["X-First", "X-Second"]
