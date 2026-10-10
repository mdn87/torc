from __future__ import annotations

import json
from pathlib import Path

STRATEGIES = {
    "global-stop-rewrite",
    "dual-write-backfill",
    "cdc-mirror-cutover",
    "shadow-copy-cas",
}
CONSTRAINTS = {f"C{number}" for number in range(1, 8)}


def _decision() -> dict[str, object]:
    value = json.loads(Path("decision.json").read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def test_decision_has_the_frozen_shape() -> None:
    decision = _decision()

    assert set(decision) == {
        "schema_version",
        "selected_strategy",
        "rationale",
        "constraints_addressed",
        "rejected_strategies",
        "plan",
        "cutover_gate",
        "rollback",
        "max_tenant_write_pause_seconds",
    }
    assert decision["schema_version"] == 1
    assert decision["selected_strategy"] in STRATEGIES
    assert isinstance(decision["rationale"], str) and decision["rationale"]
    assert isinstance(decision["constraints_addressed"], list)
    assert set(decision["constraints_addressed"]) <= CONSTRAINTS
    assert isinstance(decision["rejected_strategies"], dict)


def test_plan_is_a_well_formed_dependency_order() -> None:
    plan = _decision()["plan"]

    assert isinstance(plan, list) and plan
    seen: set[str] = set()
    for step in plan:
        assert isinstance(step, dict)
        assert set(step) == {"step_id", "operation", "depends_on", "satisfies"}
        step_id = step["step_id"]
        assert isinstance(step_id, str) and step_id and step_id not in seen
        assert isinstance(step["operation"], str) and step["operation"]
        assert isinstance(step["depends_on"], list)
        assert set(step["depends_on"]) <= seen
        assert isinstance(step["satisfies"], list)
        assert set(step["satisfies"]) <= CONSTRAINTS
        seen.add(step_id)


def test_control_sections_have_stable_types() -> None:
    decision = _decision()

    gate = decision["cutover_gate"]
    assert isinstance(gate, dict) and set(gate) == {"mode", "requires"}
    assert isinstance(gate["mode"], str) and gate["mode"]
    assert isinstance(gate["requires"], list)
    rollback = decision["rollback"]
    assert isinstance(rollback, dict)
    assert set(rollback) == {"before_cutover", "after_cutover"}
    assert all(isinstance(value, str) and value for value in rollback.values())
    pause = decision["max_tenant_write_pause_seconds"]
    assert isinstance(pause, int) and pause >= 0
