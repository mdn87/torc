from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
CONTROL_PATH = (
    ROOT / "experiments" / "cross-agent-collaboration-001" / "fixture_control.py"
)
SPEC = importlib.util.spec_from_file_location("cross_agent_fixture_control", CONTROL_PATH)
assert SPEC is not None and SPEC.loader is not None
control = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = control
SPEC.loader.exec_module(control)


def test_fixture_manifest_pins_visible_and_hidden_trees() -> None:
    result = control.verify_all()

    assert result["valid"] is True
    assert {item["fixture_id"] for item in result["fixtures"]} == {
        "bug-hidden-regression",
        "refactor-superseded-path",
        "release-policy-interaction",
    }


@pytest.mark.parametrize(
    "fixture_id",
    [
        "bug-hidden-regression",
        "refactor-superseded-path",
        "release-policy-interaction",
    ],
)
def test_staging_never_copies_oracle(fixture_id: str, tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"

    result = control.stage_fixture(fixture_id, workspace)

    assert result["oracle_staged"] is False
    assert result["staged_tree_sha256"] == result["agent_visible_sha256"]
    assert len(result["baseline_revision"]) == 40
    assert not (workspace / "oracle").exists()
    assert not any("hidden" in path.name for path in workspace.rglob("*"))
    status = subprocess.run(
        ["git", "status", "--short"],
        cwd=workspace,
        check=True,
        capture_output=True,
        text=True,
    )
    assert status.stdout == ""


def test_bug_fixture_starts_with_visible_and_hidden_failures(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    control.stage_fixture("bug-hidden-regression", workspace)

    result = control.score_fixture("bug-hidden-regression", workspace)

    assert result["visible"]["exit_status"] != 0
    assert result["hidden"]["exit_status"] != 0
    assert result["accepted"] is False


def test_refactor_fixture_hides_architecture_failure(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    control.stage_fixture("refactor-superseded-path", workspace)

    result = control.score_fixture("refactor-superseded-path", workspace)

    assert result["visible"]["exit_status"] == 0
    assert result["hidden"]["exit_status"] != 0
    assert result["accepted"] is False


def test_release_fixture_hides_policy_interactions(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    control.stage_fixture("release-policy-interaction", workspace)

    result = control.score_fixture("release-policy-interaction", workspace)

    assert result["visible"]["exit_status"] == 0
    assert result["hidden"]["exit_status"] != 0
    assert result["accepted"] is False


def test_bug_fixture_accepts_a_constraint_complete_solution(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    control.stage_fixture("bug-hidden-regression", workspace)
    (workspace / "header_merge.py").write_text(
        """from collections.abc import Mapping


def merge_headers(defaults: Mapping[str, str], overrides: Mapping[str, str]) -> dict[str, str]:
    order: list[str] = []
    values: dict[str, tuple[str, str]] = {}
    for source in (defaults, overrides):
        for name, value in source.items():
            identity = name.lower()
            if identity not in values:
                order.append(identity)
            values[identity] = (name, value)
    return {values[identity][0]: values[identity][1] for identity in order}
""",
        encoding="utf-8",
    )

    result = control.score_fixture("bug-hidden-regression", workspace)

    assert result["accepted"] is True
    assert result["workspace_diff_bytes"] > 0
    assert result["workspace_status"] == [" M header_merge.py"]


def test_refactor_fixture_accepts_the_delegating_solution(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    control.stage_fixture("refactor-superseded-path", workspace)
    routing = workspace / "routing.py"
    source = routing.read_text(encoding="utf-8")
    start = source.index("def legacy_route")
    end = source.index("\n\ndef dispatch", start)
    source = source[:start] + (
        "def legacy_route(kind: str) -> str:\n"
        "    return route_request(kind)\n"
    ) + source[end:]
    source = source.replace(
        'return legacy_route(event["kind"])', 'return route_request(event["kind"])'
    )
    source = source.replace(
        'return [legacy_route(event["kind"]) for event in events]',
        'return [route_request(event["kind"]) for event in events]',
    )
    routing.write_text(source, encoding="utf-8")

    result = control.score_fixture("refactor-superseded-path", workspace)

    assert result["accepted"] is True
    assert result["workspace_diff_bytes"] > 0
    assert result["workspace_status"] == [" M routing.py"]


def test_release_fixture_accepts_a_fail_closed_solution(tmp_path: Path) -> None:
    workspace = tmp_path / "workspace"
    control.stage_fixture("release-policy-interaction", workspace)
    (workspace / "release_policy.py").write_text(
        '''from __future__ import annotations

import hmac
from collections.abc import Iterable, Mapping


def _parts(value: object) -> tuple[str, ...] | None:
    if not isinstance(value, str) or not value or value.startswith("/") or "\\\\" in value:
        return None
    parts = value.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        return None
    return tuple(parts)


def release_allowed(
    attested_digest: str,
    artifact_digest: str,
    changes: Iterable[Mapping[str, str]],
    allowed_roots: Iterable[str],
) -> bool:
    if not hmac.compare_digest(attested_digest, artifact_digest):
        return False
    roots = [_parts(root) for root in allowed_roots]
    if not roots or any(root is None for root in roots):
        return False

    def in_scope(value: object) -> bool:
        path = _parts(value)
        return path is not None and any(path[: len(root)] == root for root in roots if root)

    try:
        for change in changes:
            action = change["action"]
            if action not in {"add", "modify", "delete", "rename"}:
                return False
            if not in_scope(change["path"]):
                return False
            if action == "rename" and not in_scope(change["from_path"]):
                return False
    except (KeyError, TypeError):
        return False
    return True
''',
        encoding="utf-8",
    )

    result = control.score_fixture("release-policy-interaction", workspace)

    assert result["accepted"] is True
    assert result["workspace_diff_bytes"] > 0
    assert result["workspace_status"] == [" M release_policy.py"]
