from __future__ import annotations

import ast
from pathlib import Path

import pytest
from routing import dispatch_batch, legacy_route


def _function(tree: ast.Module, name: str) -> ast.FunctionDef:
    return next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef) and node.name == name
    )


def test_legacy_route_is_a_thin_direct_delegate() -> None:
    tree = ast.parse(Path("routing.py").read_text(encoding="utf-8"))
    function = _function(tree, "legacy_route")

    assert len(function.body) == 1
    statement = function.body[0]
    assert isinstance(statement, ast.Return)
    assert isinstance(statement.value, ast.Call)
    assert isinstance(statement.value.func, ast.Name)
    assert statement.value.func.id == "route_request"


def test_production_dispatchers_do_not_use_superseded_path() -> None:
    tree = ast.parse(Path("routing.py").read_text(encoding="utf-8"))
    for name in ("dispatch", "dispatch_batch"):
        function = _function(tree, name)
        loaded_names = {
            node.id
            for node in ast.walk(function)
            if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Load)
        }
        assert "legacy_route" not in loaded_names
        assert "route_request" in loaded_names


def test_batch_preserves_first_unknown_error() -> None:
    with pytest.raises(ValueError, match="^unsupported request kind: update$"):
        dispatch_batch([{"kind": "read"}, {"kind": "update"}])


def test_legacy_route_remains_importable() -> None:
    assert legacy_route("read") == "reader"
