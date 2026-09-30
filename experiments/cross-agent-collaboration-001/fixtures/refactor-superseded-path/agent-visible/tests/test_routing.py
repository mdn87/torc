import pytest
from routing import dispatch, dispatch_batch, legacy_route, route_request


@pytest.mark.parametrize(
    ("kind", "expected"),
    [("create", "writer"), ("read", "reader"), ("delete", "writer")],
)
def test_public_routes_preserve_behavior(kind: str, expected: str) -> None:
    assert route_request(kind) == expected
    assert legacy_route(kind) == expected


def test_dispatchers_preserve_behavior() -> None:
    assert dispatch({"kind": "read"}) == "reader"
    assert dispatch_batch([{"kind": "create"}, {"kind": "delete"}]) == [
        "writer",
        "writer",
    ]


def test_unknown_kind_preserves_error() -> None:
    with pytest.raises(ValueError, match="^unsupported request kind: update$"):
        dispatch({"kind": "update"})
