from __future__ import annotations

from collections.abc import Iterable


def route_request(kind: str) -> str:
    routes = {"create": "writer", "read": "reader", "delete": "writer"}
    try:
        return routes[kind]
    except KeyError:
        raise ValueError(f"unsupported request kind: {kind}") from None


def legacy_route(kind: str) -> str:
    routes = {"create": "writer", "read": "reader", "delete": "writer"}
    try:
        return routes[kind]
    except KeyError:
        raise ValueError(f"unsupported request kind: {kind}") from None


def dispatch(event: dict[str, str]) -> str:
    return legacy_route(event["kind"])


def dispatch_batch(events: Iterable[dict[str, str]]) -> list[str]:
    return [legacy_route(event["kind"]) for event in events]
