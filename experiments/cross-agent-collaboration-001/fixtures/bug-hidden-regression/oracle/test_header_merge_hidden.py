from header_merge import merge_headers


def test_inputs_are_not_mutated() -> None:
    defaults = {"Content-Type": "application/json"}
    overrides = {"content-type": "text/plain"}

    merge_headers(defaults, overrides)

    assert defaults == {"Content-Type": "application/json"}
    assert overrides == {"content-type": "text/plain"}


def test_case_variants_within_defaults_collapse_without_moving() -> None:
    result = merge_headers(
        {"X-ID": "old", "Keep": "yes", "x-id": "new"},
        {},
    )

    assert list(result.items()) == [("x-id", "new"), ("Keep", "yes")]


def test_case_variants_within_overrides_collapse_without_moving() -> None:
    result = merge_headers(
        {"Keep": "yes"},
        {"X-ID": "old", "New": "value", "x-id": "new"},
    )

    assert list(result.items()) == [
        ("Keep", "yes"),
        ("x-id", "new"),
        ("New", "value"),
    ]


def test_empty_inputs_return_a_new_empty_dictionary() -> None:
    result = merge_headers({}, {})

    assert result == {}
    assert type(result) is dict
